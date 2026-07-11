import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "reference-engine"


def test_p66_local_engine_contract_is_present() -> None:
    required = [
        ENGINE / "pyproject.toml",
        ENGINE / "README.md",
        ENGINE / "refintel" / "models.py",
        ENGINE / "refintel" / "ingest.py",
        ENGINE / "refintel" / "media.py",
        ENGINE / "refintel" / "transcript.py",
        ENGINE / "refintel" / "analysis.py",
        ENGINE / "refintel" / "report.py",
        ENGINE / "refintel" / "fingerprint.py",
        ENGINE / "refintel" / "pipeline.py",
        ENGINE / "refintel" / "cli.py",
        ENGINE / "refintel" / "api.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"Missing P66 files: {missing}"


def test_p66_is_excluded_from_static_vercel_bundle() -> None:
    vercel_ignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert "reference-engine/" in vercel_ignore.splitlines()

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    ignore_command = config.get("ignoreCommand", "")
    assert "web/static-creator-ui" in ignore_command
    assert "reference-engine" not in ignore_command


def test_p66_requires_human_review_and_rights_declaration() -> None:
    models = (ENGINE / "refintel" / "models.py").read_text(encoding="utf-8")
    assert 'PUBLIC_INTERNAL_RESEARCH = "public-internal-research"' in models
    assert 'human_review_required: Literal[True]' in models
    assert 'status: Literal["draft_for_human_review"]' in models


def test_p66_has_offline_acceptance_workflow() -> None:
    workflow = (ROOT / ".github" / "workflows" / "p66-reference-engine.yml").read_text(
        encoding="utf-8"
    )
    assert "Run offline tests" in workflow
    assert "Verify Vercel exclusion" in workflow
    assert "pytest -vv" in workflow
