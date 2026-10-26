"""Real-archive bridge: cut the real log into windows of k distinct named agents so its
statistics can sit next to the 36-agent simulated runs."""
from nullspace.bridge import label_windows, INFRA_PAGES


def rev(name, label, t):
    return {"name": name, "label": label, "time": float(t), "body": "x", "prev_body": "", "delta": "x"}


def test_windows_hold_exactly_k_distinct_labels_and_do_not_overlap():
    revs = [rev("P", f"a{i % 5}", i) for i in range(20)] + [rev("Q", f"b{i}", 100 + i) for i in range(6)]
    ws = label_windows(revs, k=3)
    seen = set()
    for w in ws:
        labels = {r["label"] for r in w}
        assert len(labels) == 3
        ids = {id(r) for r in w}
        assert not (ids & seen)
        seen |= ids


def test_incomplete_tail_window_is_dropped():
    revs = [rev("P", "a", 1), rev("P", "b", 2), rev("P", "c", 3), rev("P", "d", 4)]
    assert len(label_windows(revs, k=3)) == 1


def test_unlabelled_and_infra_rows_are_ignored():
    revs = [rev(INFRA_PAGES[0], "a", 1), rev("P", None, 2), rev("P", "b", 3), rev("P", "c", 4)]
    ws = label_windows(revs, k=2)
    assert len(ws) == 1 and {r["label"] for r in ws[0]} == {"b", "c"}


def test_windows_are_time_ordered():
    revs = [rev("P", "b", 5), rev("P", "a", 1), rev("Q", "c", 3), rev("Q", "d", 7)]
    w = label_windows(revs, k=2)[0]
    assert [r["time"] for r in w] == sorted(r["time"] for r in w)


import json as _json

from nullspace.bridge import window_judge_prompt, sample_windows


def test_window_prompt_uses_added_text_not_full_page():
    w = [{"name": "P", "label": "a", "time": 1.0, "body": "OLD INHERITED TEXT\nnew", "delta": "new"}]
    p = window_judge_prompt(w)
    assert "new" in p and "OLD INHERITED TEXT" not in p
    for leak in ("onset", "before", "after", "blind", "visible"):
        assert leak not in p.lower().replace("before writing", "")


def test_sample_windows_takes_all_before_and_fixed_count_after():
    rows = [{"after_onset": False}] * 3 + [{"after_onset": True}] * 10
    pick = sample_windows(rows, n_after=4, seed=0)
    assert sum(not r["after_onset"] for _, r in pick) == 3
    assert sum(r["after_onset"] for _, r in pick) == 4
    assert pick == sample_windows(rows, n_after=4, seed=0)


def test_windows_straddling_the_onset_are_marked_and_excluded():
    from nullspace.bridge import ONSET, onset_side
    assert onset_side({"start": ONSET - 100, "end": ONSET - 1}) == "before"
    assert onset_side({"start": ONSET, "end": ONSET + 50}) == "after"
    assert onset_side({"start": ONSET - 100, "end": ONSET + 100}) == "straddle"
