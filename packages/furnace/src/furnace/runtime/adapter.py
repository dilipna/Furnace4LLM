"""Adapter contract: how an architecture supplies loading and inference to Furnace.

Furnace owns the operational envelope (verified artifacts, isolated container,
network policy, readiness, logs, metrics, stop and recovery). An adapter owns only
what is specific to a model: which files and image it needs and how its server is
launched. Every adapter's server speaks PROTOCOL on its container port:

  GET  /health                 200 {"status": "ok"} once loaded; 503 while loading
  GET  /v1/models              {"data": [{"id": <model_id>}]}
  POST /v1/chat/completions    one text user message, stream false, temperature 0,
                               max_tokens; requires "Authorization: Bearer <key>"
                               when a per-launch key is supplied in `secret_env`
  GET  /metrics                optional Prometheus text

Two adapters ship: an engine adapter for GGUF models served by llama.cpp, and a
Python adapter that hosts a researcher's own `load`/`generate` implementation
(see pyserve.py) for architectures no engine supports.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from furnace.runtime.catalog import (
    ENGINES,
    MODELS,
    RELAY_IMAGE,
    Accelerator,
    Artifact,
    ModelRecipe,
    manifest,
)

PROTOCOL = "furnace-chat-v1"
PYSERVE = Path(__file__).with_name("pyserve.py")
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/:-]*@sha256:[a-f0-9]{64}$")


@dataclass(frozen=True)
class Mount:
    source: Path
    target: str


@dataclass(frozen=True)
class LaunchSettings:
    accelerator: Accelerator = "cpu"
    context_tokens: int = 4096
    threads: int = 4
    memory_mb: int = 2048
    cpus: float = 4.0
    max_output_tokens: int = 1024

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaunchSpec:
    """Everything the supervisor needs; it never interprets model-specific flags."""

    image: str
    command: tuple[str, ...]
    mounts: tuple[Mount, ...]
    model_id: str
    entrypoint: str | None = None
    internal_port: int = 8080
    health_path: str = "/health"
    gpu: bool = False
    secret_env: str = "FURNACE_API_KEY"  # noqa: S105 -- variable name, not a secret
    memory_mb: int = 2048
    cpus: float = 2.0
    pids: int = 256
    tmpfs_mb: int = 64
    load_timeout_s: float = 180.0
    labels: dict[str, str] = field(default_factory=dict)


class ServingAdapter(Protocol):
    kind: str

    def artifacts(self) -> list[Artifact]: ...

    def images(self, settings: LaunchSettings) -> list[str]: ...

    def launch(self, files: dict[str, Path], settings: LaunchSettings) -> LaunchSpec: ...

    def manifest(self, settings: LaunchSettings) -> dict[str, Any]: ...


class LlamaCppAdapter:
    """Serve one pinned GGUF file with a pinned llama.cpp server image."""

    kind = "llama.cpp"

    def __init__(self, recipe: ModelRecipe):
        self.recipe = recipe
        self.engine = ENGINES[recipe.engine]

    @classmethod
    def for_model(cls, model_id: str) -> LlamaCppAdapter:
        return cls(MODELS[model_id])

    def artifacts(self) -> list[Artifact]:
        return [self.recipe.weights]

    def images(self, settings: LaunchSettings) -> list[str]:
        return [self.engine.images[settings.accelerator], RELAY_IMAGE]

    def manifest(self, settings: LaunchSettings) -> dict[str, Any]:
        return manifest(self.recipe.id, settings.accelerator, settings.as_dict())

    def launch(self, files: dict[str, Path], settings: LaunchSettings) -> LaunchSpec:
        weights = files[self.recipe.weights.sha256]
        gpu = settings.accelerator == "nvidia"
        command = (
            "--model", "/models/model.gguf",
            "--host", "0.0.0.0",  # noqa: S104 -- container interface on an internal network only
            "--port", "8080",
            "--alias", self.recipe.alias,
            "--ctx-size", str(settings.context_tokens),
            "--parallel", "1",
            "--threads", str(settings.threads),
            "--n-gpu-layers", "999" if gpu else "0",
            "--n-predict", str(settings.max_output_tokens),
            "--timeout", "600",
            "--metrics",
            "--no-webui",
            "--offline",
        )  # fmt: skip
        return LaunchSpec(
            image=self.engine.images[settings.accelerator],
            command=command,
            mounts=(Mount(weights, "/models/model.gguf"),),
            model_id=self.recipe.alias,
            gpu=gpu,
            secret_env="LLAMA_API_KEY",  # noqa: S106 -- variable name, not a secret
            memory_mb=settings.memory_mb,
            cpus=settings.cpus,
            load_timeout_s=180.0,
        )


class PythonAdapter:
    """Host a researcher's own loading/inference code behind the same protocol.

    The researcher supplies an image (pinned by digest) holding their dependencies,
    a code directory mounted read-only, and `module:factory` returning an object with
    `load(weights_dir)` and `generate(messages, max_tokens, temperature)`; an optional
    `reset()` clears recurrent/session state before every request.
    """

    kind = "python"

    def __init__(
        self,
        image: str,
        code: Path,
        entrypoint: str,
        model_id: str,
        weights: Path | None = None,
        load_timeout_s: float = 300.0,
    ):
        if not _IMAGE.fullmatch(image):
            raise ValueError("pin the adapter image by digest (name@sha256:...)")
        if not re.fullmatch(r"[A-Za-z_][\w.]*:[A-Za-z_]\w*", entrypoint):
            raise ValueError("entrypoint must look like package.module:factory")
        self.image, self.code, self.entrypoint = image, code.resolve(), entrypoint
        self.model_id, self.weights, self.load_timeout_s = model_id, weights, load_timeout_s

    def artifacts(self) -> list[Artifact]:
        return []

    def images(self, settings: LaunchSettings) -> list[str]:
        return [self.image, RELAY_IMAGE]

    def manifest(self, settings: LaunchSettings) -> dict[str, Any]:
        return {
            "schema": "furnace-serving-manifest-v1",
            "adapter": {"kind": self.kind, "image": self.image, "entrypoint": self.entrypoint},
            "model": {"alias": self.model_id},
            "relay_image": RELAY_IMAGE,
            "settings": dict(sorted(settings.as_dict().items())),
        }

    def launch(self, files: dict[str, Path], settings: LaunchSettings) -> LaunchSpec:
        mounts = [Mount(PYSERVE.resolve(), "/furnace/pyserve.py"), Mount(self.code, "/adapter")]
        command = [
            "-I", "/furnace/pyserve.py",
            "--adapter", self.entrypoint,
            "--code", "/adapter",
            "--model-id", self.model_id,
            "--port", "8080",
            "--max-tokens", str(settings.max_output_tokens),
        ]  # fmt: skip
        if self.weights is not None:
            mounts.append(Mount(self.weights.resolve(), "/weights"))
            command += ["--weights", "/weights"]
        return LaunchSpec(
            image=self.image,
            command=tuple(command),
            mounts=tuple(mounts),
            model_id=self.model_id,
            entrypoint="python",
            gpu=settings.accelerator == "nvidia",
            secret_env="FURNACE_API_KEY",  # noqa: S106 -- variable name, not a secret
            memory_mb=settings.memory_mb,
            cpus=settings.cpus,
            load_timeout_s=self.load_timeout_s,
        )
