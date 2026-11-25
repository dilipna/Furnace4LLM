"""Opt-in real cached-model probe; no installer, publication or quality benchmark."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from furnace_api.desktop import DesktopService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite an existing probe")
    git = shutil.which("git")
    assert git
    root = Path(__file__).resolve().parents[1]
    record: dict = {
        "schema": "furnace-real-timeout-recovery-v1",
        "at": datetime.now(UTC).isoformat(),
        "source_commit": subprocess.check_output(  # noqa: S603 -- resolved git, fixed argv
            [git, "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_dirty": bool(subprocess.check_output([git, "status", "--porcelain"], cwd=root)),  # noqa: S603 -- resolved git, fixed argv
        "timeout_seconds": 2,
        "result": "failed",
    }
    service = DesktopService(
        Path(tempfile.mkdtemp(prefix="furnace-timeout-probe-")), Path.home() / ".furnace/artifacts"
    )
    try:
        service.start()
        with httpx.Client(
            base_url=service.url,
            headers={"x-furnace-session": service.token},
            timeout=300,
            trust_env=False,
        ) as client:

            def api(method, path, **kwargs):
                response = client.request(method, "/api/" + path, **kwargs)
                response.raise_for_status()
                return response.json()

            def observe():
                value = api("GET", f"projects/{pid}/managed/observe")
                return {key: value.get(key) for key in ("gpu", "resources", "container")}

            pid = api("POST", "everyday/setup")["id"]
            selection = {
                "model": "qwen2.5-1.5b-instruct-q4_k_m",
                "accelerator": "cpu",
                "threads": 4,
                "memory_mb": 4096,
                "context_tokens": 4096,
                "max_tokens": 512,
                "request_timeout_seconds": 2,
                "evaluation_budget_seconds": 900,
            }
            record["selection"] = selection
            api("PUT", f"projects/{pid}/managed", json=selection)
            api("POST", f"projects/{pid}/managed/prepare", json={"consent": True})
            deadline = time.monotonic() + 1800
            while True:
                state = api("GET", f"projects/{pid}/managed")
                if state["status"] in {"prepared", "failed"}:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Preparation deadline")
                time.sleep(1)
            assert state["status"] == "prepared", state.get("reason")
            api("POST", f"projects/{pid}/managed/start", json={"consent": True})
            record["before"] = observe()
            model = service.server.config.app.state.model
            _, config = model.ready(pid)
            prompt = "Count from 1 to 300 in order, without skipping numbers. Output only the complete list."
            # Control uses the same pinned server and output cap, with the existing
            # maximum request deadline. It must actually take longer than 2 seconds.
            record["control"] = model.client.predict(
                config, prompt, 120, api_key=model.key_for(pid, config)
            )
            assert record["control"]["duration_ms"] > 2000
            began = time.monotonic()
            response = client.post(f"/api/projects/{pid}/model/predict", json={"input": prompt})
            record["timeout"] = {
                "http_status": response.status_code,
                "body": response.json(),
                "elapsed_seconds": round(time.monotonic() - began, 3),
            }
            assert response.status_code == 409 and response.json()["detail"] == "endpoint_timeout"
            record["followups"] = []
            for _ in range(4):
                response = client.post(
                    f"/api/projects/{pid}/model/predict",
                    json={"input": "What is 2 + 2? Reply with only the number."},
                )
                record["followups"].append(
                    {"http_status": response.status_code, "body": response.json()}
                )
            assert all(r["http_status"] == 200 for r in record["followups"])
            record["state"] = api("GET", f"projects/{pid}/model")["model_endpoint"]["state"]
            assert record["state"]["status"] == "connected"
            record["after"] = observe()
            record["result"] = "passed"
    except Exception as error:
        record["error"] = type(error).__name__
    finally:
        record["shutdown_completed"] = service.stop() if service.thread.ident else True
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(args.out, record["result"], flush=True)
    return 0 if record["result"] == "passed" and record["shutdown_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
