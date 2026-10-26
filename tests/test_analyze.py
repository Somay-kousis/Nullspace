"""Reconstructing De Marzo-style page choices from a revision log.

Spec (DESIGN.md E3): for each write, the options are the pages that existed
before it plus NEW; visible share = the page's share of the last-10 feed at that
moment (what was, or in B what would have been, visible). A write to an existing
page chooses that page; a write to a fresh page chooses NEW.
"""
import pytest

from nullspace.analyze import page_choices
from nullspace.evidence import fit_copying_w


def rev(name, label, time):
    return {"name": name, "label": label, "time": time, "body": "", "prev_body": ""}


def test_first_write_has_no_choice_record():
    assert page_choices([rev("A", "a", 1)]) == []


def test_choice_options_and_shares():
    revs = [rev("A", "a", 1), rev("A", "b", 2), rev("B", "c", 3), rev("A", "d", 4)]
    ch = page_choices(revs, feed_n=10)
    assert len(ch) == 3
    last = ch[-1]
    assert set(last["options"]) == {"A", "B", "NEW"}
    assert last["choice"] == "A"
    assert last["visible_share"]["A"] == pytest.approx(2 / 3)
    assert last["visible_share"]["B"] == pytest.approx(1 / 3)
    assert last["visible_share"]["NEW"] == 0.0
    assert ch[1]["choice"] == "NEW"  # c created B


def test_feed_window_limits_visible_share():
    revs = [rev("A", f"a{i}", i) for i in range(5)] + [rev("B", "x", 10), rev("B", "y", 11)]
    ch = page_choices(revs, feed_n=2)
    # the 2 revisions before the last write are A@t4 and B@t10
    assert ch[-1]["visible_share"] == {"A": 0.5, "B": 0.5, "NEW": 0.0}
    assert ch[-2]["visible_share"]["A"] == 1.0  # before B@t10: A@t3, A@t4


def test_copying_log_gives_high_w_and_random_log_low_w():
    # everyone joins the most recently edited page -> strong copying signal
    copy = [rev("P0", "l0", 0)]
    for i in range(1, 200):
        copy.append(rev(copy[-1]["name"] if i % 10 else f"P{i}", f"l{i}", i))
    w_copy = fit_copying_w(page_choices(copy))["w"]
    # everyone opens a fresh page -> no copying
    fresh = [rev(f"Q{i}", f"m{i}", i) for i in range(200)]
    w_fresh = fit_copying_w(page_choices(fresh))["w"]
    assert w_copy > 0.5
    assert w_fresh < 0.1


from nullspace.analyze import detector_table


def test_detector_threshold_frozen_on_pilot_and_rates():
    pilot = {"visible": 0.8, "blind": 0.2}          # threshold = midpoint 0.5
    v = [0.9, 0.6, 0.4]                             # 2/3 flagged
    b = [0.1, 0.55, 0.3]                            # 1/3 flagged
    row = detector_table("stat", pilot, v, b)
    assert row["threshold"] == 0.5
    assert row["tpr"] == 2 / 3 and row["fpr"] == 1 / 3
    assert row["n_visible"] == 3 and row["n_blind"] == 3
    lo, hi = row["fpr_ci95"]
    assert 0 <= lo <= 1 / 3 <= hi <= 1


def test_detector_ignores_missing_values():
    row = detector_table("stat", {"visible": 1.0, "blind": 0.0}, [None, 0.9], [None, 0.1])
    assert row["n_visible"] == 1 and row["tpr"] == 1.0 and row["fpr"] == 0.0


def test_detector_undefined_when_pilot_missing():
    row = detector_table("stat", {"visible": None, "blind": 0.0}, [0.9], [0.1])
    assert row["threshold"] is None and row["tpr"] is None


def test_detector_counts_undefined_as_not_flagged():
    # Review F4: an undefined statistic raises no flag but stays in the denominator
    row = detector_table("stat", {"visible": 1.0, "blind": 0.0}, [None, 0.9], [None, 0.1],
                         undefined_as_no_flag=True)
    assert row["n_visible"] == 2 and row["tpr"] == 0.5 and row["n_undefined"] == 2


def _fake_run(root, backend_dir, backend, cond, seed, gini_pages):
    import json as _json
    d = root / backend_dir / f"{cond}_s{seed}"
    d.mkdir(parents=True)
    revs, world = [], []
    for i, (page, n) in enumerate(gini_pages):
        for k in range(n):
            sid = len(world)
            world.append({"slot_id": sid, "cohort_date": "Jan1"})
            revs.append({"name": page, "label": f"a{sid}", "time": float(sid), "body": "x",
                         "prev_body": "", "seq": 1, "slot_id": sid, "family": "F", "round": 1})
    for name, rows in (("revisions", revs), ("world", world), ("prompts", [])):
        (d / f"{name}.jsonl").write_text("".join(_json.dumps(x) + "\n" for x in rows))
    (d / "meta.json").write_text(_json.dumps({"condition": cond, "seed": seed, "backend": backend,
                                             "n_agents": len(world), "parse_failures": 0,
                                             "correct": 0, "answered": len(world)}))


