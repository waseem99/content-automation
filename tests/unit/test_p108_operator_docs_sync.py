from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
CREATOR_STUDIO = ROOT / "docs" / "operations" / "CREATOR_STUDIO_V2.md"
LOCAL_RUNBOOK = ROOT / "docs" / "operations" / "LOCAL_PRODUCTION_RUNBOOK.md"
ACTIVATION = ROOT / "docs" / "operations" / "PRODUCTION_ACTIVATION.md"


STALE_PUBLIC_ROLE_PHRASES = (
    "Admin, Producer, Reviewer, and Publisher roles",
    "Producer or Admin",
    "Publisher workspace",
    "copy Producer, Reviewer, and Publisher keys",
    "Producer and Admin users see",
    "a Producer or Admin opens",
    "human Publisher/Admin",
)

STALE_INTEGRATION_PHRASES = (
    "No Higgsfield or other managed renderer is configured",
    "No live social publishing adapter is enabled",
    "Higgsfield or another real managed renderer until a supported account integration is configured",
    "Managed natural-motion rendering through Higgsfield or another provider",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_operator_docs_expose_only_three_public_roles() -> None:
    combined = "\n".join(_read(path) for path in (README, CREATOR_STUDIO, LOCAL_RUNBOOK, ACTIVATION))

    assert "Super Admin" in combined
    assert "Admin" in combined
    assert "Reviewer" in combined
    assert "three user-facing roles" in combined or "three public roles" in combined
    assert "internal compatibility permissions" in combined or "internal compatibility capabilities" in combined

    for phrase in STALE_PUBLIC_ROLE_PHRASES:
        assert phrase not in combined


def test_operator_docs_match_current_remote_and_provider_paths() -> None:
    combined = "\n".join(_read(path) for path in (README, CREATOR_STUDIO, LOCAL_RUNBOOK, ACTIVATION))

    assert "deploy_remote_content_automation.ps1" in combined
    assert "check_production_readiness.ps1" in combined
    assert "setup_youtube_official.ps1" in combined
    assert "setup_higgsfield_official.ps1" in combined
    assert "private-only" in combined or "private by default" in combined
    assert "explicit" in combined and "spend approval" in combined

    for phrase in STALE_INTEGRATION_PHRASES:
        assert phrase not in combined


def test_operator_docs_keep_real_execution_gates_explicit() -> None:
    combined = "\n".join(_read(path) for path in (README, LOCAL_RUNBOOK, ACTIVATION))

    assert "four-item P100" in combined or "P100 four-item" in combined
    assert "one real Higgsfield managed shot" in combined or "real managed shot" in combined
    assert "one separately approved external live result" in combined
    assert "six-video" in combined
    assert "Generated media" in combined and "outside Git" in combined
    assert "Automatic final approval" in combined
    assert "Automatic public publishing" in combined
