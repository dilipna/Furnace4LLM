"""Real loopback predictions with the scripted adapter; no model or Docker proof implied."""

import base64
import io
import json
import subprocess
import sys
import zipfile

import pytest
from furnace.runtime.catalog import ENGINES, MODELS
from furnace_api.documents import extract_document
from furnace_api.everyday import chunks
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.api.tests.test_studio_managed import ANSWERS, MODEL, build, client_for, ready_project


def text_pdf(text="Review meeting on 2026-12-03. Owner: Maya."):
    writer = PdfWriter()
    page = writer.add_blank_page(width=500, height=500)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 30 30 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


def privacy_double(app, fake, pid):
    def observed(_):
        saved = app.state.runtime.store.get(pid)["managed_server"]
        return {
            "evidence_kind": "test_adapter",
            "launch_id": saved["launch"]["launch_id"],
            "image": ENGINES[MODELS[MODEL].engine].images["cpu"],
            "checks": {
                name: True
                for name in (
                    "running",
                    "internal_network_only",
                    "non_root",
                    "read_only_root",
                    "all_capabilities_dropped",
                    "no_new_privileges",
                    "no_direct_published_ports",
                    "read_only_mounts",
                )
            },
        }

    setattr(fake, "privacy_state", observed)
    setattr(fake, "gpu", lambda: {})
    return observed


@pytest.mark.parametrize("kind", ["txt", "md", "pdf", "docx"])
def test_real_bounded_extractor_preserves_document_text(kind):
    marker = "Private invoice 12345"
    data = marker.encode()
    if kind == "pdf":
        data = text_pdf(marker)
    elif kind == "docx":
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w") as z:
            z.writestr(
                "word/document.xml",
                f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{marker}</w:t></w:r></w:p></w:body></w:document>',
            )
        data = target.getvalue()
    result = extract_document(kind, base64.b64encode(data).decode())
    assert marker in result["text"] and result["ocr"] is False


@pytest.mark.parametrize(
    "kind,data",
    [("txt", b"\xff"), ("pdf", b"not a PDF"), ("txt", b"x" * 24001), ("docx", b"not a zip")],
)
def test_parser_failures_do_not_echo_private_input(kind, data):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        extract_document(kind, base64.b64encode(data).decode())
    assert error.value.status_code == 422
    assert "not a PDF" not in str(error.value.detail)


def test_byte_chunks_do_not_cut_unicode_or_omit_text():
    text = "秘密の資料🙂" * 500
    parts = chunks(text)
    assert "".join(parts) == text
    assert all(len(part.encode()) <= 1000 for part in parts)


