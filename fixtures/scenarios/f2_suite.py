"""The F2 reliability suite, bound to graph nodes as for F1 (f1_suite.py). F2 has no RAG, so
there are no citation or grounding items; the approval-gate security check always runs."""

from furnace.guardian.impact import SuiteItem

F2_SUITE: list[SuiteItem] = [
    SuiteItem("unit:tests/test_tools.py", "unit", ["component:app/tools.py::*", "tool:app/tools.py::*"], {"code", "tool", "dependency"}, cost={"seconds": 2}),
    SuiteItem("check:prompt_prefix_stable", "check", ["prompt:*#system"], {"prompt", "code"}, cost={"seconds": 3}),
    SuiteItem("security:approval_gate", "security", ["tool:*", "security_boundary:*"], {"tool", "code"}, always=True, cost={"seconds": 2}),
]  # fmt: skip
