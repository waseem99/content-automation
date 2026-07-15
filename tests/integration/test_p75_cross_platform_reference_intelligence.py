from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "reference-engine"


def test_p75_adapter_contract_and_operator_docs_exist() -> None:
    for relative in ("refintel/adapters.py", "tests/test_p75_adapters.py"):
        assert (ENGINE / relative).is_file()
    assert (ENGINE / "refintel" / "acquisition.py").is_file()
    assert (ENGINE / "tests" / "test_p75_acquisition.py").is_file()
    assert (ROOT / "docs" / "operations" / "p75-cross-platform-reference-intelligence.md").is_file()


def test_p75_covers_requested_platforms_and_media_shapes() -> None:
    adapters = (ENGINE / "refintel" / "adapters.py").read_text(encoding="utf-8")
    models = (ENGINE / "refintel" / "models.py").read_text(encoding="utf-8")
    for platform in ("FACEBOOK", "YOUTUBE", "INSTAGRAM", "TIKTOK", "X", "SNAPCHAT"):
        assert f"Platform.{platform}" in adapters
    for media_kind in ("VIDEO", "IMAGE", "CAROUSEL", "MIXED"):
        assert f'{media_kind} = "{media_kind.lower()}"' in adapters
    assert 'SNAPCHAT = "snapchat"' in models


def test_p75_is_honest_about_conditional_routes_and_access_controls() -> None:
    adapters = (ENGINE / "refintel" / "adapters.py").read_text(encoding="utf-8")
    docs = (
        ROOT / "docs" / "operations" / "p75-cross-platform-reference-intelligence.md"
    ).read_text(encoding="utf-8")
    assert "SupportLevel.CONDITIONAL" in adapters
    assert "requires_resolution" in adapters
    assert "operator-controlled" in adapters
    assert "does not bypass" in docs
    assert "originality" in docs.lower()


def test_p75_canonical_identity_preserves_query_media_ids() -> None:
    ingest = (ENGINE / "refintel" / "ingest.py").read_text(encoding="utf-8")
    assert 'return f"url:{canonicalize_url(url)}"' in ingest


def test_p75_acquisition_is_resumable_sanitized_and_batch_isolated() -> None:
    acquisition = (ENGINE / "refintel" / "acquisition.py").read_text(encoding="utf-8")
    cli = (ENGINE / "refintel" / "cli.py").read_text(encoding="utf-8")
    facebook = (ENGINE / "refintel" / "facebook.py").read_text(encoding="utf-8")
    portfolio = (ROOT / "scripts" / "p74_run_facebook_portfolio.py").read_text(
        encoding="utf-8"
    )
    assert 'schema_version: str = "p75.acquisition.v1"' in acquisition
    assert '"continuedl": self.policy.continue_partial_downloads' in acquisition
    assert '"concurrent_fragment_downloads": 1' in acquisition
    assert "sha256_path(primary) == primary_record.sha256" in acquisition
    assert "SENSITIVE_QUERY_KEYS" in acquisition
    assert '@app.command("acquire-batch")' in cli
    assert '@app.command("discover-url")' in cli
    assert '"fallback_action": "Use ingest-file' in cli
    assert "acquire_only: bool = False" in facebook
    assert "def resolve_facebook_share_url(" in facebook
    assert "p75.facebook_share_resolution.v1" in facebook
    assert 'parser.add_argument("--acquire-only"' in portfolio


def test_p75_keeps_source_media_local_and_out_of_vercel() -> None:
    acquisition = (ENGINE / "refintel" / "acquisition.py").read_text(encoding="utf-8")
    vercel_ignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert "source_media_must_not_enter_generated_content: bool = True" in acquisition
    assert "human_review_required: bool = True" in acquisition
    assert "reference-engine/" in vercel_ignore.splitlines()
