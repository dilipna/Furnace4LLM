"""Serve the static preview on loopback; no API proxy and no deployment."""

import argparse
import functools
import gzip
import http.server
import io
from pathlib import Path


class ExportHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        file = Path(self.translate_path(self.path))
        if (
            file.is_file()
            and file.suffix in {".html", ".css", ".js", ".json", ".svg", ".txt"}
            and "gzip" in self.headers.get("Accept-Encoding", "")
        ):
            data = gzip.compress(file.read_bytes(), mtime=0)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(file)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return io.BytesIO(data)
        return super().send_head()

    def end_headers(self):
        if self.path.startswith("/_next/static/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        super().end_headers()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        page = Path(self.directory) / "404.html"
        if code == 404 and page.is_file():
            data = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        else:
            super().send_error(code, message, explain)

    def translate_path(self, path: str) -> str:
        resolved = Path(super().translate_path(path))
        # /demo also has a public video directory. Prefer the exported page over
        # a directory listing, matching the static host's clean-URL routing.
        if resolved.with_suffix(".html").is_file():
            return str(resolved.with_suffix(".html"))
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("apps/web/out"))
    parser.add_argument("--port", type=int, default=4010)
    args = parser.parse_args()
    if not (args.root / "index.html").is_file():
        raise SystemExit("Build the static site first; see docs/operations/windows-download.md")
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        functools.partial(ExportHandler, directory=str(args.root.resolve())),
    )
    print(f"Unpublished local preview: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
