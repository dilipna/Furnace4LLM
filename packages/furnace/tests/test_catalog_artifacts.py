"""Pinned recipes and verified, resumable artifact downloads (local transport, no network)."""

import hashlib
import threading

import httpx
import pytest
from furnace.runtime import catalog
from furnace.runtime.artifacts import ArtifactError, ArtifactStore, _https_only
from furnace.runtime.catalog import Artifact
from furnace.runtime.scoring import ScoringRule

DATA = bytes(range(256)) * 4096  # 1 MiB of deterministic bytes
ART = Artifact(
    url="https://example.invalid/weights.bin",
    sha256=hashlib.sha256(DATA).hexdigest(),
    size=len(DATA),
    filename="weights.bin",
)


def test_every_recipe_pins_image_digests_weights_and_a_valid_reference_suite():
    for recipe in catalog.MODELS.values():
        assert len(recipe.weights.sha256) == 64 and recipe.weights.size > 0
        assert recipe.weights.url.startswith("https://huggingface.co/")
        assert f"/resolve/{recipe.revision}/" in recipe.weights.url
        assert len(recipe.revision) == 40
        engine = catalog.ENGINES[recipe.engine]
        assert all("@sha256:" in image for image in engine.images.values())
        cases = catalog.suite_cases(recipe.suite)
        assert 1 <= len(cases) <= 30
        for case in cases:
            assert set(case) == {"name", "input", "expected_behavior", "expected_output", "scoring"}
            ScoringRule.model_validate(case["scoring"])
    assert "@sha256:" in catalog.RELAY_IMAGE


def test_changed_reference_suite_cannot_keep_its_identity(monkeypatch):
    real = catalog.SUITES["general-tasks-v1"]
    monkeypatch.setitem(
        catalog.SUITES, real.id, catalog.Suite(real.id, real.filename, "0" * 64, real.description)
    )
    with pytest.raises(catalog.CatalogError):
        catalog.suite_cases(real.id)


def test_manifest_digest_changes_with_any_pinned_input():
    base = catalog.manifest("qwen2.5-0.5b-instruct-q8_0", "cpu", {"threads": 4})
    assert catalog.manifest_digest(base) == catalog.manifest_digest(
        catalog.manifest("qwen2.5-0.5b-instruct-q8_0", "cpu", {"threads": 4})
    )
    for other in (
        catalog.manifest("qwen2.5-0.5b-instruct-q8_0", "nvidia", {"threads": 4}),
        catalog.manifest("qwen2.5-0.5b-instruct-q8_0", "cpu", {"threads": 2}),
        catalog.manifest("granite-4.0-h-350m-q8_0", "cpu", {"threads": 4}),
    ):
        assert catalog.manifest_digest(other) != catalog.manifest_digest(base)


class Server:
    """Serves DATA with range support; can cut a response short or corrupt it."""

    def __init__(self):
        self.requests = []
        self.cut_after: int | None = None
        self.corrupt = False
        self.ignore_range = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.headers.get("range"))
        start = 0
        header = request.headers.get("range")
        if header and not self.ignore_range:
            start = int(header.split("=")[1].split("-")[0])
        body = DATA[start:]
        if self.corrupt:
            body = b"\xff" + body[1:]  # DATA starts with 0x00
        if self.cut_after is not None:
            body, self.cut_after = body[: self.cut_after], None

            def chunks():
                yield body
                raise httpx.ReadError("connection reset")

            status = 206 if start else 200
            headers = {"content-range": f"bytes {start}-{len(DATA) - 1}/{len(DATA)}"}
            return httpx.Response(status, headers=headers, content=chunks())
        pieces = iter([body[i : i + 65536] for i in range(0, len(body), 65536)])
        if start:
            return httpx.Response(
                206, headers={"content-range": f"bytes {start}-{len(DATA) - 1}/{len(DATA)}"},
                content=pieces,
            )  # fmt: skip
        return httpx.Response(200, content=pieces)


def store_for(tmp_path, server):
    return ArtifactStore(tmp_path, client=httpx.Client(transport=httpx.MockTransport(server)))


def test_interrupted_download_resumes_with_range_and_publishes_only_verified_bytes(tmp_path):
    server = Server()
    server.cut_after = 300_000
    store = store_for(tmp_path, server)
    path = store.fetch(ART, attempts=3)
    assert path.read_bytes() == DATA
    assert server.requests == [None, "bytes=300000-"]
    assert not list((tmp_path / "partial").iterdir())
    assert store.status(ART)["state"] == "present"
    # A second prepare re-verifies instead of downloading again.
    assert store.fetch(ART) == path and len(server.requests) == 2


def test_partial_file_survives_cancellation_and_is_never_served(tmp_path):
    server = Server()
    cancel = threading.Event()
    store = store_for(tmp_path, server)

    def progress(done, total):
        if done >= 1:
            cancel.set()

    with pytest.raises(ArtifactError, match="download_cancelled"):
        store.fetch(ART, progress=progress, cancel=cancel)
    assert store.status(ART)["state"] == "partial"
    with pytest.raises(ArtifactError, match="artifact_missing"):
        store.verify(ART)
    assert store.fetch(ART).read_bytes() == DATA


def test_digest_mismatch_discards_download_and_tampered_blob_is_quarantined(tmp_path):
    server = Server()
    server.corrupt = True
    store = store_for(tmp_path, server)
    with pytest.raises(ArtifactError, match="download_digest_mismatch"):
        store.fetch(ART)
    assert store.status(ART)["state"] == "absent"
    server.corrupt = False
    path = store.fetch(ART)
    path.chmod(0o644)
    path.write_bytes(b"\x01" + DATA[1:])
    with pytest.raises(ArtifactError, match="artifact_digest_mismatch"):
        store.verify(ART)
    assert not path.exists()
    assert len(list((tmp_path / "quarantine").iterdir())) == 1


def test_server_ignoring_range_restarts_cleanly_and_oversize_is_refused(tmp_path):
    server = Server()
    store = store_for(tmp_path, server)
    (tmp_path / "partial").mkdir(parents=True)
    (tmp_path / "partial" / f"{ART.sha256}.part").write_bytes(DATA[:1000])
    server.ignore_range = True
    assert store.fetch(ART).read_bytes() == DATA
    small = Artifact(ART.url, hashlib.sha256(DATA[:10]).hexdigest(), 10, "small.bin")
    with pytest.raises(ArtifactError, match="download_larger_than_pinned_size"):
        store_for(tmp_path / "other", Server()).fetch(small)


def test_redirects_must_stay_on_https():
    with pytest.raises(ArtifactError, match="download_redirect_not_https"):
        _https_only(httpx.Request("GET", "http://cdn.example.invalid/file"))
    _https_only(httpx.Request("GET", "https://cdn.example.invalid/file"))
