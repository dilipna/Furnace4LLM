import os

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8100/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
PAYMENTS_URL = os.environ.get("PAYMENTS_URL", "http://payments.internal/refunds")
EMAIL_URL = os.environ.get("EMAIL_URL", "http://mailer.internal/send")
MAX_TOOL_ROUNDS = 4
