"""Precision regressions found by scanning a real public repository."""

from pathlib import Path

from furnace.code_intel.inventory import build_inventory
from furnace.code_intel.python_ast import extract_python


def _facts(tmp_path: Path, files: dict[str, str]):
    for name, src in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return extract_python(build_inventory(tmp_path))


ASSISTANTS = """
from openai import OpenAI
client = OpenAI()

def ask(thread_id, text):
    client.beta.threads.messages.create(thread_id=thread_id, role="user", content=text)
    return client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id="asst_1")
"""


def test_assistants_thread_message_is_not_inference_but_run_is(tmp_path):
    calls = [f for f in _facts(tmp_path, {"a.py": ASSISTANTS}) if f.kind == "llm_call"]
    assert [c.data["api"] for c in calls] == ["openai.assistants.runs.create"]


ANTHROPIC = """
import anthropic
client = anthropic.Anthropic()

def ask(q):
    return client.messages.create(model="claude-x", max_tokens=10, messages=[{"role": "user", "content": q}])
"""


def test_anthropic_messages_create_still_detected(tmp_path):
    calls = [f for f in _facts(tmp_path, {"a.py": ANTHROPIC}) if f.kind == "llm_call"]
    assert len(calls) == 1 and calls[0].data["api"] == "anthropic.messages.create"
    assert calls[0].data["model_effective"] == "claude-x"


NESTED = """
from flask import Flask
from openai import OpenAI
app = Flask(__name__)
client = OpenAI()

@app.route("/chat", methods=["POST"])
def chat():
    def generate():
        stream = client.chat.completions.create(model="gpt-4o-mini", messages=[], stream=True)
        for chunk in stream:
            yield chunk
    return app.response_class(generate())
"""


def test_nested_function_call_attributed_once_and_linked(tmp_path):
    facts = _facts(tmp_path, {"app.py": NESTED})
    calls = [f for f in facts if f.kind == "llm_call"]
    assert len(calls) == 1
    assert calls[0].data["function_key"] == "component:app.py::chat.generate"
    edges = {(f.key, f.data["callee_key"]) for f in facts if f.kind == "call_edge"}
    assert ("component:app.py::chat", "component:app.py::chat.generate") in edges


def test_same_route_in_two_apps_gets_distinct_keys(tmp_path):
    src = 'from flask import Flask\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "ok"\n'
    routes = [
        f for f in _facts(tmp_path, {"one/app.py": src, "two/app.py": src}) if f.kind == "route"
    ]
    assert {r.key for r in routes} == {"route:one/app.py::GET /", "route:two/app.py::GET /"}
