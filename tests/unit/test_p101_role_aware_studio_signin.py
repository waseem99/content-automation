from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_role_aware_signin_and_navigation_use_the_routed_studio() -> None:
    index = read("web/static-creator-ui/index.html")
    core = read("web/static-creator-ui/assets/studio-v2.js")
    extensions = read("web/static-creator-ui/assets/studio-v2-extensions.js")

    assert index.index('src="/assets/studio-v2-api.js"') < index.index('src="/assets/studio-v2.js"')
    assert index.index('src="/assets/studio-v2.js"') < index.index('src="/assets/studio-v2-extensions.js"')
    assert 'show: hasRole("producer")' in core
    assert 'show: hasRole("reviewer")' in core
    assert 'show: isAdmin()' in core
    assert 'hasRole("reviewer") && !hasRole("producer")' in core
    assert 'const landing = hasRole("reviewer")' in core
    assert 'if (!nav || !hasRole("publisher")' in extensions
    assert 'if (!hasRole("publisher")) return' in extensions


def test_non_publishers_do_not_call_publisher_delivery_apis_during_signin() -> None:
    core = read("web/static-creator-ui/assets/studio-v2.js")
    extensions = read("web/static-creator-ui/assets/studio-v2-extensions.js")

    assert "StudioApi.deliveries(" not in core
    publisher_guard = extensions.index('if (!hasRole("publisher")) return')
    deliveries_call = extensions.index("window.StudioApi.deliveries()")
    assert publisher_guard < deliveries_call
    assert 'window.location.pathname === "/app/publishing"' in extensions
