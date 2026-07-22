from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .linkedin_qualification import (
    DEFAULT_OWNER,
    LinkedInPostSignal,
    OpportunityDisposition,
    classify_linkedin_opportunity,
)


class LinkedInQueueInputError(ValueError):
    def __init__(self, message: str, *, line_number: int | None = None) -> None:
        self.line_number = line_number
        prefix = f"line {line_number}: " if line_number is not None else ""
        super().__init__(prefix + message)


@dataclass(frozen=True, slots=True)
class QualificationBatchStats:
    total: int = 0
    needs_research: int = 0
    individual_hiring: int = 0
    not_opportunity: int = 0


def _first_string(
    record: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    required: bool = False,
) -> str | None:
    for key in keys:
        if key not in record or record.get(key) is None:
            continue
        value = record[key]
        if not isinstance(value, str):
            raise LinkedInQueueInputError(f"{key} must be a string or null")
        return value
    if required:
        raise LinkedInQueueInputError(f"one of {', '.join(keys)} must be a string")
    return None


def qualify_record(
    record: Mapping[str, Any],
    *,
    owner: str = DEFAULT_OWNER,
) -> dict[str, Any]:
    text = _first_string(
        record,
        ("text", "post_text", "content", "raw_signal_summary"),
        required=True,
    )
    assert text is not None

    canonical_post_url = _first_string(
        record,
        ("canonical_post_url", "original_post_url", "source_link"),
    )
    source_url = _first_string(
        record,
        ("source_url", "capture_url", "source_link"),
    )
    signal = LinkedInPostSignal(
        text=text,
        original_author=_first_string(record, ("original_author", "person_name")),
        interaction_actor=_first_string(
            record, ("interaction_actor", "wrapper_actor")
        ),
        canonical_post_url=canonical_post_url,
        source_url=source_url,
    )
    decision = classify_linkedin_opportunity(signal, owner=owner)
    return {
        **dict(record),
        "qualification": {
            "disposition": decision.disposition.value,
            "status_label": decision.status_label,
            "status": decision.status,
            "service": decision.service,
            "intent": decision.intent,
            "priority": decision.priority,
            "win_potential": decision.win_potential,
            "queue": decision.queue,
            "owner": decision.owner,
            "is_genuine_opportunity": decision.is_genuine_opportunity,
            "is_job_vacancy": decision.is_job_vacancy,
            "matched_services": list(decision.matched_services),
            "reason_codes": list(decision.reason_codes),
        },
    }


def qualify_records(
    records: Iterable[Mapping[str, Any]],
    *,
    owner: str = DEFAULT_OWNER,
) -> tuple[list[dict[str, Any]], QualificationBatchStats]:
    qualified: list[dict[str, Any]] = []
    counts = {
        OpportunityDisposition.NEEDS_RESEARCH.value: 0,
        OpportunityDisposition.INDIVIDUAL_HIRING.value: 0,
        OpportunityDisposition.NOT_OPPORTUNITY.value: 0,
    }
    for record in records:
        output = qualify_record(record, owner=owner)
        qualified.append(output)
        counts[output["qualification"]["disposition"]] += 1
    return qualified, QualificationBatchStats(
        total=len(qualified),
        needs_research=counts[OpportunityDisposition.NEEDS_RESEARCH.value],
        individual_hiring=counts[OpportunityDisposition.INDIVIDUAL_HIRING.value],
        not_opportunity=counts[OpportunityDisposition.NOT_OPPORTUNITY.value],
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LinkedInQueueInputError(
                    f"invalid JSON ({exc.msg})", line_number=line_number
                ) from exc
            if not isinstance(value, dict):
                raise LinkedInQueueInputError(
                    "record must be a JSON object", line_number=line_number
                )
            try:
                records.append(dict(value))
            except (TypeError, ValueError) as exc:
                raise LinkedInQueueInputError(
                    "record cannot be converted to an object", line_number=line_number
                ) from exc
    return records


def write_jsonl_atomic(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def qualify_jsonl(
    input_path: Path,
    output_path: Path,
    *,
    owner: str = DEFAULT_OWNER,
) -> QualificationBatchStats:
    records = read_jsonl(input_path)
    qualified, stats = qualify_records(records, owner=owner)
    write_jsonl_atomic(output_path, qualified)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify captured LinkedIn records into a local-only research queue."
    )
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL capture file")
    parser.add_argument("--output", type=Path, required=True, help="Output qualified JSONL file")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="Local research owner")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        stats = qualify_jsonl(args.input, args.output, owner=args.owner)
    except (OSError, LinkedInQueueInputError) as exc:
        raise SystemExit(f"qualification failed: {exc}") from exc
    print(json.dumps(asdict(stats), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
