"""Local workspace with optional fixture execution and explicit external-server requests."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import platform
import secrets
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from furnace.runtime.lease import WorkspaceLease
from furnace.runtime.manager import RuntimeFault, RuntimeManager
from furnace.runtime.oplog import OperationsLog
from furnace.runtime.scoring import ScoringRule
from furnace.starter import assess_model, write_starter_files
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from furnace_api.documents import extract_document
from furnace_api.everyday import DocumentUpload, EverydayRequest, EverydayService
from furnace_api.studio_evidence import project_view, provenance
from furnace_api.studio_managed import ACTIVE as MANAGED_ACTIVE
from furnace_api.studio_managed import ManagedConsent, ManagedSelection, ManagedService
from furnace_api.studio_model import ConnectionInput, ConsentInput, ModelPrompt, ModelService
from furnace_api.studio_runtime import RuntimeService

ASSETS = Path(__file__).with_name("studio_assets")
EXAMPLE = Path(__file__).with_name("studio_example")
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
    expected_output: str | None = Field(default=None, max_length=8000)
    scoring: ScoringRule | None = None


class Cases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[Case] = Field(max_length=30)
    expected_configuration_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[a-f0-9]+$"
    )


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapter: Literal["framework_fixture"]
    consent: Literal[True]


class PredictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=4000)
    operation: Literal["predict", "error", "timeout", "crash"] = "predict"


class Store:
    def __init__(self, directory: Path):
        self.path = directory / "studio.sqlite3"

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
                project_view(json.loads(row[0]))
                for row in db.execute("SELECT data FROM projects ORDER BY rowid")
            ]

    def get(self, project_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Project not found")
        return project_view(json.loads(row[0]))

    def create(self, value: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT data FROM projects WHERE path=?", (value["path"],)).fetchone()
            if old:
                return project_view(json.loads(old[0]))
            if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] >= 2:
                raise HTTPException(
                    409,
                    "Demo workspace supports two model projects; remove one before adding another",
                )
            db.execute(
                "INSERT INTO projects VALUES (?,?,?)",
                (value["id"], value["path"], json.dumps(value)),
            )
        return project_view(value)

    def change(
        self,
        project_id: str,
        field: str,
        value: Any,
        event: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Project not found")
            project = json.loads(row[0])
            project[field] = value
            project.update(extra or {})
            project["revision"] = project.get("revision", 0) + 1
            project["events"] = (project["events"] + [{"at": now(), "message": event}])[-100:]
            db.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project), project_id))
        return project_view(project)

    def delete(self, project_id: str) -> None:
        with self.connect() as db:
            if db.execute("DELETE FROM projects WHERE id=?", (project_id,)).rowcount == 0:
                raise HTTPException(404, "Project not found")


def inspect_project(path: str) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).resolve(strict=True)
    return resolved, assess_model(resolved)


def now() -> str:
    return datetime.now(UTC).isoformat()


async def payload(request: Request, schema: type[BaseModel], limit: int = MAX_BODY) -> Any:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Request exceeds the allowed body size")
        body.extend(chunk)
    try:
        return schema.model_validate_json(body)
    except (ValidationError, ValueError):
        raise HTTPException(
            422, "Invalid form data; check field lengths, required values and allowed options"
        ) from None


def artifacts_root(workspace: Path) -> Path:
    """Verified weights are shared by content digest; FURNACE_ARTIFACTS relocates them."""
    configured = os.environ.get("FURNACE_ARTIFACTS")
    return Path(configured).expanduser() if configured else workspace / "artifacts"


def create_app(workspace: Path, token: str, artifacts: Path | None = None) -> FastAPI:
    if len(token) < 32:
        raise ValueError("Studio requires a strong local session token")
    store = Store(workspace)
    runtime = RuntimeService(store, RuntimeManager(workspace))
    oplog = OperationsLog(workspace / "logs")
    model = ModelService(store, runtime.manager, oplog)
    managed = ManagedService(
        store, runtime.manager, model, workspace, artifacts or artifacts_root(workspace), oplog
    )

    everyday = EverydayService(managed, model)

    def needs_container_recovery() -> bool:
        pending = MANAGED_ACTIVE | {"preparing", "unknown"}
        return any((p.get("managed_server") or {}).get("status") in pending for p in store.all())

    def startup() -> None:
        # Runs inside the acquired workspace lease: nothing touches storage before it.
        store.initialize()
        runtime.recover()
        model.recover()
        if needs_container_recovery():
            managed.recover()
        oplog.prune(
            {p["id"]: (p.get("plan") or {}).get("log_retention_days", 7) for p in store.all()}
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with WorkspaceLease(workspace):
            await asyncio.to_thread(startup)
            try:
                yield
            finally:
                await asyncio.to_thread(managed.close)
                await asyncio.to_thread(model.recover)
                await asyncio.to_thread(runtime.close)

    app = FastAPI(
        title="Furnace Studio", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.runtime = runtime
    app.state.model = model
    app.state.managed = managed
    app.state.oplog = oplog

    @app.exception_handler(RuntimeFault)
    async def runtime_error(request: Request, exc: RuntimeFault):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={
                "detail": "The project changed after preview. Refresh its saved state, then preview the suite again."
                if exc.code == "configuration_changed_before_case_import"
                else exc.code
                if "/model/" in request.url.path
                or "/managed" in request.url.path
                or request.url.path.startswith("/api/everyday/")
                else "Framework runtime: "
                + exc.code.replace("_", " ")
                + ". No model validation is implied."
            },
        )

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
    def everyday_home():
        return FileResponse(ASSETS / "everyday.html")

    @app.get("/advanced")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.post("/api/everyday/extract")
    async def document_extract(request: Request):
        value = await payload(request, DocumentUpload, 4_010_000)
        return await asyncio.to_thread(extract_document, value.kind, value.data)

    @app.get("/api/everyday/hardware")
    async def everyday_hardware():
        return {"gpu": await asyncio.to_thread(managed.supervisor.gpu)}

    @app.post("/api/everyday/setup")
    def everyday_setup():
        # No download or execution; the user must approve those separate actions.
        for project in store.all():
            if project.get("origin") == "everyday":
                return runtime.status(project["id"])
        path = workspace / "everyday-project"
        path.mkdir(exist_ok=True)
        return store.create(
            {
                "id": uuid.uuid4().hex,
                "name": "Private documents",
                "origin": "everyday",
                "path": str(path),
                "assessment": assess_model(path),
                "contract": None,
                "plan": None,
                "cases": [],
                "runtime": "not_connected",
                "evaluation": None,
                "events": [
                    {
                        "at": now(),
                        "message": "Private-document workspace created; no document content retained",
                    }
                ],
            }
        )

    @app.post("/api/everyday/projects/{project_id}/answer")
    async def everyday_answer(project_id: str, request: Request):
        value = await payload(request, EverydayRequest, 800_000)
        return await asyncio.to_thread(everyday.answer, project_id, value)

    @app.post("/api/everyday/projects/{project_id}/answer-stream")
    async def everyday_answer_stream(project_id: str, request: Request):
        value = await payload(request, EverydayRequest, 800_000)
        stopped = threading.Event()
        loop = asyncio.get_running_loop()
        events: asyncio.Queue = asyncio.Queue()

        def progress(event):
            if stopped.is_set():
                raise RuntimeFault("Document task cancelled")
            loop.call_soon_threadsafe(events.put_nowait, {"progress": event})

        def execute():
            try:
                result = {"result": everyday.answer(project_id, value, progress)}
            except RuntimeFault as error:
                result = {"error": error.code}
            except Exception:
                result = {"error": "Local document task failed; retry after checking the model"}
            if not stopped.is_set():
                loop.call_soon_threadsafe(events.put_nowait, result)

        async def stream():
            task = asyncio.create_task(asyncio.to_thread(execute))
            try:
                while True:
                    event = await events.get()
                    yield json.dumps(event) + "\n"
                    if "result" in event or "error" in event:
                        break
            finally:
                # A sent model request may finish; no further section is sent.
                stopped.set()
                task.cancel()

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.get("/guide")
    def real_evaluation_guide():
        return FileResponse(ASSETS / "real-evaluation.html")

    @app.get("/model")
    def model_workspace():
        return FileResponse(ASSETS / "model.html")

    @app.get("/assets/{name}")
    def asset(
        name: Literal[
            "studio.js",
            "studio.css",
            "studio-state.mjs",
            "model.js",
            "case-import.mjs",
            "favicon.svg",
            "everyday.js",
            "everyday.css",
        ],
    ):
        # Windows registry MIME mappings can label .js/.mjs text/plain. Browsers
        # then refuse the entire module graph; shipped assets have known types.
        media = (
            "image/svg+xml"
            if name.endswith(".svg")
            else "text/css"
            if name.endswith(".css")
            else "text/javascript"
        )
        return FileResponse(ASSETS / name, media_type=media)

    @app.get("/favicon.ico")
    def favicon():
        return RedirectResponse("/assets/favicon.svg")

    @app.get("/healthz")
    def health():
        states = [(p.get("managed_server") or {}).get("status") for p in store.all()]
        return {
            "studio": "ready",
            "managed_servers": {s: states.count(s) for s in sorted({s for s in states if s})},
            "billing": "inactive",
        }

    @app.get("/api/projects")
    def projects():
        return [runtime.status(project["id"]) for project in store.all()]

    @app.get("/api/system")
    def system():
        return {
            "workspace": "available",
            "platform": platform.system(),
            "python": platform.python_version(),
            "runtime": runtime.manager.readiness(),
            "model_compatibility": "not_verified",
            "billing": "inactive",
        }

    @app.post("/api/examples/framework")
    def example():
        # Reopening an example preserves edits/results and never starts a worker.
        for saved in store.all():
            if saved.get("origin") == "guided_example":
                return runtime.status(saved["id"])
        path, assessment = inspect_project(str(EXAMPLE))
        return store.create(
            {
                "id": uuid.uuid4().hex,
                "name": "Infrastructure walkthrough",
                "origin": "guided_example",
                "path": str(path),
                "assessment": assessment,
                "contract": Contract(
                    architecture="Deterministic infrastructure fixture — not a model",
                    task="custom",
                    revision="framework-v1",
                    license="Repository license; no model weights",
                    device="cpu",
                    notes="Returns framework: followed by uppercase input. No learned parameters, user code or weights. Exercises infrastructure only.",
                ).model_dump(),
                "plan": {
                    **Plan(
                        compute="customer", memory_gb=1, timeout_seconds=2, log_retention_days=7
                    ).model_dump(),
                    "subscription_usd_month": 20,
                    "billing": "inactive",
                    "provisioning": "not_started",
                },
                "cases": [
                    {
                        **Case(
                            name="Exact protocol output",
                            input="hello furnace",
                            expected_behavior="The fixture uppercases input; this is not a model-quality test.",
                            expected_output="framework:HELLO FURNACE",
                        ).model_dump(),
                        "status": "not_run",
                    },
                    {
                        **Case(
                            name="An expectation needs a scoring rule",
                            input="explain your reasoning",
                            expected_behavior="A description alone cannot establish correctness. This case must remain unscored.",
                        ).model_dump(),
                        "status": "not_run",
                    },
                ],
                "runtime": "not_connected",
                "evaluation": None,
                "events": [
                    {
                        "at": now(),
                        "message": "Guided infrastructure example created; no model or worker executed",
                    }
                ],
            }
        )

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
                "evaluation": None,
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
        return runtime.status(project_id)

    @app.put("/api/projects/{project_id}/contract")
    async def contract(project_id: str, request: Request):
        value = await payload(request, Contract)
        return await asyncio.to_thread(
            runtime.update,
            project_id,
            "contract",
            value.model_dump(),
            "Model contract saved; runtime compatibility remains unverified",
        )

    @app.put("/api/projects/{project_id}/plan")
    async def plan(project_id: str, request: Request):
        value = await payload(request, Plan)
        return await asyncio.to_thread(
            runtime.update,
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
        return await asyncio.to_thread(
            runtime.update,
            project_id,
            "cases",
            [
                {
                    **case.model_dump(exclude={"scoring"} if case.scoring is None else set()),
                    "status": "not_run",
                }
                for case in value.cases
            ],
            "Evaluation cases saved; no model evaluation has run",
            value.expected_configuration_sha256,
        )

    @app.get("/api/adapters")
    def adapters():
        return [
            {
                "id": "framework_fixture",
                "label": "Infrastructure fixture — not a model",
                "evidence": "framework_only",
                "model_execution": False,
                "requires": "Local Docker and prepared framework image",
                "limits": "256 MiB, 1 CPU, no network; request timeout at most 5 seconds",
            }
        ]

    @app.post("/api/runtime/prepare")
    def prepare_runtime():
        runtime.manager.prepare()
        return {"status": "prepared", "model_execution": False}

    @app.post("/api/projects/{project_id}/start")
    async def start(project_id: str, request: Request):
        store.get(project_id)
        if request.headers.get("content-length", "0") == "0" and not request.headers.get(
            "transfer-encoding"
        ):
            raise HTTPException(
                409,
                "Select the infrastructure fixture explicitly and approve local Docker execution; no model adapter is connected",
            )
        await payload(request, StartInput)
        return await asyncio.to_thread(runtime.start, project_id)

    @app.post("/api/projects/{project_id}/stop")
    def stop(project_id: str):
        return runtime.stop(project_id)

    @app.post("/api/projects/{project_id}/predict")
    async def predict(project_id: str, request: Request):
        value = await payload(request, PredictInput)
        return await asyncio.to_thread(runtime.predict, project_id, value.input, value.operation)

    @app.post("/api/projects/{project_id}/evaluate")
    def evaluate(project_id: str):
        return runtime.evaluate(project_id)

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
                        "runtime": project["runtime"],
                        "evaluation": project.get("evaluation"),
                        "model_endpoint": project["model_endpoint"],
                        "managed_server": managed.view(project_id),
                        "operations": oplog.read(project_id, 200),
                        "provenance": provenance(project),
                        "assessment_sha256": hashlib.sha256(
                            json.dumps(project["assessment"], sort_keys=True).encode()
                        ).hexdigest(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            if (project.get("managed_server") or {}).get("manifest"):
                (folder / "serving-manifest.json").write_text(
                    json.dumps(project["managed_server"]["manifest"], indent=2, sort_keys=True),
                    encoding="utf-8",
                )
            with (folder / "README.md").open("a", encoding="utf-8") as readme:
                readme.write(
                    "\n## Studio evidence\n\nSee workspace-plan.json provenance for the project, configuration and verification status.\nFixture execution checks deterministic output against a saved expected string. There is no measured model baseline or base/head comparison.\nRound-trip timings include Docker control and are not model latency. Fixture evidence supplies no model inference, GPU result or model-quality verification.\nLegacy/unbound records are retained but do not verify the current configuration.\nFor a real-model validation procedure, open /guide in Studio.\n"
                )
                readme.write(
                    "\nIf configured, model_endpoint records separate local-server HTTP observations. Its history retains the last ten attempts in start order, including failures; older attempts expire uniformly. Export before retrying to preserve older copies. History stores hashes and request metadata, not raw prompts/outputs or previous case text. A matching configuration label does not establish readiness or independently attest the declared model/revision; exact output equality is not semantic quality. Non-streaming round-trip duration is not TTFT. Disconnecting Furnace never stops the external server.\n"
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
        model.flag(project_id).set()
        with managed.lock(project_id):
            status = (store.get(project_id).get("managed_server") or {}).get("status")
            if status in MANAGED_ACTIVE | {"preparing", "unknown"}:
                managed.stop(project_id, "Managed server stopped before project removal")
            runtime.remove(project_id)
        return Response(status_code=204)

    @app.get("/api/managed/catalog")
    def managed_catalog():
        return managed.catalog()

    @app.put("/api/projects/{project_id}/managed")
    async def managed_select(project_id: str, request: Request):
        value = await payload(request, ManagedSelection)
        return await asyncio.to_thread(managed.configure, project_id, value)

    @app.get("/api/projects/{project_id}/managed")
    def managed_view(project_id: str):
        return managed.refresh(project_id)

    @app.post("/api/projects/{project_id}/managed/prepare")
    async def managed_prepare(project_id: str, request: Request):
        await payload(request, ManagedConsent)
        return await asyncio.to_thread(managed.prepare, project_id)

    @app.post("/api/projects/{project_id}/managed/cancel")
    def managed_cancel(project_id: str):
        return managed.cancel(project_id)

    @app.post("/api/projects/{project_id}/managed/start")
    async def managed_start(project_id: str, request: Request):
        await payload(request, ManagedConsent)
        return await asyncio.to_thread(managed.start, project_id)

    @app.post("/api/projects/{project_id}/managed/stop")
    def managed_stop(project_id: str):
        return managed.stop(project_id)

    @app.get("/api/projects/{project_id}/managed/observe")
    def managed_observe(project_id: str):
        return managed.observe(project_id)

    @app.post("/api/projects/{project_id}/managed/suite")
    def managed_suite(project_id: str):
        return managed.load_suite(project_id, runtime.update)

    @app.get("/api/projects/{project_id}/operations")
    def operations(project_id: str):
        store.get(project_id)
        return oplog.read(project_id, 200)

    @app.put("/api/projects/{project_id}/model/connection")
    async def model_connection(project_id: str, request: Request):
        value = await payload(request, ConnectionInput)
        return await asyncio.to_thread(
            model.configure, project_id, value.model_dump(), request.url.port
        )

    @app.get("/api/projects/{project_id}/model")
    def saved_model(project_id: str):
        return store.get(project_id)

    @app.post("/api/projects/{project_id}/model/connect")
    async def model_connect(project_id: str, request: Request):
        value = await payload(request, ConsentInput)
        return await asyncio.to_thread(model.connect, project_id, value.consent)

    @app.post("/api/projects/{project_id}/model/disconnect")
    def model_disconnect(project_id: str):
        return model.disconnect(project_id)

    @app.post("/api/projects/{project_id}/model/predict")
    async def model_predict(project_id: str, request: Request):
        value = await payload(request, ModelPrompt)
        return await asyncio.to_thread(model.predict, project_id, value.input)

    @app.post("/api/projects/{project_id}/model/evaluate")
    def model_evaluate(project_id: str):
        return model.evaluate(project_id)

    return app


def launch(
    workspace: Path, port: int, open_browser: bool = True, artifacts: Path | None = None
) -> None:
    import threading
    import webbrowser

    import uvicorn

    if not 1024 <= port <= 65535:
        raise ValueError("Choose a port from 1024 to 65535")
    token = secrets.token_urlsafe(32)
    app = create_app(workspace, token, artifacts)
    url = f"http://127.0.0.1:{port}/#session={token}"
    print(f"Furnace Studio local session: {url}", flush=True)
    print(
        "Demo mode: $20/month offer; no billing or cloud provisioning. Docker is optional; it runs the infrastructure fixture and Furnace-operated local model servers.",
        flush=True,
    )
    # A stalled body/transport must not postpone lifespan cleanup and retain the
    # workspace lease forever. Owned workers are still reconciled by lifespan.
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, access_log=False, timeout_graceful_shutdown=5
        )
    )
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
    except KeyboardInterrupt:
        # Uvicorn may re-raise SIGINT after lifespan cleanup; Ctrl+C is not a crash.
        if not server.started:
            raise SystemExit(130) from None
    finally:
        done.set()
    if not server.started:
        raise SystemExit("Studio could not start; check the application errors above")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="furnace-studio")
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".furnace" / "studio")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--artifacts", type=Path, default=None)
    args = parser.parse_args()
    launch(args.workspace, args.port, open_browser=not args.no_browser, artifacts=args.artifacts)
