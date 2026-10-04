"""Append-only JSONL log of LLM calls (one line per call)."""

import json
import threading
import time
from typing import Any

from app.config import TRACE_LOG

_lock = threading.Lock()


def log_llm_call(**fields: Any) -> None:
    record = {"ts": time.time(), **fields}
    TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _lock, TRACE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
