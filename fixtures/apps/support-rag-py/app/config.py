import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8100/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
MODEL = os.getenv("LLM_MODEL", "lab")
TICKETS_URL = os.getenv("TICKETS_URL", "http://localhost:9000/tickets")
TRACE_LOG = Path(os.getenv("TRACE_LOG", str(ROOT / "traces" / "llm_calls.jsonl")))


@lru_cache
def rag_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
