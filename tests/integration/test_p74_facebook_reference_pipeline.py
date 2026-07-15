import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "reference-engine"


def test_p74_has_browser_discovery_batch_and_every_frame_modules():
    for relative in (
        "refintel/facebook.py",
        "refintel/frame_stream.py",
        "tests/test_p74_facebook_page_pipeline.py",
    ):
        assert (ENGINE / relative).is_file()
    assert (ROOT / "scripts" / "p74_run_facebook_portfolio.py").is_file()
    assert (ROOT / "docs" / "operations" / "p74-facebook-reference-ingestion.md").is_file()


def test_p74_uses_stable_configured_pages_for_four_priority_brands():
    config = json.loads(
        (ROOT / "config" / "portfolio-brands.staging.json").read_text(encoding="utf-8")
    )
    brands = {item["slug"]: item for item in config["brands"]}
    assert brands["rawr-nation"]["source_links"] == [
        "https://www.facebook.com/RawrNationTV"
    ]
    assert brands["animal-x"]["source_links"][0].endswith("61566325046583")
    assert brands["historiq"]["source_links"][0].endswith("61580906280508")
    assert brands["ani-films"]["source_links"][0].endswith("61563298430902")


def test_p74_keeps_authentication_local_and_has_no_access_bypass():
    facebook = (ENGINE / "refintel" / "facebook.py").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "launch_persistent_context" in facebook
    assert "export_netscape_cookies" in facebook
    assert 'os.chmod(target, 0o600)' in facebook
    assert 'if key != "cookie_file"' in facebook
    assert "facebook-cookies.txt" in gitignore
    for forbidden in ("captcha solver", "captcha bypass", "drm bypass", "stealth plugin"):
        assert forbidden not in facebook.lower()


def test_p74_decodes_every_frame_and_adds_sequence_storytelling():
    frame_stream = (ENGINE / "refintel" / "frame_stream.py").read_text(encoding="utf-8")
    analysis = (ENGINE / "refintel" / "analysis.py").read_text(encoding="utf-8")
    fingerprint = (ENGINE / "refintel" / "fingerprint.py").read_text(encoding="utf-8")
    pipeline = (ENGINE / "refintel" / "pipeline.py").read_text(encoding="utf-8")
    assert "while True:" in frame_stream and "capture.read()" in frame_stream
    assert '"frames": measured' in frame_stream
    assert "def analyze_sequence(" in analysis
    assert "chronologically ordered frames and transcript" in analysis
    assert "Sequence observation for human review" in fingerprint
    assert "every_frame: bool = False" in pipeline


def test_p74_browser_dependency_is_optional_and_vercel_remains_excluded():
    project = (ENGINE / "pyproject.toml").read_text(encoding="utf-8")
    vercel_ignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert 'browser = ["playwright>=1.50,<2"]' in project
    assert '"playwright>=1.50,<2"' in project
    assert "reference-engine/" in vercel_ignore.splitlines()
