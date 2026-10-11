"""Create the Furnace GitHub App from a manifest (`furnace gh-setup`).

GitHub's App-manifest flow: a local page POSTs the manifest below to github.com, the user
reviews it and clicks "Create GitHub App", GitHub redirects back to this machine with a
one-time code, and the code is exchanged (POST /app-manifests/{code}/conversions) for the
App id, its private key and its webhook secret. The permission set is therefore defined
here, in code, not typed by hand into a settings form.

Least privilege: Contents read/write (read revisions; write only the commits of draft
PRs, never to a default branch), Pull requests read/write (read PRs; open draft PRs),
Checks read/write (Guard's check run), Metadata read (mandatory). One event:
pull_request. No account or organization permissions. Private (installable only on the
owner's account).

The callback listens on 127.0.0.1 only and checks a random `state` (so another page cannot
complete the flow with its own code). The private key is written to a file outside the
repository with owner-only permissions; secrets are never printed.
"""

from __future__ import annotations

import html
import json
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from furnace.github.client import API, HEADERS, GitHubError

APP_PERMISSIONS = {
    "contents": "write",
    "pull_requests": "write",
    "checks": "write",
    "metadata": "read",
}
APP_EVENTS = ["pull_request"]


def manifest(*, name: str, homepage: str, webhook_url: str, redirect_url: str) -> dict[str, Any]:
    return {
        "name": name,
        "url": homepage,
        "hook_attributes": {"url": webhook_url, "active": True},
        "redirect_url": redirect_url,
        "public": False,
        "default_permissions": dict(APP_PERMISSIONS),
        "default_events": list(APP_EVENTS),
        "description": "Furnace: inference-reliability checks and draft repair PRs (human merges).",
    }


def create_url(state: str, org: str | None = None) -> str:
    base = (
        f"https://github.com/organizations/{org}/settings/apps/new"
        if org
        else "https://github.com/settings/apps/new"
    )
    return f"{base}?state={state}"


def form_page(manifest_json: str, action: str) -> str:
    """Auto-submitting form (GitHub requires the manifest as a POSTed form field)."""
    return (
        "<!doctype html><meta charset=utf-8><title>Create the Furnace GitHub App</title>"
        "<body style='font-family:system-ui;max-width:40rem;margin:3rem auto'>"
        "<h1>Create the Furnace GitHub App</h1>"
        "<p>GitHub will show the permissions below for you to review before creating it.</p>"
        f"<pre>{html.escape(json.dumps(json.loads(manifest_json), indent=2))}</pre>"
        f"<form id=f method=post action='{html.escape(action, quote=True)}'>"
        f"<input type=hidden name=manifest value='{html.escape(manifest_json, quote=True)}'>"
        "<button type=submit>Continue to GitHub</button></form>"
        "<script>document.getElementById('f').submit()</script>"
    )


@dataclass
class CreatedApp:
    app_id: str
    slug: str
    html_url: str
    pem: str
    webhook_secret: str | None


async def convert(code: str, transport: httpx.AsyncBaseTransport | None = None) -> CreatedApp:
    """Exchange the one-time manifest code (valid one hour) for the App's credentials."""
    async with httpx.AsyncClient(
        base_url=API, headers=HEADERS, transport=transport, timeout=30
    ) as c:
        r = await c.post(f"/app-manifests/{code}/conversions")
    if r.status_code != 201:
        raise GitHubError(f"manifest conversion failed: {r.status_code} {r.text[:200]}")
    d = r.json()
    return CreatedApp(
        app_id=str(d["id"]),
        slug=d["slug"],
        html_url=d["html_url"],
        pem=d["pem"],
        webhook_secret=d.get("webhook_secret"),
    )


def write_credentials(app: CreatedApp, key_dir: Path, env_file: Path) -> Path:
    """Private key to `key_dir/<slug>.pem` (owner-only), ids and secret into `env_file`."""
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / f"{app.slug}.pem"
    key_path.write_text(app.pem, encoding="utf-8")
    key_path.chmod(0o600)
    values = {
        "FURNACE_GITHUB_APP_ID": app.app_id,
        "FURNACE_GITHUB_PRIVATE_KEY_PATH": key_path.resolve().as_posix(),
    }
    if app.webhook_secret:
        values["FURNACE_GITHUB_WEBHOOK_SECRET"] = app.webhook_secret
    update_env_file(env_file, values)
    return key_path


def update_env_file(path: Path, values: dict[str, str]) -> None:
    """Set keys in a dotenv file, keeping every other line as it was."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    path.chmod(0o600)


def wait_for_code(page: str, state: str, port: int, timeout_s: float = 900) -> str:
    """Serve the form at http://127.0.0.1:<port>/ and return the code GitHub redirects back
    with to /callback (after checking `state`)."""
    result: dict[str, str] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # keep the code out of the terminal
            pass

        def _send(self, status: int, body: str) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(200, page)
            if u.path != "/callback":
                return self._send(404, "not found")
            q = parse_qs(u.query)
            if q.get("state", [""])[0] != state or not q.get("code"):
                return self._send(400, "state mismatch or no code: start again with gh-setup")
            result["code"] = q["code"][0]
            self._send(200, "<p>Furnace received the App. You can close this tab.</p>")
            done.set()

    server = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        if not done.wait(timeout_s):
            raise GitHubError("timed out waiting for GitHub to redirect back")
    finally:
        server.shutdown()
    return result["code"]


def discard_sink() -> str:
    """A fresh smee.io channel URL (GitHub's documented webhook relay for local
    development) used only as a place GitHub can deliver to, so the App's delivery log
    fills; `furnace gh-poll` reads that log over the authenticated API instead."""
    r = httpx.get("https://smee.io/new", follow_redirects=False, timeout=15)
    loc = r.headers.get("location", "")
    if not loc.startswith("https://smee.io/"):
        raise GitHubError("could not create a smee.io channel; pass --webhook-url")
    return loc


def run_setup(
    *,
    name: str,
    webhook_url: str | None,
    org: str | None,
    port: int,
    key_dir: Path,
    env_file: Path,
    open_browser: bool = True,
) -> dict[str, Any]:
    import asyncio

    state = secrets.token_urlsafe(24)
    hook = webhook_url or discard_sink()
    m = manifest(
        name=name,
        homepage="https://github.com/dilipna/Furnace4LLM",
        webhook_url=hook,
        redirect_url=f"http://127.0.0.1:{port}/callback",
    )
    page = form_page(json.dumps(m), create_url(state, org))
    local = f"http://127.0.0.1:{port}/"
    print(f"Open {local} (opening it now) and click 'Create GitHub App' on GitHub.", flush=True)
    if open_browser:
        webbrowser.open(local)
    code = wait_for_code(page, state, port)
    app = asyncio.run(convert(code))
    key_path = write_credentials(app, key_dir, env_file)
    return {
        "app_id": app.app_id,
        "slug": app.slug,
        "private_key": str(key_path),
        "env_file": str(env_file.resolve()),
        "webhook_url": hook,
        "webhook_secret_written": bool(app.webhook_secret),
        "next": f"install it on your demo repository: {app.html_url}/installations/new",
    }
