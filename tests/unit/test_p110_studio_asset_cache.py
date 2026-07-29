from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "web" / "static-creator-ui" / "index.html"
STUDIO_RUNTIME = ROOT / "src" / "operator_api" / "studio_runtime.py"


def test_creator_studio_assets_use_one_versioned_release_key() -> None:
    index = INDEX.read_text(encoding="utf-8")
    asset_urls = re.findall(r'(?:src|href)="(/assets/[^"]+)"', index)
    assert asset_urls
    versions = {url.split("?v=", 1)[1] for url in asset_urls if "?v=" in url}
    assert len(versions) == 1
    assert len(versions) == len({url.split("?v=", 1)[1] for url in asset_urls})
    assert index.index("studio-v2-api.js") < index.index("studio-v2-p110.js")


def test_creator_studio_static_responses_disable_browser_caching() -> None:
    source = STUDIO_RUNTIME.read_text(encoding="utf-8")
    assert "class NoStoreStaticFiles" in source
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in source
    assert 'app.mount("/assets", NoStoreStaticFiles' in source
    assert 'app.mount("/data", NoStoreStaticFiles' in source
