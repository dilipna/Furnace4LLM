"""Tiny Prometheus text-format parser (enough for vLLM / SGLang /metrics).

Returns {metric_name: summed value across label sets}, skipping histogram
bucket/sum/count series and ``*_created`` timestamps.
"""

from __future__ import annotations

import math


def parse_prometheus(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "{" in line:
            name = line[: line.index("{")]
            rest = line[line.rindex("}") + 1 :].strip()
        else:
            name, _, rest = line.partition(" ")
        if name.endswith(("_bucket", "_created")):
            continue
        value_str = rest.split()[0] if rest else ""
        try:
            value = float(value_str)
        except ValueError:
            continue
        if math.isnan(value):
            continue
        out[name] = out.get(name, 0.0) + value
    return out
