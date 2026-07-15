from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "reference-engine"


def test_p75_adapter_contract_and_operator_docs_exist() -> None:
    for relative in ("refintel/adapters.py", "tests/test_p75_adapters.py"):
        assert (ENGINE / relative).is_file()
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
