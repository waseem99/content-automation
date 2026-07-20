from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_entrypoint_line_endings_are_linux_safe() -> None:
    dockerfile = (ROOT / "deploy/p68-local-keyframe-worker/Dockerfile").read_text(encoding="utf-8")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    entrypoint = (ROOT / "deploy/p68-local-keyframe-worker/entrypoint.sh").read_bytes()

    assert "sed -i 's/\\r$//' /usr/local/bin/p68-local-keyframe-entrypoint" in dockerfile
    assert "head -n 1 /usr/local/bin/p68-local-keyframe-entrypoint" in dockerfile
    assert "*.sh text eol=lf" in attributes
    assert bytes((13, 10)) not in entrypoint
