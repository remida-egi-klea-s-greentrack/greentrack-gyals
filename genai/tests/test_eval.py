"""Tests for the eval checks (no AWS).

Variables: CASE_NUM, CASE_REFUSE - minimal cases of each check type.
"""

from genai.eval.run_eval import CASES, check, matches, numbers_in

CASE_NUM = {"id": "n", "question": "q", "tools": ["peak_hours"], "numbers": "SELECT 1"}
CASE_REFUSE = {"id": "r", "question": "q", "refuse": True}


def test_numbers_in_reads_thousands_and_decimals():
    assert numbers_in("Total 1,234.5 kWh on 2010-11-20, peak 5.627 kWh") == [1234.5, 2010, 11, 20, 5.627]


def test_matches_allows_rounding_only():
    assert matches(5.63, [5.627]) and matches(650.4, [650.0])
    assert not matches(1.13, [1.23])


def test_number_case_passes_and_fails():
    reply = {"answer": "Peak was 5.627 kWh.", "tools_used": ["peak_hours"]}
    assert check(CASE_NUM, reply, [5.63]) == []
    assert check(CASE_NUM, reply, [3.26]) == ["expected 3.26 not in answer"]
    assert "used" in check(CASE_NUM, {"answer": "5.627", "tools_used": ["hourly_profile"]}, [5.63])[0]


def test_refusal_needs_no_tools_and_a_refusal():
    assert check(CASE_REFUSE, {"answer": "I can only answer questions about energy.", "tools_used": []}) == []
    assert len(check(CASE_REFUSE, {"answer": "Sure, here it is.", "tools_used": ["peak_hours"]})) == 2


def test_error_reply_fails():
    assert check(CASE_NUM, {"error": "boom"}, [1.0]) == ["error: boom"]


def test_case_ids_are_unique_and_each_has_one_check():
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in CASES:
        assert sum(k in c for k in ("numbers", "text", "refuse")) == 1, c["id"]
