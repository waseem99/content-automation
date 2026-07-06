from __future__ import annotations

from uuid import UUID

import pytest

from src.application.intake_service import CreateIntakeRequest, IntakeValidationError, SourceIntakeService
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_topic_only_intake_is_persisted_with_event(database) -> None:
    workflow_id = create_workflow(database)
    result = SourceIntakeService(database).create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic="Arsenal comeback angle",
            created_by="pytest",
            football_metadata={"team": "Arsenal", "league": "Premier League"},
        )
    )

    assert result.created is True
    assert result.intake.topic == "Arsenal comeback angle"
    assert result.intake.created_by == "pytest"
    assert result.intake.football_metadata["team"] == "Arsenal"
    assert result.references == []

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'content_intake_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["intake_id"] == str(result.intake.id)


def test_url_backed_intake_stores_normalized_reference(database) -> None:
    workflow_id = create_workflow(database)
    result = SourceIntakeService(database).create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            source_urls=("HTTPS://Example.com/Match?b=2&a=1",),
            created_by="pytest",
        )
    )

    assert result.created is True
    assert len(result.references) == 1
    assert result.references[0]["normalized_url"] == "https://example.com/Match?a=1&b=2"


def test_combined_topic_and_url_intake_has_stable_hash(database) -> None:
    workflow_id = create_workflow(database)
    service = SourceIntakeService(database)
    first = service.create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic="Derby preview",
            angle="tactical story",
            source_urls=("https://example.com/story",),
            created_by="pytest",
        )
    )
    second = service.create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic="  Derby   preview ",
            angle="tactical story",
            source_urls=("https://example.com/story",),
            created_by="pytest",
        )
    )

    assert first.created is True
    assert second.created is False
    assert second.intake.id == first.intake.id
    assert second.intake.canonical_input_hash == first.intake.canonical_input_hash


def test_invalid_intake_inputs_fail_closed(database) -> None:
    workflow_id = create_workflow(database)
    service = SourceIntakeService(database)

    with pytest.raises(IntakeValidationError, match="Provide"):
        service.create(CreateIntakeRequest(workflow_run_id=workflow_id, created_by="pytest"))

    for bad_url in ("file:///tmp/story.txt", "/tmp/story.txt", "ftp://example.com/story", "http://localhost/story"):
        with pytest.raises(IntakeValidationError):
            service.create(
                CreateIntakeRequest(
                    workflow_run_id=workflow_id,
                    source_urls=(bad_url,),
                    created_by="pytest",
                )
            )


def test_list_for_workflow_returns_created_intakes(database) -> None:
    workflow_id = create_workflow(database)
    service = SourceIntakeService(database)
    created = service.create(
        CreateIntakeRequest(workflow_run_id=workflow_id, topic="Transfer explainer", created_by="pytest")
    )

    rows = service.list_for_workflow(workflow_id)
    assert [row.id for row in rows] == [created.intake.id]
    assert isinstance(rows[0].workflow_run_id, UUID)
