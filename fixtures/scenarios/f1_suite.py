"""The F1 reliability suite: what Forge installs for F1, bound to graph nodes.

Costs are rough per-run estimates used for RQ3 cost accounting and are replaced
by measured durations when the suite actually runs.
"""

from furnace.guardian.impact import SuiteItem

QUALITY_TRIGGERS = {"prompt", "retrieval_config", "retrieval", "model", "llm_call", "code", "generation_config", "serving_config", "endpoint", "llm_sdk"}
PERF_TRIGGERS = {"prompt", "retrieval_config", "retrieval", "serving_config", "model", "llm_call", "endpoint", "generation_config"}

F1_SUITE: list[SuiteItem] = [
    SuiteItem("unit:tests/test_retriever.py", "unit", ["component:app/retriever.py::*", "retriever:app/retriever.py::*"], {"code", "dependency"}, cost={"seconds": 2}),
    SuiteItem("unit:tests/test_prompts.py", "unit", ["component:app/prompts.py::*", "prompt:app/prompts.py::*"], {"code", "prompt", "dependency"}, cost={"seconds": 2}),
    SuiteItem("check:citation_required", "check", ["capability:*::rag_answer"], QUALITY_TRIGGERS, cost={"seconds": 60, "gpu_seconds": 60}),
    SuiteItem("judge:ungrounded_answer", "judge", ["capability:*::rag_answer"], QUALITY_TRIGGERS - {"serving_config", "endpoint"}, cost={"seconds": 90, "llm_tokens": 120_000}),
    SuiteItem("check:prompt_prefix_stable", "check", ["prompt:*#system"], {"prompt", "code"}, cost={"seconds": 3}),
    SuiteItem("check:context_budget", "check", ["config_key:*retrieval*", "retriever:*", "prompt:*#system"], {"retrieval_config", "retrieval", "prompt"}, cost={"seconds": 3}),
    SuiteItem("security:approval_gate", "security", ["tool:*", "security_boundary:*"], {"tool", "code"}, always=True, cost={"seconds": 2}),
    SuiteItem("bench:chat_perf_gate", "benchmark", ["workflow:app/main.py::POST /chat"], PERF_TRIGGERS, cost={"seconds": 420, "gpu_seconds": 420}),
]
