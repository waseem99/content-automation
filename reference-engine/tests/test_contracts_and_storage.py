from pathlib import Path

import pytest

from refintel.media import interval_timestamps
from refintel.models import (
    Platform,
    ReferenceProject,
    RightsDeclaration,
    SourceAccess,
    SourceDescriptor,
)
from refintel.storage import WorkspaceStore


def make_project(store: WorkspaceStore) -> ReferenceProject:
    workspace = store.create_workspace("ref-test123")
    return ReferenceProject(
        reference_id="ref-test123",
        source=SourceDescriptor(
            kind="file",
            platform=Platform.LOCAL,
            original_path="fixture.mp4",
            title="Fixture",
            canonical_key="sha256:test",
        ),
        access=SourceAccess(declaration=RightsDeclaration.OWNED),
        workspace_path=str(workspace),
    )


def test_project_round_trip(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "workspace")
    project = make_project(store)
    store.save_project(project)
    loaded = store.load_project(project.reference_id)
    assert loaded == project
    assert store.find_by_canonical_key("sha256:test") == "ref-test123"
    assert store.list_references()[0]["rights_declaration"] == "owned"


def test_workspace_layout_is_created(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "workspace")
    workspace = store.create_workspace("ref-layout")
    assert (workspace / "source").is_dir()
    assert (workspace / "frames" / "interval").is_dir()
    assert (workspace / "reports" / "assets").is_dir()
    assert (workspace / "exports").is_dir()


def test_interval_timestamps_include_minute_boundaries() -> None:
    assert interval_timestamps(125.0, 60) == [0.0, 60.0, 120.0]
    assert interval_timestamps(60.0, 60) == [0.0, 59.95]
    assert interval_timestamps(0.0, 60) == [0.0]
    with pytest.raises(ValueError):
        interval_timestamps(10, 0)
