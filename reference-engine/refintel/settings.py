from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FACEBOOK_PROFILE = Path.home() / ".local" / "share" / "refintel" / "facebook-browser"


def _optional_path(value: str | None) -> Path | None:
    if not value or not value.strip():
        return None
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class RefIntelSettings:
    """Non-secret runtime configuration and paths to operator-owned secret files.

    Cookie contents and account credentials are intentionally not accepted here. A caller may
    point at a local cookie jar or persistent browser profile without serializing either path into
    analysis artifacts.
    """

    workspace: Path
    facebook_profile: Path
    facebook_cookie_file: Path | None
    cookies_from_browser: str | None
    use_ollama: bool
    ollama_model: str
    ollama_endpoint: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RefIntelSettings:
        values = os.environ if environ is None else environ
        cookie_file = _optional_path(values.get("REFINTEL_FACEBOOK_COOKIE_FILE"))
        browser = values.get("REFINTEL_COOKIES_FROM_BROWSER") or None
        return cls(
            workspace=_optional_path(values.get("REFINTEL_WORKSPACE"))
            or Path("workspace").resolve(),
            facebook_profile=_optional_path(values.get("REFINTEL_FACEBOOK_PROFILE"))
            or DEFAULT_FACEBOOK_PROFILE.resolve(),
            facebook_cookie_file=cookie_file,
            cookies_from_browser=browser.strip().lower() if browser else None,
            use_ollama=values.get("REFINTEL_USE_OLLAMA", "0").strip() == "1",
            ollama_model=values.get("REFINTEL_OLLAMA_MODEL", "qwen2.5vl:7b").strip(),
            ollama_endpoint=values.get(
                "REFINTEL_OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat"
            ).strip(),
        )

    def validate_local_auth(self) -> None:
        if self.cookies_from_browser and self.facebook_cookie_file:
            raise ValueError(
                "Set either REFINTEL_COOKIES_FROM_BROWSER or "
                "REFINTEL_FACEBOOK_COOKIE_FILE, not both"
            )
        if self.facebook_cookie_file and not self.facebook_cookie_file.is_file():
            raise FileNotFoundError(self.facebook_cookie_file)


ENVIRONMENT_VARIABLES = {
    "REFINTEL_WORKSPACE": "Local reference workspace root; never a Vercel media directory.",
    "REFINTEL_FACEBOOK_PROFILE": "Path to the operator-owned Playwright profile.",
    "REFINTEL_FACEBOOK_COOKIE_FILE": "Path to a local Netscape cookie jar, not its contents.",
    "REFINTEL_COOKIES_FROM_BROWSER": "Optional supported local browser name.",
    "REFINTEL_USE_OLLAMA": "Set to 1 to enable local visual observations.",
    "REFINTEL_OLLAMA_MODEL": "Local Ollama vision model name.",
    "REFINTEL_OLLAMA_ENDPOINT": "Loopback Ollama chat endpoint.",
}