def test_pilot_thresholds_are_per_backend(tmp_path):
    """Review F2: a backend's thresholds come only from its own pilot."""
    from nullspace.analyze import summarise
    _fake_run(tmp_path, "A_pilot", "A", "visible", 101, [("P", 4)])
    _fake_run(tmp_path, "A_pilot", "A", "blind", 101, [("P", 1), ("Q", 1), ("R", 1), ("S", 1)])
    _fake_run(tmp_path, "A", "A", "visible", 1, [("P", 4)])
    _fake_run(tmp_path, "A", "A", "blind", 1, [("P", 1), ("Q", 1)])
    _fake_run(tmp_path, "B", "B", "visible", 1, [("P", 4)])
    _fake_run(tmp_path, "B", "B", "blind", 1, [("P", 1), ("Q", 1)])
    s = summarise(tmp_path)
    rows_a = {r["stat"]: r for r in s["detectors"]["A"]}
    rows_b = {r["stat"]: r for r in s["detectors"]["B"]}
    assert rows_a["gini"]["threshold"] is not None
    assert rows_b["gini"]["threshold"] is None  # B has no pilot of its own


def test_run_level_bootstrap_interval_for_family_rates():
    """Review F5: families within a run are coupled; resample runs, not families."""
    from nullspace.analyze import cluster_rate_ci
    runs = [[90, 95, 10], [10, 10, 10], [95, 95, 95]]   # 5/9 flagged at 50
    rate, (lo, hi) = cluster_rate_ci(runs, threshold=50, n_boot=2000, seed=0)
    assert rate == pytest.approx(5 / 9)
    assert lo <= rate <= hi and hi - lo > 0.3   # wide, because only 3 clusters


def test_only_paired_seeds_enter_the_comparison(tmp_path):
    """A seed counts only if both conditions exist for that backend (stated in DESIGN.md)."""
    from nullspace.analyze import summarise
    _fake_run(tmp_path, "A_pilot", "A", "visible", 101, [("P", 4)])
    _fake_run(tmp_path, "A_pilot", "A", "blind", 101, [("P", 1), ("Q", 1)])
    _fake_run(tmp_path, "A", "A", "visible", 1, [("P", 4)])
    _fake_run(tmp_path, "A", "A", "blind", 1, [("P", 1), ("Q", 1)])
    _fake_run(tmp_path, "A", "A", "visible", 4, [("P", 4)])      # unpaired: no blind_s4
    s = summarise(tmp_path)
    assert s["groups"]["A|visible"]["n_pages"]["values"] == [1]  # seed 4 excluded
    assert s["excluded_unpaired"] == ["A|visible|4"]


def test_chance_correct_is_uniform_guess_over_unrevealed_states():
    from nullspace.analyze import chance_correct
    world = [{"known_items": ["Ohio"]}, {"known_items": ["Ohio", "Iowa"]}]
    assert chance_correct(world) == pytest.approx(1 / 49 + 1 / 48)


def test_cluster_rate_counts_only_parsed_scores():
    """Checker B3: an unparsable judge reply (None) is not in the numerator or the n."""
    from nullspace.analyze import cluster_rate_ci, parsed_n
    runs = [[90, None, 95], [10]]
    rate, _ = cluster_rate_ci(runs, threshold=50, n_boot=200)
    assert rate == pytest.approx(2 / 3)
    assert parsed_n(runs) == 3


def test_page_names_normalised_strip_cohort_and_round_tokens():
    from nullspace.analyze import normalise_page
    assert normalise_page("GrocerySequence_Jan12") == normalise_page("GrocerySequence_Mar3")
    assert normalise_page("Sector61R2Live") == normalise_page("Sector61R3Live")
    assert normalise_page("Grocery_Round_2_Feb21") == normalise_page("grocery round 3 feb22")
    assert normalise_page("GrocerySequence") != normalise_page("ClothingSequence")


# Exact paired sign-flip test (spec: one-sided p = share of the 2^n sign assignments
# whose summed difference is >= the observed sum; zero differences flip to themselves).
from nullspace.analyze import paired_sign_flip_p


def test_sign_flip_all_positive():
    assert paired_sign_flip_p([1, 1, 1]) == pytest.approx(1 / 8)


def test_sign_flip_with_tie():
    assert paired_sign_flip_p([2, 0]) == pytest.approx(2 / 4)


def test_sign_flip_reversal_raises_p():
    assert paired_sign_flip_p([3, -3]) == pytest.approx(3 / 4)


def test_sign_flip_empty_is_none():
    assert paired_sign_flip_p([]) is None
