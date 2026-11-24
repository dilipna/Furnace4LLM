"""Reviewed, pinned serving recipes. Nothing here is fetched or executed on import.

A recipe pins every input that decides what runs: the engine container image by
content digest, the weights file by SHA-256 and size at a fixed upstream revision,
the launch flags and the reference suite. Its canonical digest is the durable
version record that evaluation runs cite. Validation status is evidence recorded
in the repository, never inferred from a recipe existing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from importlib import resources
from typing import Any, Literal

Accelerator = Literal["cpu", "nvidia"]


@dataclass(frozen=True)
class Artifact:
    """One file fetched over HTTPS and accepted only if its size and SHA-256 match."""

    url: str
    sha256: str
    size: int
    filename: str


@dataclass(frozen=True)
class Engine:
    id: str
    name: str
    version: str
    source_commit: str
    license: str
    images: dict[str, str]  # accelerator -> image@sha256 (multi-arch index digest)
    source: str


@dataclass(frozen=True)
class ModelRecipe:
    id: str
    name: str
    architecture: str
    family_note: str
    parameters: str
    license: str
    repository: str
    revision: str
    weights: Artifact
    alias: str
    context_tokens: int
    engine: str
    suite: str
    hardware: str
    validation: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Suite:
    id: str
    filename: str
    sha256: str
    description: str


RELAY_IMAGE = "alpine/socat@sha256:7f9a06753033f2b7de18edc2353f2c15153413d95a039163c6db270fc7a6c3b0"

LLAMA_CPP = Engine(
    id="llama.cpp-b12004",
    name="llama.cpp server",
    version="b12004",
    source_commit="3c809f44383bcebc318b8cddd8c6d11aaa861e9b",
    license="MIT",
    images={
        "cpu": "ghcr.io/ggml-org/llama.cpp@sha256:b32890309c1a33a534a01b0b461e953dc2c5a6bac20213abcf48e22847a19c85",
        "nvidia": "ghcr.io/ggml-org/llama.cpp@sha256:f25bfa096802cdf35ceb7d124816387a1e3ed5cbfc869eb242246cd29ab29352",
    },
    source="https://github.com/ggml-org/llama.cpp/releases/tag/b12004",
)

ENGINES = {LLAMA_CPP.id: LLAMA_CPP}

SUITES = {
    "general-tasks-v1": Suite(
        id="general-tasks-v1",
        filename="general-tasks-v1.jsonl",
        sha256="0a7c418b5b8a954c398b8880db8fb4714139f5635d49a9b254f36a6adfdddf25",
        description="Twelve short task checks (arithmetic, facts, choices, formats). "
        "Scored by rule; small models are expected to miss some.",
    ),
}

MODELS = {
    recipe.id: recipe
    for recipe in (
        ModelRecipe(
            id="qwen2.5-1.5b-instruct-q4_k_m",
            name="Qwen2.5 1.5B Instruct (Q4_K_M GGUF)",
            architecture="qwen2 (decoder-only transformer)",
            family_note="Everyday document candidate. Quality and latency are measured separately from privacy checks.",
            parameters="1.54B",
            license="apache-2.0",
            repository="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
            revision="91cad51170dc346986eccefdc2dd33a9da36ead9",
            weights=Artifact(
                url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/"
                "91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                sha256="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
                size=1117320736,
                filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
            ),
            alias="qwen2.5-1.5b-instruct-q4_k_m",
            context_tokens=4096,
            engine=LLAMA_CPP.id,
            suite="general-tasks-v1",
            hardware="Candidate for CPU with 8 GiB Docker memory and a 4 GiB NVIDIA GPU; see recorded validation, not a universal fit guarantee.",
        ),
        ModelRecipe(
            id="qwen2.5-0.5b-instruct-q8_0",
            name="Qwen2.5 0.5B Instruct (Q8_0 GGUF)",
            architecture="qwen2 (decoder-only transformer)",
            family_note="Dense attention transformer; the repository's earlier vLLM runs used this model.",
            parameters="0.49B",
            license="apache-2.0",
            repository="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
            revision="9217f5db79a29953eb74d5343926648285ec7e67",
            weights=Artifact(
                url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/"
                "9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q8_0.gguf",
                sha256="ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e",
                size=675710816,
                filename="qwen2.5-0.5b-instruct-q8_0.gguf",
            ),
            alias="qwen2.5-0.5b-instruct-q8_0",
            context_tokens=4096,
            engine=LLAMA_CPP.id,
            suite="general-tasks-v1",
            hardware="About 1 GiB of container memory on CPU; fits a 4 GiB GPU.",
        ),
        ModelRecipe(
            id="granite-4.0-h-350m-q8_0",
            name="IBM Granite 4.0 H 350M (Q8_0 GGUF)",
            architecture="granitehybrid (Mamba-2 state-space layers with some attention)",
            family_note="Hybrid state-space architecture: most layers keep recurrent state "
            "instead of a growing KV cache, so per-request state isolation matters.",
            parameters="0.35B",
            license="apache-2.0",
            repository="ibm-granite/granite-4.0-h-350m-GGUF",
            revision="a864f823cce6e6048b5752e2816fe7a23987d790",
            weights=Artifact(
                url="https://huggingface.co/ibm-granite/granite-4.0-h-350m-GGUF/resolve/"
                "a864f823cce6e6048b5752e2816fe7a23987d790/granite-4.0-h-350m-Q8_0.gguf",
                sha256="c7d9873640dc303b6773dcc44e72e5bdf533e1c95ca8421e6191fbff5c94c942",
                size=366195616,
                filename="granite-4.0-h-350m-Q8_0.gguf",
            ),
            alias="granite-4.0-h-350m-q8_0",
            context_tokens=4096,
            engine=LLAMA_CPP.id,
            suite="general-tasks-v1",
            hardware="About 1 GiB of container memory on CPU; fits a 4 GiB GPU.",
        ),
    )
}


class CatalogError(Exception):
    pass


def suite_bytes(suite_id: str) -> bytes:
    suite = SUITES[suite_id]
    data = resources.files("furnace.runtime").joinpath("suites", suite.filename).read_bytes()
    # A changed reference file must be a new suite version, never the same identity.
    if hashlib.sha256(data).hexdigest() != suite.sha256:
        raise CatalogError(f"reference suite {suite_id} does not match its pinned digest")
    return data


def suite_digest(suite_id: str) -> str:
    return hashlib.sha256(suite_bytes(suite_id)).hexdigest()


def suite_cases(suite_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in suite_bytes(suite_id).decode("utf-8").splitlines() if line]


def manifest(model_id: str, accelerator: Accelerator, settings: dict[str, Any]) -> dict[str, Any]:
    """Everything that decides what a launch runs, in canonical form."""
    recipe = MODELS[model_id]
    engine = ENGINES[recipe.engine]
    return {
        "schema": "furnace-serving-manifest-v1",
        "model": {
            "id": recipe.id,
            "repository": recipe.repository,
            "revision": recipe.revision,
            "weights_sha256": recipe.weights.sha256,
            "weights_size": recipe.weights.size,
            "alias": recipe.alias,
            "architecture": recipe.architecture,
            "license": recipe.license,
        },
        "engine": {
            "id": engine.id,
            "version": engine.version,
            "source_commit": engine.source_commit,
            "image": engine.images[accelerator],
            "accelerator": accelerator,
        },
        "relay_image": RELAY_IMAGE,
        "settings": dict(sorted(settings.items())),
        "suite": {"id": recipe.suite, "sha256": suite_digest(recipe.suite)},
    }


def manifest_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def public_catalog() -> dict[str, Any]:
    return {
        "engines": [asdict(engine) for engine in ENGINES.values()],
        "models": [
            {
                **asdict(recipe),
                "download_bytes": recipe.weights.size,
                "suite_sha256": suite_digest(recipe.suite),
            }
            for recipe in MODELS.values()
        ],
        "relay_image": RELAY_IMAGE,
    }
