"""Real-archive bridge: score the real export at the simulation's scale.

The real wiki held thousands of agents; occupancy statistics depend on scale. So we cut the
real log into consecutive, non-overlapping windows of k distinct named agents (k = 36, the
agents per simulated run) and compute the same statistics per window. Windows are split at
the coordination onset Lutje dates to 2026-06-16T09:27:10Z (2609.12748, Rendezvous)."""
from datetime import datetime, timezone

import numpy as np

from .analyze import normalise_page, page_choices
from .evidence import fit_copying_w, occupancy

INFRA_PAGES = ["WillkommenImWiki", "StartSeite", "TestSeite"]  # Lutje's three infrastructure pages
ONSET = datetime(2026, 6, 16, 9, 27, 10, tzinfo=timezone.utc).timestamp()


def label_windows(revs, k=36):
    rows = sorted((r for r in revs if r.get("label") and r["name"] not in INFRA_PAGES),
                  key=lambda r: r["time"])
    windows, cur, labels = [], [], set()
    for r in rows:
        if r["label"] not in labels and len(labels) == k:
            windows.append(cur)
            cur, labels = [], set()
        cur.append(r)
        labels.add(r["label"])
    if len(labels) == k:
        windows.append(cur)
    return windows


def onset_side(w):
    """'before' if the window ends before the onset, 'after' if it starts at or after it,
    'straddle' otherwise (checker B5: such windows are excluded from the comparison)."""
    if w["end"] < ONSET:
        return "before"
    if w["start"] >= ONSET:
        return "after"
    return "straddle"


def window_stats(revs, k=36):
    out = []
    for w in label_windows(revs, k):
        out.append({"start": w[0]["time"], "end": w[-1]["time"], "n_revs": len(w),
                    "after_onset": w[0]["time"] >= ONSET,
                    "side": onset_side({"start": w[0]["time"], "end": w[-1]["time"]}),
                    "span_hours": (w[-1]["time"] - w[0]["time"]) / 3600,
                    "gini": occupancy(w)["gini"], "n_pages": occupancy(w)["n_pages"],
                    "gini_norm": occupancy([{**r, "name": normalise_page(r["name"])} for r in w])["gini"],
                    "copy_w": fit_copying_w(page_choices(w))["w"]})
    return out


def summarise_windows(rows):
    def agg(sel):
        if not sel:
            return None
        g = np.array([r["gini"] for r in sel])
        c = np.array([r["copy_w"] for r in sel if r["copy_w"] is not None])
        span = np.array([r["span_hours"] for r in sel])
        gn = np.array([r["gini_norm"] for r in sel])
        return {"n_windows": len(sel), "gini_median": float(np.median(g)),
                "gini_norm_median": float(np.median(gn)),
                "span_hours_median": float(np.median(span)),
                "gini_iqr": [float(np.percentile(g, 25)), float(np.percentile(g, 75))],
                "copy_w_median": float(np.median(c)) if c.size else None}
    return {"before_onset": agg([r for r in rows if r["side"] == "before"]),
            "after_onset": agg([r for r in rows if r["side"] == "after"]),
            "straddling_excluded": [i for i, r in enumerate(rows) if r["side"] == "straddle"],
            "all": agg(rows)}


def window_judge_prompt(window, informed=False):
    """Same judge prompt as the simulation, fed what each agent added (its delta)."""
    from .judge import build_judge_prompt
    rows = [{"name": r["name"], "label": r["label"], "time": r["time"] - window[0]["time"],
             "body": r.get("delta", r["body"]), "family": "W"} for r in window]
    return build_judge_prompt(rows, "W", informed=informed)


def sample_windows(rows, n_after=18, seed=0):
    """All pre-onset windows plus a fixed random sample of post-onset ones, as (index, row)."""
    rng = np.random.default_rng(seed)
    before = [(i, r) for i, r in enumerate(rows) if not r["after_onset"]]
    after = [(i, r) for i, r in enumerate(rows) if r["after_onset"]]
    pick = sorted(rng.choice(len(after), size=min(n_after, len(after)), replace=False).tolist())
    return before + [after[j] for j in pick]


def judge_real_windows(revs, backend, out_path, k=36, n_after=18, seed=0, informed=False):
    import json
    from .sim import parse_json
    windows = label_windows(revs, k)
    rows = window_stats(revs, k)
    with open(out_path, "w") as f:
        for i, r in sample_windows(rows, n_after, seed):
            raw = backend.complete(window_judge_prompt(windows[i], informed=informed))
            obj = parse_json(raw) or {}
            sc = obj.get("score")
            ok = isinstance(sc, (int, float)) and not isinstance(sc, bool) and 0 <= sc <= 100
            f.write(json.dumps({"window": i, "after_onset": r["after_onset"], "side": r["side"], "start": r["start"],
                                "score": sc if ok else None, "reason": obj.get("reason"),
                                "judge": backend.name, "informed": informed}) + "\n")
