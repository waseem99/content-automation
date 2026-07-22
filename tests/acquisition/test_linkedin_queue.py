from __future__ import annotations

import json
from pathlib import Path

import pytest

from workers.acquisition.linkedin_queue import (
    LinkedInQueueInputError,
    main,
    qualify_jsonl,
    qualify_record,
    qualify_records,
    read_jsonl,
    write_jsonl_atomic,
)


def test_qualify_record_preserves_capture_fields() -> None:
    record = {
        "capture_id": "capture-1",
        "text": "Looking for a social media agency",
        "original_author": "Buyer",
        "interaction_actor": "Commenter",
    }
    output = qualify_record(record)
    assert output["capture_id"] == "capture-1"
    assert output["original_author"] == "Buyer"
    assert output["qualification"]["disposition"] == "needs_research"
    assert output["qualification"]["queue"] == "local_only"


def test_qualify_record_rejects_missing_text() -> None:
    with pytest.raises(LinkedInQueueInputError, match="text must be a string"):
        qualify_record({"capture_id": "capture-1"})


def test_qualify_record_rejects_non_string_identity() -> None:
    with pytest.raises(LinkedInQueueInputError, match="original_author"):
        qualify_record({"text": "Need a digital agency", "original_author": 123})


def test_qualify_records_returns_disposition_counts() -> None:
    _, stats = qualify_records(
        [
            {"text": "Looking for a digital marketing agency"},
            {"text": "We are hiring a full-time social media manager. Send your CV."},
            {"text": "Digital marketing trends for 2026"},
        ]
    )
    assert stats.total == 3
    assert stats.needs_research == 1
    assert stats.individual_hiring == 1
    assert stats.not_opportunity == 1


def test_read_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "captures.jsonl"
    path.write_text('\n{"text":"Need a video production company"}\n\n', encoding="utf-8")
    assert len(read_jsonl(path)) == 1


def test_read_jsonl_reports_invalid_json_line(tmp_path: Path) -> None:
    path = tmp_path / "captures.jsonl"
    path.write_text('{"text":"ok"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(LinkedInQueueInputError, match="line 2"):
        read_jsonl(path)


def test_read_jsonl_rejects_non_object_record(tmp_path: Path) -> None:
    path = tmp_path / "captures.jsonl"
    path.write_text('["not", "an", "object"]\n', encoding="utf-8")
    with pytest.raises(LinkedInQueueInputError, match="record must be a JSON object"):
        read_jsonl(path)


def test_atomic_writer_replaces_existing_output(tmp_path: Path) -> None:
    path = tmp_path / "qualified.jsonl"
    path.write_text("legacy\n", encoding="utf-8")
    write_jsonl_atomic(path, [{"text": "replacement"}])
    assert json.loads(path.read_text(encoding="utf-8")) == {"text": "replacement"}
    assert not (tmp_path / ".qualified.jsonl.tmp").exists()


def test_qualify_jsonl_writes_local_qualified_output(tmp_path: Path) -> None:
    input_path = tmp_path / "captures.jsonl"
    output_path = tmp_path / "qualified.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "text": "Looking for AI-powered videos and animations",
                "original_author": "Saad Rasheed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    stats = qualify_jsonl(input_path, output_path)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert stats.needs_research == 1
    assert output["qualification"]["owner"] == "Waseem"
    assert output["qualification"]["queue"] == "local_only"
    assert output["original_author"] == "Saad Rasheed"


def test_cli_prints_stats_and_writes_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "captures.jsonl"
    output_path = tmp_path / "qualified.jsonl"
    input_path.write_text('{"text":"Need a content production agency"}\n', encoding="utf-8")
    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0
    assert json.loads(capsys.readouterr().out)["needs_research"] == 1
    assert output_path.exists()


def test_cli_fails_closed_for_invalid_input(tmp_path: Path) -> None:
    input_path = tmp_path / "captures.jsonl"
    output_path = tmp_path / "qualified.jsonl"
    input_path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="qualification failed"):
        main(["--input", str(input_path), "--output", str(output_path)])
    assert not output_path.exists()
