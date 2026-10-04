import time
from collections.abc import Iterator

from openai import OpenAI

from app.config import LLM_API_KEY, LLM_BASE_URL, MODEL
from app.trace_log import log_llm_call

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


def stream_answer(
    messages: list[dict[str, str]], *, max_tokens: int, temperature: float, route: str
) -> Iterator[str]:
    start = time.perf_counter()
    first_token_at = None
    parts: list[str] = []
    usage = None
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=max_tokens,
        temperature=temperature,
    )
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            if first_token_at is None:
                first_token_at = time.perf_counter()
            parts.append(chunk.choices[0].delta.content)
            yield chunk.choices[0].delta.content
    end = time.perf_counter()
    log_llm_call(
        route=route,
        model=MODEL,
        messages=messages,
        completion="".join(parts),
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        latency_ms=(end - start) * 1000,
        ttft_ms=(first_token_at - start) * 1000 if first_token_at else None,
        stream=True,
    )
