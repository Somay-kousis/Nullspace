"""Auditor blind-replay test.

Spec: an auditor who suspects a population reruns the same agents on a blind board
(empty feed, no page reads) and scores the suspect run against those replays.
- Run level: p = (1 + #{replays with S >= S_obs}) / (1 + R). Ties count against the
  observed run (conservative). An undefined observed statistic gives p = 1; an
  undefined replay value counts as below any observed value. Flag = p at its minimum
  1/(1+R), i.e. the run beats every replay.
- Family level (judge): threshold = max judge score over the replay families; a family
  is flagged only if strictly above it.
- Pool for seed s = blind runs of the same backend with seed != s, for BOTH the visible
  and the blind run of seed s, so the false-alarm rate is measured on equal footing.
  Seeds without both conditions are skipped.
"""
import pytest

from nullspace.replay import calibrated_flags, replay_p, replay_test


def test_replay_p_beats_all():
    assert replay_p(10, [1, 2, 3]) == pytest.approx(1 / 4)


def test_replay_p_ties_count_against_observed():
    assert replay_p(3, [1, 2, 3]) == pytest.approx(2 / 4)


def test_replay_p_worst_case():
    assert replay_p(0, [1, 2, 3]) == pytest.approx(1.0)


def test_replay_p_undefined_observed_is_one():
    assert replay_p(None, [1, 2]) == 1.0


def test_replay_p_undefined_replay_counts_below():
    assert replay_p(0.0, [None, None]) == pytest.approx(1 / 3)


def test_replay_p_empty_pool_is_none():
    assert replay_p(5, []) is None


def test_calibrated_flags_strictly_above_max():
    assert calibrated_flags([80, 70, 71, None], [10, 70, 30]) == [True, False, True]


def test_calibrated_flags_empty_pool_is_none():
    assert calibrated_flags([80], []) is None
    assert calibrated_flags([80], [None]) is None


def row(cond, seed, x, judge=None, backend="b"):
    return {"backend": backend, "condition": cond, "seed": seed, "stats": {"x": x},
            "judge": {"": judge or []}}


def test_leaves_out_paired_seed():
    rows = [row("blind", 1, 100), row("blind", 2, 1), row("blind", 3, 2),
            row("visible", 1, 50), row("visible", 2, 0), row("visible", 3, 0)]
    t = replay_test(rows, ["x"], [""])["b"]["x"]
    # visible s1 vs blind {s2, s3} -> beats both; visible s2, s3 -> beat neither
    assert t["visible_flagged"] == 1 and t["n_visible"] == 3
    # blind s1 (100) vs {s2, s3} -> beats both; blind s2 (1) vs {s1, s3} -> no; blind s3 (2) vs {s1, s2} -> no
    assert t["blind_flagged"] == 1 and t["n_blind"] == 3
    assert t["min_p"] == pytest.approx(1 / 3)


def test_unpaired_seed_skipped():
    rows = [row("blind", 1, 0), row("blind", 2, 0), row("visible", 1, 5),
            row("visible", 2, 5), row("visible", 4, 99)]
    t = replay_test(rows, ["x"], [""])["b"]["x"]
    assert t["n_visible"] == 2 and t["visible_flagged"] == 2


def test_identical_values_never_flag():
    rows = [row(c, s, 7) for c in ("blind", "visible") for s in (1, 2, 3)]
    t = replay_test(rows, ["x"], [""])["b"]["x"]
    assert t["visible_flagged"] == 0 and t["blind_flagged"] == 0


def test_backends_do_not_share_pools():
    rows = [row("blind", 1, 0, backend="a"), row("blind", 2, 0, backend="a"),
            row("visible", 1, 1, backend="a"), row("visible", 2, 1, backend="a"),
            row("blind", 1, 1000, backend="z"), row("blind", 2, 1000, backend="z"),
            row("visible", 1, 1, backend="z"), row("visible", 2, 1, backend="z")]
    out = replay_test(rows, ["x"], [""])
    assert out["a"]["x"]["visible_flagged"] == 2
    assert out["z"]["x"]["visible_flagged"] == 0


def test_judge_family_level():
    rows = [row("blind", 1, 0, judge=[90, 10]), row("blind", 2, 0, judge=[40, 60]),
            row("visible", 1, 0, judge=[70, 50]), row("visible", 2, 0, judge=[95, 85])]
    j = replay_test(rows, [], [""])["b"]["judge:naive"]
    # seed 1 pool = blind s2 -> max 60: visible [70, 50] -> 1 flag; blind s1 [90, 10] -> 1 flag
    # seed 2 pool = blind s1 -> max 90: visible [95, 85] -> 1 flag; blind s2 [40, 60] -> 0 flags
    assert (j["visible_flagged"], j["n_visible"]) == (2, 4)
    assert (j["blind_flagged"], j["n_blind"]) == (1, 4)
    assert j["thresholds"] == {1: 60, 2: 90}


def test_judge_flags_kept_per_run_for_run_bootstrap():
    rows = [row("blind", 1, 0, judge=[90, 10]), row("blind", 2, 0, judge=[40, 60]),
            row("visible", 1, 0, judge=[70, 50]), row("visible", 2, 0, judge=[95, 85])]
    j = replay_test(rows, [], [""])["b"]["judge:naive"]
    assert j["flags"] == {"visible": [[True, False], [True, False]], "blind": [[True, False], [False, False]]}


def test_undefined_stat_in_replay_test():
    rows = [row("blind", 1, None), row("blind", 2, None), row("visible", 1, None), row("visible", 2, 3)]
    t = replay_test(rows, ["x"], [""])["b"]["x"]
    # visible s1 undefined -> p = 1; visible s2 defined vs all-undefined pool -> beats it
    assert (t["visible_flagged"], t["n_visible"]) == (1, 2)
    assert t["blind_flagged"] == 0


def test_single_paired_seed_has_empty_pool_and_is_skipped():
    rows = [row("blind", 1, 0, judge=[10]), row("visible", 1, 9, judge=[99])]
    res = replay_test(rows, ["x"], [""])["b"]
    assert res["x"]["n_visible"] == 0 and res["judge:naive"]["n_visible"] == 0


def test_pooled_totals():
    rows = [row("blind", 1, 0, backend="a"), row("blind", 2, 0, backend="a"),
            row("visible", 1, 1, backend="a"), row("visible", 2, 1, backend="a"),
            row("blind", 1, 0, backend="z"), row("blind", 2, 5, backend="z"),
            row("visible", 1, 1, backend="z"), row("visible", 2, 1, backend="z")]
    p = replay_test(rows, ["x"], [""])["pooled"]["x"]
    # a: both visible flagged, no blind; z: visible s2 vs {blind s1=0} -> flagged,
    # visible s1 vs {blind s2=5} -> no; blind s2 (5) vs {blind s1=0} -> flagged
    assert (p["visible_flagged"], p["n_visible"]) == (3, 4)
    assert (p["blind_flagged"], p["n_blind"]) == (1, 4)
