from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "reference-engine"


def test_p75_adapter_contract_and_operator_docs_exist() -> None:
    for relative in ("refintel/adapters.py", "tests/test_p75_adapters.py"):
        assert (ENGINE / relative).is_file()
    assert (ENGINE / "refintel" / "acquisition.py").is_file()
    assert (ENGINE / "tests" / "test_p75_acquisition.py").is_file()
    assert (ENGINE / "refintel" / "images.py").is_file()
    assert (ENGINE / "refintel" / "settings.py").is_file()
    assert (ENGINE / "tests" / "test_p75_images.py").is_file()
    assert (
        ROOT / "docs" / "operations" / "p75-cross-platform-reference-intelligence.md"
    ).is_file()


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


def test_p75_image_carousel_contract_is_typed_resumable_and_originality_safe() -> None:
    images = (ENGINE / "refintel" / "images.py").read_text(encoding="utf-8")
    cli = (ENGINE / "refintel" / "cli.py").read_text(encoding="utf-8")
    docs = (
        ROOT / "docs" / "operations" / "p75-cross-platform-reference-intelligence.md"
    ).read_text(encoding="utf-8")
    assert 'schema_version: str = "p75.image_reference.v1"' in images
    assert "source_digest" in images
    assert "ImageFailure" in images
    assert "source_text_must_not_be_reused_verbatim: bool = True" in images
    assert "source_media_must_not_enter_generated_content: bool = True" in images
    assert "human_review_required: bool = True" in images
    assert '@app.command("process-images")' in cli
    assert "deterministic measurements" in docs
    assert "local-first" in docs


def test_p75_local_auth_env_contract_uses_paths_not_raw_credentials() -> None:
    settings = (ENGINE / "refintel" / "settings.py").read_text(encoding="utf-8")
    example = (ENGINE / ".env.example").read_text(encoding="utf-8")
    assert "REFINTEL_FACEBOOK_PROFILE" in settings
    assert "REFINTEL_FACEBOOK_COOKIE_FILE" in settings
    assert "FACEBOOK_PASSWORD" not in settings
    assert "FACEBOOK_EMAIL" not in settings
    assert "Never paste cookie contents" in example


def test_p75_temporal_report_contract_combines_modalities_without_overclaiming() -> (
    None
):
    temporal = (ENGINE / "refintel" / "temporal.py").read_text(encoding="utf-8")
    pipeline = (ENGINE / "refintel" / "pipeline.py").read_text(encoding="utf-8")
    report = (ENGINE / "refintel" / "report.py").read_text(encoding="utf-8")
    assert 'schema_version: str = "p75.temporal_report.v1"' in temporal
    for expected in (
        "every_frame_metrics.json",
        "audio.wav",
        "transcript.json",
        "extract_ocr",
        "motion_disclosure",
        "production_difficulty",
        "source_media_must_not_enter_generated_content: bool = True",
        "source_text_must_not_be_reused_verbatim: bool = True",
        "human_review_required: bool = True",
    ):
        assert expected in temporal
    assert "build_temporal_report(" in pipeline
    assert "Temporal evidence report" in report


def test_p75_comparison_contract_is_typed_resumable_and_originality_gated() -> None:
    comparison = (ENGINE / "refintel" / "comparison.py").read_text(encoding="utf-8")
    cli = (ENGINE / "refintel" / "cli.py").read_text(encoding="utf-8")
    docs = (
        ROOT / "docs" / "operations" / "p75-cross-platform-reference-intelligence.md"
    ).read_text(encoding="utf-8")
    for expected in (
        'schema_version: str = "p75.reference_comparison.v1"',
        'schema_version: str = "p75.pattern_brief.v1"',
        'schema_version: str = "p75.originality_gate.v1"',
        "source_specific_expression_compared: bool = False",
        "source_excerpt_persisted: bool = False",
        "source_media_must_not_enter_generated_content: bool = True",
        "source_identities_watermarks_voices_music_excluded: bool = True",
        "automatic_generation: bool = False",
        "automatic_publication: bool = False",
        "human_review_required: bool = True",
        "transcript_sha256",
        "project_sha256",
    ):
        assert expected in comparison
    assert '@app.command("compare-library")' in cli
    assert "controlled visual/audio/mechanics terms" in docs
    assert "missing transcript never becomes an originality pass" in docs.lower()
