from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPORT = Path("docs/operations/p28-closeout-report.md")
CHECKLIST = Path("docs/operations/p28-closeout-checklist.json")

P28_ARTIFACTS = [
    "src/long_form_concept.py",
    "docs/operations/p28-step-01.md",
    "docs/operations/p28-long-form-concept-example.json",
    "tests/integration/test_p28_step_01.py",
    "src/long_form_command_contract.py",
    "docs/operations/p28-step-02.md",
    "docs/operations/p28-produce-longform-output-contract-example.json",
    "tests/integration/test_p28_step_02.py",
    "src/series_metadata.py",
    "docs/operations/p28-step-03.md",
    "docs/operations/p28-series-metadata-example.json",
    "tests/integration/test_p28_step_03.py",
    "src/topic_calendar.py",
    "docs/operations/p28-step-04.md",
    "docs/operations/p28-topic-calendar-example.json",
    "tests/integration/test_p28_step_04.py",
    "src/shorts_longform_funnel.py",
    "docs/operations/p28-step-05.md",
    "docs/operations/p28-shorts-longform-funnel-example.json",
    "tests/integration/test_p28_step_05.py",
    "docs/operations/p28-closeout-report.md",
    "docs/operations/p28-closeout-checklist.json",
    "tests/integration/test_p28_step_06.py",
]


def test_p28_closeout_report_references_scope_and_child_tasks() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #361 after the PR merges.",
        "#356",
        "#357",
        "#358",
        "#359",
        "#360",
        "#361",
        "P28-01 — Define long-form 16:9 concept model",
        "P28-02 — Design produce-longform command and output contract",
        "P28-03 — Add series and episode metadata contract",
        "P28-04 — Define topic scoring and content calendar contract",
        "P28-05 — Define Shorts-to-long-form funnel and cutdown map",
        "P28-06 — P28 long-form and topic intelligence closeout",
    ]:
        assert term in content


def test_p28_closeout_report_confirms_artifact_and_validation_coverage() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "long-form 16:9 concept planning",
        "future `produce-longform` command and output design",
        "repeatable series and episode metadata",
        "topic scoring rubric",
        "review-only content calendar",
        "Shorts-to-long-form funnel types",
        "cutdown map fields and examples",
        "content package connections",
        "P27 export-after-review connections",
        "required long-form concept fields",
        "required produce-longform CLI arguments",
        "required series metadata fields",
        "topic scoring dimensions",
        "content calendar fields",
        "funnel types",
        "cutdown map fields",
        "publish_allowed: false",
        "review_required: true",
    ]:
        assert term in content


def test_p28_closeout_report_documents_future_work_and_guardrails() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "produce-longform CLI implementation",
        "long-form video assembly",
        "16:9 rendering pipeline",
        "Shorts cutdown rendering",
        "analytics feedback loop",
        "YouTube search-volume or trend data integration",
        "YouTube upload API integration",
        "TikTok/Meta/X upload APIs",
        "content scheduling automation",
        "treat planning contracts as publish approval",
        "render or upload media without scoped implementation issues",
        "set `publish_allowed` to `true` by default",
        "skip rights review",
        "skip P29 editorial approval",
        "bypass P26 risk gates",
        "commit rendered video assets",
        "commit credentials or secrets",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p28_closeout_checklist_schema_and_child_tasks() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    assert checklist["schema_version"] == "p28.closeout_checklist.v1"
    assert checklist["parent_epic"] == 330
    assert checklist["closeout_issue"] == 361
    assert checklist["publish_allowed"] is False
    assert checklist["review_required"] is True
    assert checklist["p28_complete_after_issue_361_merge"] is True

    child_tasks = checklist["child_tasks"]
    assert [task["issue"] for task in child_tasks] == [356, 357, 358, 359, 360, 361]
    assert [task["step"] for task in child_tasks] == ["P28-01", "P28-02", "P28-03", "P28-04", "P28-05", "P28-06"]

    for task in child_tasks[:-1]:
        assert task["status"] == "complete"
        assert task["required_artifacts"]

    assert child_tasks[-1]["status"] == "complete_after_merge"


def test_p28_closeout_checklist_artifacts_exist() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    checklist_artifacts = {
        artifact
        for task in checklist["child_tasks"]
        for artifact in task["required_artifacts"]
    }

    assert checklist_artifacts == set(P28_ARTIFACTS)

    for artifact in checklist_artifacts:
        assert Path(artifact).exists(), artifact


def test_p28_closeout_checklist_contract_coverage_and_validation_summary() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    coverage = checklist["contract_coverage"]
    for key in [
        "long_form_concept_model",
        "produce_longform_command_design",
        "series_episode_metadata",
        "topic_scoring_rubric",
        "content_calendar_contract",
        "shorts_longform_funnel",
        "cutdown_map_contract",
        "content_package_connections",
        "p27_export_after_review_connections",
    ]:
        assert coverage[key] is True

    validation = checklist["validation_summary"]
    assert validation["long_form_validation"] == "src/long_form_concept.py"
    assert validation["produce_longform_validation"] == "src/long_form_command_contract.py"
    assert validation["series_metadata_validation"] == "src/series_metadata.py"
    assert validation["topic_calendar_validation"] == "src/topic_calendar.py"
    assert validation["funnel_validation"] == "src/shorts_longform_funnel.py"
    assert validation["publish_allowed"] is False
    assert validation["review_required"] is True


def test_p28_closeout_future_work_and_guardrails_preserved() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    for gap in [
        "produce-longform CLI implementation",
        "long-form video assembly",
        "16:9 rendering pipeline",
        "Shorts cutdown rendering",
        "analytics feedback loop",
        "YouTube upload API integration",
        "TikTok/Meta/X upload APIs",
        "content scheduling automation",
    ]:
        assert gap in checklist["future_work_out_of_scope"]

    for guardrail in [
        "No publish approval in P28.",
        "No long-form rendering in P28 closeout.",
        "No Shorts cutdown rendering in P28 closeout.",
        "No upload API integration in P28 closeout.",
        "No live trend scraping in P28 closeout.",
        "No YouTube search-volume API integration in P28 closeout.",
        "No analytics-based cutdown selection in P28 closeout.",
        "No platform credentials.",
        "No secret values.",
        "No rendered video asset commits.",
        "No bypass of P26 risk gates.",
        "No bypass of P29 editorial governance.",
        "No workflow gate bypass.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]
