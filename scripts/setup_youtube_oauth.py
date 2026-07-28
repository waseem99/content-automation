from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "ContentAutomationOAuth/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        query = parse_qs(urlparse(self.path).query)
        self.server.oauth_query = query  # type: ignore[attr-defined]
        body = (
            "<html><body><h1>YouTube authorization received</h1>"
            "<p>You may close this window and return to PowerShell.</p></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def _load_client(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    client = raw.get("installed") or raw.get("web")
    if not isinstance(client, dict):
        raise ValueError("Google OAuth client JSON must contain an installed or web client")
    required = ("client_id", "client_secret", "auth_uri", "token_uri")
    values = {key: str(client.get(key) or "").strip() for key in required}
    if any(not values[key] for key in required):
        raise ValueError("Google OAuth client JSON is missing required client fields")
    return values


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _exchange(
    *,
    token_uri: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    verifier: str,
) -> dict:
    payload = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    ).encode("utf-8")
    request = Request(
        token_uri,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Google OAuth token exchange failed with HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Google OAuth token exchange failed") from exc


def authorize(client_json: Path, output: Path, timeout_seconds: int) -> None:
    client = _load_client(client_json)
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    server = ThreadingHTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
    server.oauth_query = None  # type: ignore[attr-defined]
    redirect_uri = f"http://127.0.0.1:{server.server_port}/oauth/callback"
    authorization_url = f"{client['auth_uri']}?{urlencode({
        'client_id': client['client_id'],
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'include_granted_scopes': 'true',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("Opening the official Google authorization page...")
    print("Authorize only the intended YouTube channel account.")
    webbrowser.open(authorization_url, new=1, autoraise=True)

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline and server.oauth_query is None:  # type: ignore[attr-defined]
            time.sleep(0.25)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    query = server.oauth_query  # type: ignore[attr-defined]
    if not query:
        raise TimeoutError("Google OAuth authorization timed out")
    if query.get("state", [""])[0] != state:
        raise RuntimeError("Google OAuth callback state did not match")
    if query.get("error"):
        raise RuntimeError(f"Google OAuth authorization was denied: {query['error'][0]}")
    code = query.get("code", [""])[0]
    if not code:
        raise RuntimeError("Google OAuth callback did not contain an authorization code")

    tokens = _exchange(
        token_uri=client["token_uri"],
        client_id=client["client_id"],
        client_secret=client["client_secret"],
        code=code,
        redirect_uri=redirect_uri,
        verifier=verifier,
    )
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if not refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke the prior app grant and authorize again with consent."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    credential = {
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": refresh_token,
        "token_uri": client["token_uri"],
        "scopes": list(SCOPES),
    }
    output.write_text(json.dumps(credential, indent=2), encoding="utf-8")
    print(f"YouTube OAuth credential saved outside Git at: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize the official YouTube delivery account")
    parser.add_argument("--client-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    authorize(
        args.client_json.expanduser().resolve(strict=True),
        args.output.expanduser().resolve(),
        max(60, args.timeout_seconds),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
