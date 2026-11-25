import argparse
import base64
import io
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

parser = argparse.ArgumentParser()
parser.add_argument("--app", type=Path, required=True)
parser.add_argument("--out", type=Path, default=Path("dist/real-document-recording"))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
app = args.app.resolve()
workspace = Path(tempfile.mkdtemp(prefix="furnace-document-recording-"))
record = {
    "schema": "furnace-everyday-recording-v1",
    "kind": "private-document-recording",
    "installed_build": json.loads((app / "build.json").read_text()),
    "model": "qwen2.5-1.5b-instruct-q4_k_m",
    "accelerator": "nvidia",
    "cache": "Shared verified model cache; explicit prepare/start before footage",
    "editing": "Uncut browser recording, with paced reading pauses; setup outside footage",
    "events": [],
    "result": "failed",
}
child = subprocess.Popen(  # noqa: S603 -- explicit installed app and owned probe, no shell
    [
        str(app / "runtime/python.exe"),
        "-I",
        str(root / "scripts/installed_probe.py"),
        str(app),
        str(workspace),
        str(Path.home() / ".furnace/artifacts"),
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
try:
    ready = json.loads(child.stdout.readline())
    with httpx.Client(
        base_url=ready["url"],
        headers={"x-furnace-session": ready["token"]},
        timeout=180,
        trust_env=False,
    ) as client:

        def api(method, path, **kw):
            r = client.request(method, "/api/" + path, **kw)
            r.raise_for_status()
            return r.json()

        pid = api("POST", "everyday/setup")["id"]
        api(
            "PUT",
            f"projects/{pid}/managed",
            json={
                "model": record["model"],
                "accelerator": "nvidia",
                "memory_mb": 4096,
                "context_tokens": 4096,
                "max_tokens": 512,
                "request_timeout_seconds": 120,
            },
        )
        api("POST", f"projects/{pid}/managed/prepare", json={"consent": True})
        deadline = time.monotonic() + 600
        while True:
            state = api("GET", f"projects/{pid}/managed")
            if state["status"] in ("prepared", "failed"):
                break
            assert time.monotonic() < deadline
            time.sleep(1)
        assert state["status"] == "prepared", state.get("reason")
        api("POST", f"projects/{pid}/managed/start", json={"consent": True})
        record["hardware_observation"] = api("GET", f"projects/{pid}/managed/observe")["gpu"]
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
        stream.set_data(
            b"BT /F1 12 Tf 30 450 Td (Invoice IV-104: 875 dollars due 2026-12-03. Supplier: Cedar Design.) Tj ET"
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        pdf = io.BytesIO()
        writer.write(pdf)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                record_video_dir=str(out / "raw-video"),
                record_video_size={"width": 1440, "height": 1000},
            )
            view = context.new_page()
            began = time.monotonic()

            def event(name, caption):
                record["events"].append(
                    {
                        "name": name,
                        "seconds": round(time.monotonic() - began, 2),
                        "caption": caption,
                    }
                )
                view.screenshot(path=str(out / (name + ".png")))
                view.wait_for_timeout(1500)

            view.goto(ready["url"] + "/#session=" + ready["token"])
            expect(view.locator("#model-status")).to_contain_text("ready", timeout=30000)
            event(
                "home",
                "Actual installed local app. Pinned Qwen 1.5B is ready on the NVIDIA recipe; cached preparation is not shown.",
            )
            dt = view.evaluate_handle(
                "data=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(data),c=>c.charCodeAt(0))],'synthetic-invoice.pdf',{type:'application/pdf'}));return dt;}",
                base64.b64encode(pdf.getvalue()).decode(),
            )
            view.locator("#document-box").dispatch_event("drop", {"dataTransfer": dt})
            expect(view.locator("#document-info")).to_contain_text(
                "synthetic-invoice.pdf", timeout=30000
            )
            event(
                "document",
                "A synthetic text PDF is extracted locally. No private customer document is used.",
            )
            with view.expect_response(
                lambda r: r.url.endswith("/answer"), timeout=180000
            ) as response:
                view.get_by_role("button", name="Summarise", exact=True).click()
            assert response.value.status == 200
            answer = response.value.json()
            assert answer["receipt"]["status"] == "checked"
            record["answer"] = answer
            expect(view.locator(".output")).to_have_text(answer["output"])
            event(
                "answer",
                "Actual model summary. Check important facts against the original; privacy is not answer quality.",
            )
            view.locator(".receipt > summary").click()
            view.locator(".receipt").scroll_into_view_if_needed()
            event(
                "receipt",
                "Observed model-container checks. This is not proof of host-wide traffic or a compliance certificate.",
            )
            mobile = browser.new_page(
                viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
            )
            mobile.goto(ready["url"] + "/#session=" + ready["token"])
            expect(mobile.locator("#model-status")).to_contain_text("ready", timeout=30000)
            mobile.screenshot(path=str(out / "app-mobile.png"), full_page=True)
            video = view.video
            context.close()
            shutil.copy2(video.path(), out / "journey.webm")
            browser.close()
        record["result"] = "passed"
finally:
    if child.stdin:
        child.stdin.write("quit\n")
        child.stdin.flush()
    stdout, stderr = child.communicate(timeout=180)
    record["quit_and_lease_released"] = child.returncode == 0 and '"lease_released": true' in stdout
    (out / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
assert record["result"] == "passed" and record["quit_and_lease_released"]
print(out / "record.json")
