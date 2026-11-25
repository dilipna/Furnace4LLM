"""Rule checks are deterministic and never pass on missing or ambiguous answers."""

import pytest
from furnace.runtime.scoring import ScoringRule, normalize, score
from pydantic import ValidationError


def rule(**kwargs):
    return ScoringRule.model_validate(kwargs)


def test_without_rule_exact_expectation_is_used_and_description_stays_unscored():
    assert score(None, "a", "a") == ("pass", "exact_match")
    assert score(None, "a ", "a") == ("fail", "exact_mismatch")
    assert score(None, "anything", None) == ("unscored", "no_rule")


def test_normalized_ignores_case_width_whitespace_and_surrounding_punctuation():
    assert normalize("  “Acknowledged.”  ") != ""
    assert (
        score(rule(method="normalized", value="acknowledged"), " Acknowledged. ", None)[0] == "pass"
    )
    assert score(rule(method="normalized", value="desserts"), "dessert", None)[0] == "fail"
    assert score(rule(method="normalized"), "x", None) == ("unscored", "no_expected_output")


@pytest.mark.parametrize("output", ["¡Buenos días!", "¿Buenos días?", "  ¡Buenos días!  "])
def test_normalized_spanish_surrounding_punctuation(output):
    spanish = rule(method="normalized", value="Buenos días.")
    assert score(spanish, output, None)[0] == "pass"
    assert score(spanish, "Good morning.", None)[0] == "fail"


@pytest.mark.parametrize(
    ("output", "status"),
    [("42", "pass"), ("The answer is 42.", "pass"), ("17 + 25 = 42", "pass"), ("1,042", "fail"),
     ("forty-two", "fail"), ("42.0", "pass"), ("-42", "fail")],
)  # fmt: skip
def test_numeric_uses_the_last_number(output, status):
    assert score(rule(method="numeric", number=42), output, None)[0] == status


def test_numeric_ignores_numbers_copied_from_the_question():
    # Observed false negative (Granite 4.0 H 350M, 2026-11-17): a correct answer that
    # restated the question was read as "3" under the plain last-number convention.
    convert = rule(method="numeric", number=180)
    question = "How many minutes are in 3 hours? Reply with only the number."
    assert score(convert, "There are 180 minutes in 3 hours.", None, question)[0] == "pass"
    assert score(convert, "3 hours", None, question) == ("fail", "number_mismatch")
    times = rule(method="numeric", number=5)
    assert score(times, "5", None, "What is 5 times 1?")[0] == "pass"
    assert score(times, "5 times 1 is 5", None, "What is 5 times 1?")[0] == "pass"


def test_numeric_tolerance_and_missing_number():
    assert (
        score(rule(method="numeric", number=3.14, tolerance=0.01), "about 3.141", None)[0] == "pass"
    )
    assert score(rule(method="numeric", number=1), "none", None) == ("fail", "no_number_found")


@pytest.mark.parametrize(
    ("output", "expected"),
    [("B", ("pass", "choice_match")), ("B) Mars", ("pass", "choice_match")),
     ("The answer is b.", ("pass", "choice_match")), ("A or B", ("fail", "ambiguous_choice")),
     ("Mars", ("fail", "no_option_found")), ("C", ("fail", "wrong_choice"))],
)  # fmt: skip
def test_choice_requires_exactly_one_option_as_a_whole_word(output, expected):
    value = rule(method="choice", options=["A", "B", "C", "D"], value="B")
    assert score(value, output, None) == expected


def test_choice_words_do_not_match_inside_other_words():
    value = rule(method="choice", options=["yes", "no"], value="yes")
    assert score(value, "Yes, 17 is prime.", None)[0] == "pass"
    assert score(value, "eyes nothing", None) == ("fail", "no_option_found")


def test_contains_regex_and_json_fields():
    assert score(rule(method="contains", values=["Paris"]), "It is paris.", None)[0] == "pass"
    assert score(rule(method="contains", values=["Paris", "France"]), "Paris", None)[0] == "fail"
    assert score(rule(method="regex", value="(?i)#?ff0000"), " #FF0000 ", None)[0] == "pass"
    assert score(rule(method="regex", value="(?i)#?ff0000"), "#FF0000 is red", None)[0] == "fail"
    fields = rule(method="json_fields", fields={"name": "Ana", "age": 30})
    assert score(fields, '```json\n{"name": "ana", "age": 30}\n```', None)[0] == "pass"
    assert score(fields, '{"name": "Ana", "age": "30"}', None) == ("fail", "json_field_mismatch")
    assert score(fields, '{"name": "Ana"}', None) == ("fail", "json_field_missing")
    assert score(fields, "not json", None) == ("fail", "invalid_json")
    flag = rule(method="json_fields", fields={"ok": True})
    assert score(flag, '{"ok": 1}', None)[0] == "fail"


@pytest.mark.parametrize(
    "bad",
    [{"method": "contains"}, {"method": "regex", "value": "("}, {"method": "numeric"},
     {"method": "choice", "options": ["A", "B"], "value": "C"}, {"method": "json_fields"},
     {"method": "regex", "value": "a" * 201}, {"method": "unknown"},
     {"method": "exact", "extra": 1}],
)  # fmt: skip
def test_incomplete_or_unsafe_rules_are_rejected(bad):
    with pytest.raises(ValidationError):
        ScoringRule.model_validate(bad)
