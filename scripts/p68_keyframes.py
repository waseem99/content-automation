#!/usr/bin/env python3
"""Plan, intake, and approve P68 natural-motion keyframes."""

from __future__ import annotations

import argparse
import json

from src.p68_keyframe_batch import approve_keyframe, intake_keyframe, write_keyframe_work_orders


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "intake", "approve"))
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--output", default="p68-artifacts/keyframe-work-orders.json")
    parser.add_argument("--pilot")
    parser.add_argument("--shot")
    parser.add_argument("--source")
    parser.add_argument("--source-kind", choices=("generated_original", "commissioned_original", "licensed_asset"))
    parser.add_argument("--provider")
    parser.add_argument("--model-or-collection")
    parser.add_argument("--rights-evidence")
    parser.add_argument("--reviewer")
    parser.add_argument("--note")
    args = parser.parse_args()
    if args.command == "plan":
        result = write_keyframe_work_orders(args.pilots_root, args.artifact_root, args.output)
    elif args.command == "intake":
        required = (args.pilot, args.shot, args.source, args.source_kind, args.provider, args.model_or_collection, args.rights_evidence)
        if not all(required):
            parser.error("intake requires pilot, shot, source, source-kind, provider, model-or-collection, and rights-evidence")
        result = intake_keyframe(
            pilots_root=args.pilots_root, artifact_root=args.artifact_root, pilot_id=args.pilot,
            shot_id=args.shot, source_path=args.source, source_kind=args.source_kind,
            provider=args.provider, model_or_collection=args.model_or_collection, rights_evidence=args.rights_evidence,
        )
    else:
        if not all((args.pilot, args.shot, args.reviewer, args.note)):
            parser.error("approve requires pilot, shot, reviewer, and note")
        result = approve_keyframe(
            artifact_root=args.artifact_root, pilot_id=args.pilot, shot_id=args.shot,
            reviewer=args.reviewer, note=args.note,
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
