import json

import pytest

from furnace_bench.fingerprint import (
    TraceRecord,
    block_hashes,
    fingerprint,
    load_traces,
    parse_record,
    prefix_reuse,
)


def test_block_hashes_chain_and_drop_partial_block():
    a = block_hashes(list(range(40)), 16)
    assert len(a) == 2  # 40 tokens -> 2 full blocks, partial dropped
    b = block_hashes([99, *list(range(1, 40))], 16)
    # same second block content, different first block: chained hash must differ
    assert a[1] != b[1]


def test_prefix_reuse_counts_only_longest_cached_prefix():
    shared = list(range(32))  # 2 blocks
    p1 = shared + [1000 + i for i in range(16)]
    p2 = shared + [2000 + i for i in range(16)]
    p3 = [5000 + i for i in range(16)] + shared  # same blocks but not as a prefix
    inf, lru = prefix_reuse([p1, p2, p3], block=16)
    assert lru is None
    total = 48 * 3
    assert inf == pytest.approx(32 / total)  # only p2 reuses the 2 shared blocks


def test_lru_capacity_limits_reuse():
    a = list(range(16))
    b = list(range(100, 116))
    # capacity 1 block: a, b evicts a, a misses again
    _, lru = prefix_reuse([a, b, a], block=16, lru_capacity_blocks=1)
    assert lru == 0.0
    _, lru2 = prefix_reuse([a, b, a], block=16, lru_capacity_blocks=2)
    assert lru2 == pytest.approx(16 / 48)


def test_parse_app_log_and_openai_log_shapes():
    app = {
        "ts": 10.0,
        "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "q"}],
        "prompt_tokens": 50,
        "completion_tokens": 7,
        "latency_ms": 500,
        "stream": True,
        "model": "lab",
    }
    r = parse_record(app)
    assert r is not None and r.system == "S" and r.prompt_tokens == 50 and r.stream is True
    oa = {
        "request": {
            "model": "gpt",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
        "response": {"usage": {"prompt_tokens": 3, "completion_tokens": 4}},
    }
    r2 = parse_record(oa)
    assert r2 is not None and r2.completion_tokens == 4 and r2.stream is False and r2.model == "gpt"
    assert parse_record({"no": "messages"}) is None


def _rec(ts, lat, sys_="SYSTEM " * 50, q="question", stream=True):
    msgs = [{"role": "system", "content": sys_}, {"role": "user", "content": q}]
    r = parse_record(
        {
            "ts": ts,
            "messages": msgs,
            "completion_tokens": 20,
            "latency_ms": lat,
            "stream": stream,
            "model": "lab",
        }
    )
    assert isinstance(r, TraceRecord)
    return r


def test_fingerprint_shared_system_prompt_and_concurrency():
    # three requests: [0,1]s, [0.5,1.5]s, [3,4]s  -> peak concurrency 2
    recs = [_rec(1.0, 1000, q="a b c"), _rec(1.5, 1000, q="d e f"), _rec(4.0, 1000, q="g h i")]
    spec = fingerprint(recs, name="t")
    assert spec.synthetic is False and spec.n_observed == 3
    assert spec.arrival.peak_concurrency == 2
    assert spec.prefix.reuse_ratio_infinite is not None and spec.prefix.reuse_ratio_infinite > 0.5
    (g,) = spec.prefix.groups
    assert g.share == pytest.approx(1.0) and g.tokens > 50
    assert spec.streaming_ratio == 1.0
    assert spec.traffic_class and spec.traffic_class[0].value == "interactive"
    assert "regex-approx" in (spec.tokenizer or "")


def test_dynamic_head_destroys_measured_reuse():
    stable = [_rec(i, 100, q=f"q{i}") for i in range(1, 20)]
    unstable = [
        _rec(i, 100, sys_=f"Request {i} at {i * 7}\n" + "SYSTEM " * 50, q=f"q{i}")
        for i in range(1, 20)
    ]
    s = fingerprint(stable).prefix.reuse_ratio_infinite
    u = fingerprint(unstable).prefix.reuse_ratio_infinite
    assert s is not None and u is not None
    assert s > 0.8 and u < 0.1


def test_load_traces_skips_bad_lines(tmp_path):
    p = tmp_path / "t.jsonl"
    good = {"messages": [{"role": "user", "content": "x"}], "completion_tokens": 1}
    p.write_text(
        "not json\n" + json.dumps(good) + "\n\n" + json.dumps({"x": 1}) + "\n", encoding="utf-8"
    )
    assert len(load_traces(p)) == 1
