import numpy as np

from furnace_bench.generator import build_requests, sample_lengths
from furnace_bench.schema import BenchPlan, LengthMode
from furnace_bench.workload_spec import (
    Distribution,
    PrefixGroup,
    PrefixStats,
    WorkloadSource,
    WorkloadSpec,
)


def _spec(**kw):
    return WorkloadSpec(
        source=WorkloadSource.synthetic,
        synthetic=True,
        input_tokens=Distribution(p50=300, p95=900, max=2000),
        output_tokens=Distribution(p50=64, mean=64),
        **kw,
    )


def test_all_prompts_unique_and_reproducible():
    plan = BenchPlan(seed=7)
    a = build_requests(_spec(), plan, 300)
    b = build_requests(_spec(), plan, 300)
    users = [r.messages[-1]["content"] for r in a]
    assert len(set(users)) == 300
    assert [r.messages for r in a] == [r.messages for r in b]


def test_prefix_group_shares_identical_system_prompt():
    spec = _spec(prefix=PrefixStats(groups=[PrefixGroup(prefix_hash="sys", tokens=200, share=1.0)]))
    reqs = build_requests(spec, BenchPlan(seed=1), 50)
    systems = {r.messages[0]["content"] for r in reqs}
    assert len(systems) == 1
    assert all(r.messages[0]["role"] == "system" and r.prefix_group == "sys" for r in reqs)
    assert len(next(iter(systems)).split()) == 200


def test_prefix_share_mixes_groups():
    spec = _spec(prefix=PrefixStats(groups=[PrefixGroup(prefix_hash="sys", tokens=50, share=0.5)]))
    reqs = build_requests(spec, BenchPlan(seed=3), 400)
    frac = sum(r.prefix_group == "sys" for r in reqs) / 400
    assert 0.4 < frac < 0.6


def test_lognormal_lengths_track_p50_p95():
    rng = np.random.default_rng(0)
    x = sample_lengths(Distribution(p50=300, p95=900, max=5000), 20000, rng)
    assert abs(np.percentile(x, 50) - 300) / 300 < 0.05
    assert abs(np.percentile(x, 95) - 900) / 900 < 0.08


def test_fixed_vs_natural_max_tokens():
    fixed = build_requests(_spec(), BenchPlan(seed=1, length_mode=LengthMode.fixed), 5)
    natural = build_requests(_spec(), BenchPlan(seed=1, length_mode=LengthMode.natural), 5)
    assert all(r.max_tokens == 64 for r in fixed)
    assert all(r.max_tokens >= 128 for r in natural)
