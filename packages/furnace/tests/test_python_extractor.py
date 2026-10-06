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


# Gaps found by FurnaceBench RQ1 on held-out OSS apps (2026-10-06): module-level scripts,
# clients created inside blocks/functions, LangChain model wrappers, legacy anthropic.Client.

SCRIPT = """
import streamlit as st
from openai import OpenAI

if prompt := st.chat_input():
    client = OpenAI(api_key=st.secrets["k"])
    reply = client.chat.completions.create(model="gpt-4o-mini", messages=[])
"""


def test_module_level_call_with_client_built_in_a_block(tmp_path):
    facts = _facts(tmp_path, {"page.py": SCRIPT})
    (call,) = [f for f in facts if f.kind == "llm_call"]
    assert call.key == "component:page.py::<module>#llm0"
    assert call.data["function_key"] == "component:page.py"
    assert call.data["model_effective"] == "gpt-4o-mini"
    assert call.data["endpoint_key"] == "endpoint:page.py::client"


LOCAL_CLIENT = """
from openai import OpenAI

def ask(q):
    client = OpenAI(timeout=5)
    return client.chat.completions.create(model="m", messages=[{"role": "user", "content": q}])
"""


def test_function_local_client_resolves_endpoint_and_timeout(tmp_path):
    facts = _facts(tmp_path, {"a.py": LOCAL_CLIENT})
    (call,) = [f for f in facts if f.kind == "llm_call"]
    (client,) = [f for f in facts if f.kind == "llm_client"]
    assert call.data["endpoint_key"] == client.key == "endpoint:a.py::ask.client"
    assert client.data["has_timeout"] is True


LANGCHAIN = """
from langchain_community.llms.ollama import Ollama
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import OpenAI

def answer(q):
    return Ollama(model="mistral").invoke(q)

def stream(q):
    llm = ChatOpenAI(model_name="gpt-4o-mini", streaming=True)
    return llm.invoke(q)

def chain(store):
    llm = ChatOpenAI()
    return ConversationalRetrievalChain.from_llm(llm=llm, retriever=store.as_retriever())

def legacy(text):
    llm = OpenAI(temperature=0.7)
    return llm(text)
"""


def test_langchain_invocations_and_models_handed_to_chains(tmp_path):
    calls = {
        f.data["function_key"].split("::")[-1]: f
        for f in _facts(tmp_path, {"lc.py": LANGCHAIN})
        if f.kind == "llm_call"
    }
    assert set(calls) == {"answer", "stream", "chain", "legacy"}
    assert calls["answer"].data["api"] == "langchain.Ollama.invoke"
    assert calls["answer"].data["model_effective"] == "mistral"
    assert (
        calls["stream"].data["model_effective"] == "gpt-4o-mini"
        and calls["stream"].data["stream"] is True
    )
    assert calls["chain"].data["api"] == "langchain.ChatOpenAI (via from_llm)"
    assert calls["chain"].data["model_effective"] is None  # library default, not invented
    assert calls["legacy"].data["api"] == "langchain.OpenAI.__call__"


def test_sdk_openai_client_is_not_mistaken_for_langchain(tmp_path):
    facts = _facts(tmp_path, {"a.py": LOCAL_CLIENT})
    assert all(f.data.get("framework") is None for f in facts if f.kind == "llm_client")


LEGACY_ANTHROPIC = """
import anthropic

def ask(q):
    client = anthropic.Client(api_key="k")
    return client.completions.create(prompt=q, model="claude-v1", max_tokens_to_sample=10)
"""


def test_legacy_anthropic_client_completions(tmp_path):
    facts = _facts(tmp_path, {"a.py": LEGACY_ANTHROPIC})
    (call,) = [f for f in facts if f.kind == "llm_call"]
    assert call.data["api"] == "anthropic.completions.create"
    assert call.data["model_effective"] == "claude-v1"
    (client,) = [f for f in facts if f.kind == "llm_client"]
    assert client.data["sdk"] == "anthropic"


def test_html_templates_are_not_prompts(tmp_path):
    src = 'css = "<style>.chat-message { padding: 1rem }</style>"\nbot_template = "<div class=\\"msg\\">{{MSG}}</div>" * 3\nSYSTEM_PROMPT = "You are a careful assistant. Answer only from the context."\n'
    keys = {f.key for f in _facts(tmp_path, {"t.py": src}) if f.kind == "prompt"}
    assert keys == {"prompt:t.py::SYSTEM_PROMPT"}


VECTOR = """
from langchain.vectorstores.chroma import Chroma

def query(q):
    db = Chroma(persist_directory="chroma")
    return db.similarity_search_with_score(q, k=5)
"""


def test_langchain_vector_store_and_literal_k(tmp_path):
    (r,) = [f for f in _facts(tmp_path, {"q.py": VECTOR}) if f.kind == "retriever"]
    assert r.data["store"] == "chroma" and r.data["top_k_literal"] == 5


def test_llm_calls_in_tests_are_evals_not_app_call_sites(tmp_path):
    from furnace.reconstruction.build import reconstruct

    (tmp_path / "app.py").write_text(LOCAL_CLIENT, encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        LOCAL_CLIENT.replace("def ask", "def judge")
        + "\nEVAL_PROMPT = 'Answer true or false: does the response match the expected one?'\n",
        encoding="utf-8",
    )
    spec = reconstruct(tmp_path).appspec
    assert [c.key for c in spec.llm_calls] == ["component:app.py::ask#llm0"]
    assert [e.value for e in spec.reliability_existing.evals] == [
        "tests call an LLM (1 call site(s): live-model or LLM-judged tests)"
    ]
    assert not [p for p in spec.prompts if p.key.startswith("prompt:test_app.py")]


def test_several_models_in_code_are_not_a_contradiction(tmp_path):
    from furnace.reconstruction.build import reconstruct

    two = (
        LOCAL_CLIENT
        + "\n\ndef other(q):\n    client = OpenAI()\n    return client.chat.completions.create(model='m2', messages=[])\n"
    )
    (tmp_path / "app.py").write_text(two, encoding="utf-8")
    spec = reconstruct(tmp_path).appspec
    assert sorted(c.model.value for c in spec.llm_calls if c.model) == ["m", "m2"]
    assert spec.contradictions == []
