import json

from furnace_bench.sse import DONE, SSEDecoder, inspect_chunk


def chunk(delta, **extra):
    return json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": None}], **extra})


def feed_all(lines):
    d = SSEDecoder()
    out = []
    for line in lines:
        item = d.feed(line)
        if item is not None:
            out.append(item)
    return out


def test_data_events_comments_and_done():
    lines = [": keep-alive", "", f"data: {chunk({'content': 'hi'})}", "", "data: [DONE]", ""]
    out = feed_all(lines)
    assert len(out) == 2
    assert json.loads(out[0])["choices"][0]["delta"]["content"] == "hi"
    assert out[1] is DONE


def test_multiline_data_is_joined():
    out = feed_all(['data: {"choices":', "data: []}", ""])
    assert json.loads(out[0]) == {"choices": []}


def test_role_only_chunk_has_no_output():
    info = inspect_chunk(chunk({"role": "assistant", "content": ""}))
    assert not info.has_output


def test_content_reasoning_and_tool_calls_count_as_output():
    assert inspect_chunk(chunk({"content": "x"})).has_output
    assert inspect_chunk(chunk({"reasoning_content": "x"})).has_output
    assert inspect_chunk(chunk({"tool_calls": [{"index": 0}]})).has_output


def test_usage_and_error_chunks():
    usage = inspect_chunk(
        json.dumps({"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 5}})
    )
    assert usage.usage == {"prompt_tokens": 3, "completion_tokens": 5}
    assert not usage.has_output
    err = inspect_chunk(json.dumps({"error": {"message": "overloaded"}}))
    assert err.error == "overloaded"


def test_legacy_completions_text():
    info = inspect_chunk(json.dumps({"choices": [{"text": "abc", "finish_reason": None}]}))
    assert info.has_output and info.n_choices_text_chars == 3
