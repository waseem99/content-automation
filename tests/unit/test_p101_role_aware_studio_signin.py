from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_non_publisher_signin_skips_publisher_only_delivery_endpoint() -> None:
    index = (ROOT / "web/static-creator-ui/index.html").read_text(encoding="utf-8")
    compat = (ROOT / "web/static-creator-ui/assets/role-aware-api.js").read_text(encoding="utf-8")

    assert 'src="assets/role-aware-api.js"' in index
    assert index.index('src="assets/role-aware-api.js"') < index.index('src="assets/production-console.js"')
    assert 'authenticatedRoles.includes("publisher")' in compat
    assert 'required_role: "publisher"' in compat
    assert "return originalDeliveries(...args);" in compat
    assert "api.access = async" in compat
