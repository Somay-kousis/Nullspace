"""Evidence statistics, checked on hand-built logs with known answers.

Expected values come from the definitions in DESIGN.md, not from running code.
"""
import math

import numpy as np
import pytest

from nullspace.evidence import (exposure_adoption_rd, first_line_convergence,
                                fit_copying_w, occupancy)


def rev(name, label, time, body, prev=""):
    return {"name": name, "label": label, "time": time, "body": body, "prev_body": prev}


# ---- E2 exposure-adoption risk difference -------------------------------------

def test_rd_hand_computed():
    # 4 newcomers write to pages where the marker stood (exposed): 3 adopt.
    # 4 newcomers write where it did not: 1 adopts. RD = 0.75 - 0.25 = 0.5
    revs = []
    for i, adopt in enumerate([1, 1, 1, 0]):
        revs.append(rev(f"P{i}", f"e{i}", i, "R2 CONFIRMED" if adopt else "hello", prev="R1 CONFIRMED x"))
    for i, adopt in enumerate([1, 0, 0, 0]):
        revs.append(rev(f"Q{i}", f"u{i}", 10 + i, "R2 CONFIRMED" if adopt else "hello", prev="nothing"))
    out = exposure_adoption_rd(revs, "round_marker")
    assert out["rd"] == pytest.approx(0.5)
    assert out["n_exposed"] == 4 and out["n_unexposed"] == 4
    assert out["p_exposed"] == pytest.approx(0.75)
    assert out["p_unexposed"] == pytest.approx(0.25)


def test_rd_uses_first_revision_per_label_only():
    revs = [rev("P", "a", 1, "hello", prev="R1 CONFIRMED"),
            rev("P", "a", 2, "R2 CONFIRMED", prev="hello")]  # later rev by same label ignored
    out = exposure_adoption_rd(revs, "round_marker")
    assert out["n_exposed"] == 1 and out["p_exposed"] == 0.0


def test_rd_zero_when_adoption_independent_of_exposure():
    revs = []
    for i in range(10):
        revs.append(rev(f"E{i}", f"e{i}", i, "R2 CONFIRMED" if i % 2 else "x", prev="R1 CONFIRMED"))
        revs.append(rev(f"U{i}", f"u{i}", 100 + i, "R2 CONFIRMED" if i % 2 else "x", prev="none"))
    assert exposure_adoption_rd(revs, "round_marker")["rd"] == pytest.approx(0.0)


def test_rd_undefined_when_a_group_is_empty():
    revs = [rev("P", "a", 1, "R2 CONFIRMED", prev="R1 CONFIRMED")]
    out = exposure_adoption_rd(revs, "round_marker")
    assert out["rd"] is None


def test_rd_has_bootstrap_interval():
    revs = []
    for i in range(30):
        revs.append(rev(f"E{i}", f"e{i}", i, "R2 CONFIRMED" if i % 3 else "x", prev="R1 CONFIRMED"))
        revs.append(rev(f"U{i}", f"u{i}", 100 + i, "R2 CONFIRMED" if i % 3 == 0 else "x", prev="none"))
    out = exposure_adoption_rd(revs, "round_marker", n_boot=500, seed=0)
    lo, hi = out["ci95"]
    assert lo <= out["rd"] <= hi


# ---- E1 first-line format convergence ----------------------------------------

def test_convergence_first_vs_last_window():
    # window 0: 0/4 carry marker; window 1: 3/4 carry it -> convergence = 0.75
    revs = [rev("p", f"a{i}", i, "x") for i in range(4)]
    revs += [rev("p", f"b{i}", 100 + i, "R3 CONFIRMED" if i < 3 else "x") for i in range(4)]
    out = first_line_convergence(revs, "round_marker", n_windows=2)
    assert out["shares"] == pytest.approx([0.0, 0.75])
    assert out["convergence"] == pytest.approx(0.75)


def test_convergence_counts_each_label_once():
    revs = [rev("p", "a", 0, "x"), rev("p", "a", 200, "R3 CONFIRMED"), rev("p", "b", 200, "x")]
    out = first_line_convergence(revs, "round_marker", n_windows=2)
    assert out["n_per_window"] == [1, 1]


# ---- E3 copying-model fit ----------------------------------------------------

def test_copying_fit_recovers_known_weight():
    rng = np.random.default_rng(0)
    options = ["A", "B", "C", "D"]
    choices = []
    true_w = 0.7
    for _ in range(2000):
        share = dict(zip(options, rng.dirichlet(np.ones(4))))
        p = {o: (1 - true_w) / 4 + true_w * share[o] for o in options}
        pick = rng.choice(options, p=[p[o] for o in options])
        choices.append({"options": options, "visible_share": share, "choice": pick})
    out = fit_copying_w(choices)
    assert out["w"] == pytest.approx(true_w, abs=0.08)
    assert out["ll_gain"] > 0


def test_copying_fit_near_zero_when_choices_ignore_visibility():
    rng = np.random.default_rng(1)
    options = ["A", "B", "C", "D"]
    choices = []
    for _ in range(2000):
        share = dict(zip(options, rng.dirichlet(np.ones(4))))
        choices.append({"options": options, "visible_share": share, "choice": rng.choice(options)})
    out = fit_copying_w(choices)
    assert out["w"] < 0.1


# ---- E4 occupancy ------------------------------------------------------------

def test_occupancy_counts_distinct_labels_per_page():
    revs = [rev("A", "x", 1, ""), rev("A", "y", 2, ""), rev("A", "x", 3, ""), rev("B", "z", 4, "")]
    out = occupancy(revs)
    assert out["labels_per_page"] == {"A": 2, "B": 1}
    assert 0.0 <= out["gini"] <= 1.0


def test_adoption_reads_delta_not_inherited_body():
    # newcomer appends plain text to a page whose old text carries the marker:
    # body contains the marker, but the newcomer added none of it -> not adopted
    r = {"name": "P", "label": "n", "time": 1, "prev_body": "R1 CONFIRMED old",
         "body": "R1 CONFIRMED old\nhello", "delta": "hello"}
    out = exposure_adoption_rd([r], "round_marker", n_boot=0)
    assert out["n_exposed"] == 1 and out["p_exposed"] == 0.0


def test_unlabelled_revisions_are_not_newcomers():
    revs = [{"name": "P", "label": None, "time": 1, "prev_body": "", "body": "R1 CONFIRMED"},
            {"name": "Q", "label": None, "time": 2, "prev_body": "", "body": "x"}]
    out = exposure_adoption_rd(revs, "round_marker", n_boot=0)
    assert out["n_exposed"] + out["n_unexposed"] == 0


def test_gini_exact_value():
    # two pages with 1 and 2 distinct labels: Gini of [1, 2] = 1/6
    revs = [rev("A", "x", 1, ""), rev("B", "y", 2, ""), rev("B", "z", 3, "")]
    assert occupancy(revs)["gini"] == pytest.approx(1 / 6)


def test_unknown_previous_state_is_excluded_from_exposure():
    # Review F8: prev_body None = earlier revisions not published -> exposure unknown
    revs = [{"name": "P", "label": "a", "time": 1, "prev_body": None, "body": "R1 CONFIRMED"},
            {"name": "Q", "label": "b", "time": 2, "prev_body": "R1 CONFIRMED", "body": "x"}]
    out = exposure_adoption_rd(revs, "round_marker", n_boot=0)
    assert out["n_exposed"] == 1 and out["n_unexposed"] == 0
