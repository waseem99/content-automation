#!/usr/bin/env python3
"""Generate one local, normalized Kokoro narration from a P68 voice project."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.getenv("KOKORO_RUNTIME_DIR", ROOT / ".runtime" / "kokoro-onnx"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME))

from src.p78_kokoro_narration import synthesize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--pilots-root", type=Path, default=Path("p68-pilots"))
    parser.add_argument("--artifact-root", type=Path, default=Path("p68-artifacts"))
    parser.add_argument("--model", type=Path, default=Path(os.getenv("KOKORO_MODEL_PATH", ".runtime/kokoro-models/kokoro-v1.0.onnx")))
    parser.add_argument("--voices", type=Path, default=Path(os.getenv("KOKORO_VOICES_PATH", ".runtime/kokoro-models/voices-v1.0.bin")))
    parser.add_argument("--voice", default=os.getenv("KOKORO_VOICE", "am_michael"))
    parser.add_argument("--speed", type=float, default=float(os.getenv("KOKORO_SPEED", "1.17")))
    args = parser.parse_args()
    project = json.loads((args.pilots_root / args.pilot / "voice-project.json").read_text(encoding="utf-8"))
    output_dir = args.artifact_root / "gold" / args.pilot / "narration"
    evidence = synthesize(
        text=str(project["narration"]), model_path=args.model, voices_path=args.voices, voice=args.voice, speed=args.speed,
        output_path=output_dir / f"{args.pilot}-kokoro.wav", evidence_path=output_dir / f"{args.pilot}-kokoro-alignment.json",
    )
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
