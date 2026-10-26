"""Validity of the manipulation.

Spec (DESIGN.md, Conditions): prompt text, tool descriptions and JSON schema are
byte-identical between V and B; only board content differs. In B, no prompt may
ever contain text written by another agent (true transmission = 0).
"""
import json

from nullspace.board import Board
from nullspace.prompts import build_call1, build_call2
from nullspace.sim import run_condition
from nullspace.task import make_world


class EchoBackend:
    """Deterministic fake model: writes a unique, traceable marker per agent."""

    def __init__(self):
        self.prompts = []
        self.n = 0

    def complete(self, prompt, **kw):
        self.prompts.append(prompt)
        self.n += 1
        if '"open_page"' in prompt:
            return json.dumps({"open_page": "SharedPage"})
        return json.dumps({"answer": "Ohio", "page_name": "SharedPage",
                           "text": f"UNIQUEMARK{self.n} R2 CONFIRMED Ohio cohort"})


def test_call1_identical_between_conditions_when_board_empty():
    w = make_world(seed=1, families=2, cohorts=2, rounds=2)
    s = w.schedule()[0]
    assert build_call1(s, Board("visible").feed()) == build_call1(s, Board("blind").feed())


def test_call2_identical_between_conditions_when_page_missing():
    w = make_world(seed=1, families=2, cohorts=2, rounds=2)
    s = w.schedule()[0]
    v, b = Board("visible"), Board("blind")
    assert build_call2(s, "X", v.read("X")) == build_call2(s, "X", b.read("X"))


def test_call1_requests_json_with_open_page_key():
    w = make_world(seed=1, families=1, cohorts=1, rounds=1)
    assert '"open_page"' in build_call1(w.schedule()[0], [])


def test_call2_requests_answer_page_name_text():
    w = make_world(seed=1, families=1, cohorts=1, rounds=1)
    p = build_call2(w.schedule()[0], "X", "")
    for key in ('"answer"', '"page_name"', '"text"'):
        assert key in p


def test_blind_condition_has_zero_leakage():
    be = EchoBackend()
    out = run_condition("blind", seed=3, backend=be, families=2, cohorts=3, rounds=2)
    written = [r["body"] for r in out["revisions"]]
    assert written, "blind run must still store writes"
    for p in be.prompts:
        for text in written:
            assert text not in p
        assert "UNIQUEMARK" not in p


def test_visible_condition_does_transmit():
    """Positive control on the harness itself: with the same fake model, V
    prompts must contain earlier agents' text."""
    be = EchoBackend()
    run_condition("visible", seed=3, backend=be, families=2, cohorts=3, rounds=2)
    assert any("UNIQUEMARK" in p for p in be.prompts)


def test_run_logs_prompts_and_meta():
    be = EchoBackend()
    out = run_condition("blind", seed=3, backend=be, families=1, cohorts=2, rounds=2)
    assert len(out["prompts"]) == len(be.prompts)
    assert out["meta"]["condition"] == "blind"
    assert out["meta"]["seed"] == 3


def test_malformed_model_output_is_recorded_not_crashing():
    class Bad(EchoBackend):
        def complete(self, prompt, **kw):
            self.prompts.append(prompt)
            return "not json at all"

    out = run_condition("visible", seed=1, backend=Bad(), families=1, cohorts=1, rounds=2)
    assert out["meta"]["parse_failures"] > 0


def test_null_answer_is_not_counted_as_answered():
    class NullAns(EchoBackend):
        def complete(self, prompt, **kw):
            self.prompts.append(prompt)
            if '"open_page"' in prompt:
                return json.dumps({"open_page": None})
            return json.dumps({"answer": None, "page_name": "P", "text": "t"})
    out = run_condition("blind", seed=1, backend=NullAns(), families=1, cohorts=1, rounds=2)
    assert out["meta"]["answered"] == 0


def test_paired_seeds_give_identical_prompts_when_board_contents_match():
    """Review F1: V and B with the same seed see the same task text (first call, empty board)."""
    be_v, be_b = EchoBackend(), EchoBackend()
    run_condition("visible", seed=5, backend=be_v, families=2, cohorts=2, rounds=2)
    run_condition("blind", seed=5, backend=be_b, families=2, cohorts=2, rounds=2)
    assert be_v.prompts[0] == be_b.prompts[0]
