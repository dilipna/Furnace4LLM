"""Local researcher workspace. No model execution, cloud provisioning or billing."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import secrets
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from furnace.starter import assess_model, write_starter_files
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

ASSETS = Path(__file__).with_name("studio_assets")
MAX_BODY = 65536


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    path: str = Field(min_length=1, max_length=2048)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    architecture: str = Field(default="", max_length=120)
    task: Literal["text_generation", "classification", "embeddings", "custom"] = "custom"
    revision: str = Field(default="", max_length=120)
    license: str = Field(default="", max_length=120)
    device: Literal["not_decided", "cpu", "gpu"] = "not_decided"
    notes: str = Field(default="", max_length=2000)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compute: Literal["furnace", "customer"]
    memory_gb: int = Field(ge=1, le=1024)
    timeout_seconds: int = Field(ge=1, le=3600)
    log_retention_days: int = Field(ge=1, le=365)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    input: str = Field(min_length=1, max_length=4000)
    expected_behavior: str = Field(min_length=1, max_length=4000)


class Cases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[Case] = Field(max_length=30)


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "studio.sqlite3"
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, path TEXT UNIQUE, data TEXT NOT NULL)"
            )
        self.path.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def all(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [
                json.loads(row[0]) for row in db.execute("SELECT data FROM projects ORDER BY rowid")
            ]

    def get(self, project_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Project not found")
        return json.loads(row[0])

    def create(self, value: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT data FROM projects WHERE path=?", (value["path"],)).fetchone()
            if old:
                return json.loads(old[0])
            if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] >= 2:
                raise HTTPException(
                    409,
                    "Demo workspace supports two model projects; remove one before adding another",
                )
            db.execute(
                "INSERT INTO projects VALUES (?,?,?)",
                (value["id"], value["path"], json.dumps(value)),
            )
        return value

    def change(self, project_id: str, field: str, value: Any, event: str) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Project not found")
            project = json.loads(row[0])
            project[field] = value
            project["events"] = (project["events"] + [{"at": now(), "message": event}])[-100:]
            db.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project), project_id))
        return project

    def delete(self, project_id: str) -> None:
        with self.connect() as db:
            if db.execute("DELETE FROM projects WHERE id=?", (project_id,)).rowcount == 0:
                raise HTTPException(404, "Project not found")


def inspect_project(path: str) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).resolve(strict=True)
    return resolved, assess_model(resolved)


def now() -> str:
    return datetime.now(UTC).isoformat()


async def payload(request: Request, schema: type[BaseModel]) -> Any:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "Request exceeds 64 KiB")
        body.extend(chunk)
    try:
        return schema.model_validate_json(body)
    except (ValidationError, ValueError):
        raise HTTPException(
            422, "Invalid form data; check field lengths, required values and allowed options"
        ) from None


def create_app(workspace: Path, token: str) -> FastAPI:
    if len(token) < 32:
        raise ValueError("Studio requires a strong local session token")
    store = Store(workspace)
    app = FastAPI(title="Furnace Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.url.netloc}"
            if origin and origin != expected:
                return Response("Cross-origin requests are refused", status_code=403)
            supplied = request.headers.get("x-furnace-session", "")
            if not secrets.compare_digest(supplied.encode(), token.encode()):
                return Response(
                    "Open Studio using the session link printed by the launcher", status_code=401
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/assets/{name}")
    def asset(name: Literal["studio.js", "studio.css"]):
        return FileResponse(ASSETS / name)

    @app.get("/healthz")
    def health():
        return {"studio": "ready", "model_runtime": "not_connected", "billing": "inactive"}

    @app.get("/api/projects")
    def projects():
        return store.all()

    @app.post("/api/projects", status_code=201)
    async def add_project(request: Request):
        value = await payload(request, ProjectInput)
        try:
            path, assessment = await asyncio.to_thread(inspect_project, value.path)
        except (OSError, ValueError):
            raise HTTPException(
                422, "Cannot inspect that folder. Check access and the 5,000-entry inventory limit"
            ) from None
        return store.create(
            {
                "id": uuid.uuid4().hex,
                "name": value.name.strip() or "Untitled model",
                "path": str(path),
                "assessment": assessment,
                "contract": Contract().model_dump(),
                "plan": None,
                "cases": [],
                "runtime": "not_connected",
                "events": [
                    {
                        "at": now(),
                        "message": "Local files inspected; model code and weights were not executed",
                    }
                ],
            }
        )

    @app.get("/api/projects/{project_id}")
    def project(project_id: str):
        return store.get(project_id)

    @app.put("/api/projects/{project_id}/contract")
    async def contract(project_id: str, request: Request):
        value = await payload(request, Contract)
        return store.change(
            project_id,
            "contract",
            value.model_dump(),
            "Model contract saved; runtime compatibility remains unverified",
        )

    @app.put("/api/projects/{project_id}/plan")
    async def plan(project_id: str, request: Request):
        value = await payload(request, Plan)
        return store.change(
            project_id,
            "plan",
            {
                **value.model_dump(),
                "subscription_usd_month": 20,
                "billing": "inactive",
                "provisioning": "not_started",
            },
            "Infrastructure preferences saved; no server provisioned and no payment taken",
        )

    @app.put("/api/projects/{project_id}/cases")
    async def cases(project_id: str, request: Request):
        value = await payload(request, Cases)
        return store.change(
            project_id,
            "cases",
            [{**case.model_dump(), "status": "not_run"} for case in value.cases],
            "Evaluation cases saved; no model evaluation has run",
        )

    @app.post("/api/projects/{project_id}/start")
    def start(project_id: str):
        store.get(project_id)
        raise HTTPException(
            409,
            "Model runtime is not connected. A validated adapter and model acceptance test are required; no server was started",
        )

    @app.post("/api/projects/{project_id}/kit")
    def kit(project_id: str):
        project = store.get(project_id)
        # Render from the saved assessment, never silently inspect changed source at export.
        with tempfile.TemporaryDirectory(prefix="furnace-kit-") as td:
            folder = Path(td) / "kit"
            write_starter_files(project["assessment"], folder)
            (folder / "model-contract.json").write_text(
                json.dumps(project["contract"], indent=2), encoding="utf-8"
            )
            if project["cases"]:
                (folder / "evaluation-cases.example.jsonl").write_text(
                    "\n".join(json.dumps(c) for c in project["cases"]) + "\n", encoding="utf-8"
                )
            (folder / "workspace-plan.json").write_text(
                json.dumps(
                    {
                        "plan": project["plan"],
                        "runtime": "not_connected",
                        "assessment_sha256": hashlib.sha256(
                            json.dumps(project["assessment"], sort_keys=True).encode()
                        ).hexdigest(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(folder.iterdir()):
                    archive.write(file, file.name)
        return Response(
            data.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="furnace-starter-kit.zip"'},
        )

    @app.delete("/api/projects/{project_id}", status_code=204)
    def remove(project_id: str):
        store.delete(project_id)
        return Response(status_code=204)

    return app


def launch(workspace: Path, port: int, open_browser: bool = True) -> None:
    import threading
    import webbrowser

    import uvicorn

    if not 1024 <= port <= 65535:
        raise ValueError("Choose a port from 1024 to 65535")
    token = secrets.token_urlsafe(32)
    app = create_app(workspace, token)
    url = f"http://127.0.0.1:{port}/#session={token}"
    print(f"Furnace Studio local session: {url}", flush=True)
    print(
        "Demo mode: $20/month offer; no billing, provisioning or model execution enabled.",
        flush=True,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False))
    done = threading.Event()

    def open_when_ready() -> None:
        for _ in range(200):
            if done.wait(0.05):
                return
            if server.started:
                webbrowser.open(url)
                return

    if open_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        server.run()
    finally:
        done.set()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="furnace-studio")
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".furnace" / "studio")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    launch(args.workspace, args.port, open_browser=not args.no_browser)
