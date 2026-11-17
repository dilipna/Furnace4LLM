"""Deterministic task checks for model output. No model, network or judge is involved.

Each rule returns a pass/fail and a short reason code; the output text itself is never
part of the result, so evaluation records can keep hashes instead of raw responses.
These are rule checks of task answers, not semantic or human quality judgements.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Method = Literal["exact", "normalized", "contains", "regex", "numeric", "choice", "json_fields"]
JsonScalar = str | int | float | bool | None
MAX_OUTPUT_FOR_REGEX = 16000
_NUMBER = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_FENCE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$")


class ScoringRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Method
    value: str | None = Field(default=None, max_length=400)
    values: list[str] | None = Field(default=None, max_length=8)
    number: float | None = None
    tolerance: float = Field(default=0, ge=0, le=1e9)
    options: list[str] | None = Field(default=None, min_length=2, max_length=10)
    fields: dict[str, JsonScalar] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def complete(self) -> ScoringRule:
        need = {
            "exact": (),
            "normalized": (),
            "contains": ("values",),
            "regex": ("value",),
            "numeric": ("number",),
            "choice": ("options", "value"),
            "json_fields": ("fields",),
        }[self.method]
        for name in need:
            if getattr(self, name) in (None, [], {}):
                raise ValueError(f"{self.method} scoring requires {name}")
        if self.values is not None and any(not v or len(v) > 200 for v in self.values):
            raise ValueError("contains values must be 1-200 characters")
        if self.options is not None:
            if any(not o or len(o) > 100 for o in self.options):
                raise ValueError("choice options must be 1-100 characters")
            if normalize(self.value or "") not in {normalize(o) for o in self.options}:
                raise ValueError("choice answer must be one of the options")
        if self.method == "regex":
            if len(self.value or "") > 200:
                raise ValueError("regex patterns are limited to 200 characters")
            try:
                re.compile(self.value or "")
            except re.error:
                raise ValueError("regex pattern does not compile") from None
        if self.fields is not None and any(not k or len(k) > 100 for k in self.fields):
            raise ValueError("json field names must be 1-100 characters")
        return self


def normalize(text: str) -> str:
    """Case-, width- and whitespace-insensitive form without surrounding punctuation."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = " ".join(value.split())
    return value.strip(" \t\n\"'`.,;:!?()[]{}*_")


def _numbers(text: str) -> list[float]:
    return [float(m.group().replace(",", "")) for m in _NUMBER.finditer(text)]


def _json_object(text: str) -> Any:
    stripped = _FENCE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no object")
    return json.loads(stripped[start : end + 1])


def score(rule: ScoringRule | None, output: str, expected_output: str | None) -> tuple[str, str]:
    """Return (status, reason). Status is pass, fail or unscored."""
    if rule is None:
        if expected_output is None:
            return "unscored", "no_rule"
        return ("pass", "exact_match") if output == expected_output else ("fail", "exact_mismatch")
    method = rule.method
    if method == "exact":
        if expected_output is None:
            return "unscored", "no_expected_output"
        return ("pass", "exact_match") if output == expected_output else ("fail", "exact_mismatch")
    if method == "normalized":
        target = rule.value if rule.value is not None else expected_output
        if target is None:
            return "unscored", "no_expected_output"
        matched = normalize(output) == normalize(target)
        return ("pass", "normalized_match") if matched else ("fail", "normalized_mismatch")
    if method == "contains":
        text = normalize(output)
        missing = [v for v in rule.values or [] if normalize(v) not in text]
        return ("fail", "missing_required_text") if missing else ("pass", "contains_all")
    if method == "regex":
        if len(output) > MAX_OUTPUT_FOR_REGEX:
            return "fail", "output_too_long_for_regex"
        matched = re.fullmatch(rule.value or "", output.strip()) is not None
        return ("pass", "regex_match") if matched else ("fail", "regex_mismatch")
    if method == "numeric":
        found = _numbers(output)
        if not found:
            return "fail", "no_number_found"
        # The last number is the answer convention (e.g. "17 + 25 = 42").
        ok = abs(found[-1] - float(rule.number or 0)) <= rule.tolerance
        return ("pass", "number_within_tolerance") if ok else ("fail", "number_mismatch")
    if method == "choice":
        text = normalize(output)
        present = {
            normalize(option)
            for option in rule.options or []
            if re.search(r"(?<![\w])" + re.escape(normalize(option)) + r"(?![\w])", text)
        }
        if not present:
            return "fail", "no_option_found"
        if len(present) > 1:
            return "fail", "ambiguous_choice"
        chosen = present.pop()
        return (
            ("pass", "choice_match")
            if chosen == normalize(rule.value or "")
            else (
                "fail",
                "wrong_choice",
            )
        )
    # json_fields
    try:
        value = _json_object(output)
    except ValueError:
        return "fail", "invalid_json"
    if not isinstance(value, dict):
        return "fail", "json_not_object"
    for key, expected in (rule.fields or {}).items():
        if key not in value:
            return "fail", "json_field_missing"
        actual = value[key]
        if isinstance(expected, str):
            if not isinstance(actual, str) or normalize(actual) != normalize(expected):
                return "fail", "json_field_mismatch"
        elif isinstance(expected, bool) or expected is None:
            if actual is not expected:
                return "fail", "json_field_mismatch"
        elif (
            isinstance(actual, bool)
            or not isinstance(actual, int | float)
            or abs(float(actual) - float(expected)) > 1e-9
        ):
            return "fail", "json_field_mismatch"
    return "pass", "json_fields_match"
