import functools
import http.server
import importlib.util
import mimetypes
import threading
from pathlib import Path

import httpx

spec = importlib.util.spec_from_file_location(
    "download_preview_test", Path(__file__).resolve().parents[3] / "scripts/preview_site.py"
)
assert spec and spec.loader
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def test_preview_prefers_exported_route_over_asset_directory_and_serves_real_404(
    tmp_path, monkeypatch
):
    mimetypes.init()
    monkeypatch.setitem(mimetypes.types_map, ".js", "text/plain")
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo.html").write_text("<h1>Recorded tour</h1>")
    (tmp_path / "404.html").write_text("<h1>Not found</h1>")
    js = tmp_path / "_next/static/chunk.js"
    js.parent.mkdir(parents=True)
    js.write_text("/* test content */" * 1000)
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(preview.ExportHandler, directory=str(tmp_path))
    )
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.get("/demo").text == "<h1>Recorded tour</h1>"
            missing = client.get("/missing")
            assert missing.status_code == 404 and "Not found" in missing.text
            asset = client.get("/_next/static/chunk.js")
            assert asset.headers["Content-Encoding"] == "gzip"
            assert asset.headers["Content-Type"] == "text/javascript"
            assert asset.text == js.read_text()
            assert "immutable" in asset.headers["Cache-Control"]
    finally:
        server.shutdown()
        worker.join()
        server.server_close()