def test_document_answer_receipt_and_no_content_in_records_logs_or_exports(tmp_path, monkeypatch):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        privacy_double(app, fake, pid)
        marker = "PRIVATE_SENTINEL_783912 is confidential."
        answer_marker = "PRIVATE_ANSWER_SENTINEL_393192"
        monkeypatch.setitem(ANSWERS, marker, answer_marker)
        result = client.post(
            f"/api/everyday/projects/{pid}/answer", json={"text": marker, "action": "summarise"}
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["output"] == answer_marker and body["processing"]["model_requests"] == 1
        assert body["receipt"]["status"] == "test_adapter_only"
        assert (
            body["receipt"]["launch_id"]
            == client.get(f"/api/projects/{pid}/managed").json()["launch"]["launch_id"]
        )
        assert body["requests"][0]["request_id"]
        assert marker not in client.get(f"/api/projects/{pid}").text
        exported_response = client.post(f"/api/projects/{pid}/kit")
        assert exported_response.status_code == 200
        archive = exported_response.content
        with zipfile.ZipFile(io.BytesIO(archive)) as exported:
            for filename in exported.namelist():
                content = exported.read(filename)
                assert marker.encode() not in content
                assert answer_marker.encode() not in content
        database = (tmp_path / "ws/studio.sqlite3").read_bytes()
        assert marker.encode() not in database
        assert answer_marker.encode() not in database
        for path in (tmp_path / "ws/logs").rglob("*"):
            if path.is_file():
                assert marker.encode() not in path.read_bytes()
                assert answer_marker.encode() not in path.read_bytes()


def test_incomplete_isolation_refuses_to_send_document(tmp_path, monkeypatch):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        observed = privacy_double(app, fake, pid)

        def unsafe(pid):
            result = observed(pid)
            result["checks"]["internal_network_only"] = False
            return result

        monkeypatch.setattr(fake, "privacy_state", unsafe, raising=False)
        calls = []
        monkeypatch.setattr(app.state.model.client, "predict", lambda *a, **k: calls.append(a))
        response = client.post(
            f"/api/everyday/projects/{pid}/answer", json={"text": "private", "action": "summarise"}
        )
        assert response.status_code == 409
        assert not calls


def test_staged_document_executes_each_section_and_combines_results(tmp_path):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        privacy_double(app, fake, pid)
        result = client.post(
            f"/api/everyday/projects/{pid}/answer",
            json={"text": "Notes about a meeting. " * 120, "action": "summarise"},
        )
        assert result.status_code == 200, result.text
        processing = result.json()["processing"]
        assert processing["staged"] and processing["document_chunks"] == 3
        assert processing["model_requests"] == 4


def test_extraction_and_answer_routes_keep_session_and_origin_boundaries(tmp_path):
    app, _ = build(tmp_path)
    with client_for(app) as client:
        body = {"kind": "txt", "data": base64.b64encode(b"private").decode()}
        assert (
            client.post(
                "/api/everyday/extract", json=body, headers={"Origin": "https://malicious.test"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/everyday/extract", json=body, headers={"x-furnace-session": "wrong"}
            ).status_code
            == 401
        )
        response = client.post("/api/everyday/extract", json=body)
        assert response.json()["text"] == "private"
        assert response.headers["Cache-Control"] == "no-store"
        assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
        assert (
            client.post(
                "/api/everyday/extract",
                content=json.dumps({"kind": "txt", "data": "x" * 4_010_001}),
            ).status_code
            == 413
        )


@pytest.mark.parametrize("fault", ["token_limit", "launch_changed"])
def test_incomplete_or_changed_answer_cannot_get_a_receipt(tmp_path, monkeypatch, fault):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        observed = privacy_double(app, fake, pid)
        original = app.state.model.client.predict

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if fault == "token_limit":
                result["finish_reason"] = "length"
            else:

                def wrong_launch(project):
                    value = observed(project)
                    value["launch_id"] = "different-launch"
                    return value

                monkeypatch.setattr(fake, "privacy_state", wrong_launch, raising=False)
            return result

        monkeypatch.setattr(app.state.model.client, "predict", changed)
        response = client.post(
            f"/api/everyday/projects/{pid}/answer",
            json={"action": "summarise", "text": "private text"},
        )
        assert response.status_code == 409
        assert "receipt" not in response.json() and "output" not in response.json()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object resource boundary")
def test_windows_parser_job_enforces_its_memory_limit():
    from furnace_api.documents import WindowsJob

    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read(); bytearray(512*1024**2)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    job = WindowsJob(child.pid)
    try:
        child.communicate(b"", timeout=10)
        assert child.returncode != 0
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        job.close()


def test_chat_context_is_bounded_and_ephemeral(tmp_path, monkeypatch):
    app, fake = build(tmp_path)
    with client_for(app) as client:
        pid = ready_project(client)
        privacy_double(app, fake, pid)
        marker = "PRIVATE_CHAT_CONTEXT_543987"
        monkeypatch.setitem(ANSWERS, marker, "context received")
        response = client.post(
            f"/api/everyday/projects/{pid}/answer",
            json={
                "action": "chat",
                "question": "What did I say?",
                "history": [{"role": "user", "content": marker}],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["output"] == "context received"
        assert response.json()["processing"]["history_turns"] == 1
        assert marker not in client.get(f"/api/projects/{pid}").text
        assert marker.encode() not in (tmp_path / "ws/studio.sqlite3").read_bytes()
        invalid = client.post(
            f"/api/everyday/projects/{pid}/answer",
            json={
                "action": "chat",
                "question": "What did I say?",
                "history": [
                    {"role": "user", "content": "secret" * 100},
                    {"role": "assistant", "content": "another secret"},
                ],
            },
        )
        assert invalid.status_code == 422
        assert "another secret" not in invalid.text
