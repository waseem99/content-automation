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

    sign_in = core.split("async function authenticateSavedSession", 1)[1].split(
        "function showLogin", 1
    )[0]
    assert "StudioApi.deliveries(" not in sign_in

    operations = core.split("async function renderOperations", 1)[1].split(
        "function renderNotFound", 1
    )[0]
    admin_guard = operations.index('if (!isAdmin()) return navigate("/app/dashboard"')
    admin_delivery_call = operations.index("StudioApi.deliveries()")
    assert admin_guard < admin_delivery_call

    publisher_guard = extensions.index('if (!hasRole("publisher")) return')
    publisher_delivery_call = extensions.index("window.StudioApi.deliveries()")
    assert publisher_guard < publisher_delivery_call
    assert 'window.location.pathname === "/app/publishing"' in extensions
