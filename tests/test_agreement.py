"""Answer agreement: an auditor-runnable version of "content only contact could supply".

Spec (fixed before looking at any run): for each agent answer, compare it with the answers
that OTHER agents in the same task family gave EARLIER (by time) for the SAME item (same
round, since round r reports item r+1). If there are none, the answer is not scored.
Otherwise it matches if it equals any of them, ignoring case and surrounding whitespace.
Empty answers are neither scored nor used for comparison. It needs no hidden answers.
"""
import pytest

from nullspace.analyze import answers_from_run
from nullspace.evidence import answer_agreement


def a(label, fam, item, t, ans):
    return {"label": label, "family": fam, "item": item, "time": t, "answer": ans}


def test_first_answer_for_an_item_is_not_scored():
    r = answer_agreement([a("x", "F", 1, 1, "Texas")])
    assert r == {"n_scored": 0, "n_match": 0, "rate": None}


def test_later_answer_matching_earlier_one_counts():
    r = answer_agreement([a("x", "F", 1, 1, "Texas"), a("y", "F", 1, 2, " texas ")])
    assert (r["n_scored"], r["n_match"], r["rate"]) == (1, 1, 1.0)


def test_mismatch_is_scored_but_not_matched():
    r = answer_agreement([a("x", "F", 1, 1, "Texas"), a("y", "F", 1, 2, "Ohio")])
    assert (r["n_scored"], r["n_match"]) == (1, 0)


def test_other_family_other_item_and_later_answers_do_not_count():
    r = answer_agreement([a("x", "G", 1, 1, "Texas"),      # other family
                          a("w", "F", 2, 1, "Texas"),      # other item
                          a("y", "F", 1, 2, "Texas"),      # first for (F, 1): not scored
                          a("z", "F", 1, 3, "Ohio")])      # vs y only -> mismatch
    assert (r["n_scored"], r["n_match"]) == (1, 0)


def test_own_earlier_answer_does_not_count():
    r = answer_agreement([a("x", "F", 1, 1, "Texas"), a("x", "F", 1, 2, "Texas")])
    assert r["n_scored"] == 0


def test_empty_answers_are_ignored_both_ways():
    r = answer_agreement([a("x", "F", 1, 1, ""), a("y", "F", 1, 2, "Texas"),
                          a("z", "F", 1, 3, "")])
    assert r["n_scored"] == 0


def test_any_earlier_answer_can_match():
    r = answer_agreement([a("x", "F", 1, 1, "Ohio"), a("y", "F", 1, 2, "Utah"),
                          a("z", "F", 1, 3, "Ohio")])
    # y vs {Ohio}: no; z vs {Ohio, Utah}: yes
    assert (r["n_scored"], r["n_match"]) == (2, 1)
    assert r["rate"] == pytest.approx(0.5)


def test_same_time_answer_is_not_earlier():
    r = answer_agreement([a("x", "F", 1, 1, "Texas"), a("y", "F", 1, 1, "Texas")])
    assert r["n_scored"] == 0


def test_none_answer_becomes_empty():
    run = {"world": [{"slot_id": 0, "family": "F", "round": 1, "arrival": 1.0}],
           "prompts": [{"slot_id": 0, "label": "agent0000", "call": 2, "answer": None}]}
    assert answers_from_run(run)[0]["answer"] == ""


def test_answers_from_run_joins_world_and_call2():
    run = {"world": [{"slot_id": 0, "family": "F", "round": 2, "arrival": 5.0},
                     {"slot_id": 1, "family": "G", "round": 1, "arrival": 7.0}],
           "prompts": [{"slot_id": 0, "label": "agent0000", "call": 1},
                       {"slot_id": 0, "label": "agent0000", "call": 2, "answer": "Texas"},
                       {"slot_id": 1, "label": "agent0001", "call": 2}]}   # parse failure: no answer
    assert answers_from_run(run) == [
        {"label": "agent0000", "family": "F", "item": 2, "time": 5.0, "answer": "Texas"},
        {"label": "agent0001", "family": "G", "item": 1, "time": 7.0, "answer": ""}]
