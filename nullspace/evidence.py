"""The published evidence statistics, as functions of a revision log."""
import math

import numpy as np

from .features import extract


def _first_per_label(revs):
    seen, out = set(), []
    for r in sorted(revs, key=lambda r: r["time"]):
        if not r.get("label"):
            continue
        if r["label"] in seen:
            continue
        seen.add(r["label"])
        out.append(r)
    return out


def exposure_adoption_rd(revs, feature, n_boot=1000, seed=0):
    """Lutje Table 4: exposed = feature stood in the previous revision of the
    page written to; adopt = feature in the newcomer's own first revision."""
    firsts = [r for r in _first_per_label(revs) if r.get("prev_body") is not None]
    own = lambda r: r.get("delta", r["body"])  # what the newcomer added (Lutje: deltas, not page text)
    exp = [feature in extract(own(r)) for r in firsts if feature in extract(r["prev_body"])]
    une = [feature in extract(own(r)) for r in firsts if feature not in extract(r["prev_body"])]
    out = {"n_exposed": len(exp), "n_unexposed": len(une),
           "p_exposed": float(np.mean(exp)) if exp else None,
           "p_unexposed": float(np.mean(une)) if une else None,
           "rd": None, "ci95": None}
    if not exp or not une:
        return out
    out["rd"] = out["p_exposed"] - out["p_unexposed"]
    if n_boot:
        rng = np.random.default_rng(seed)
        e, u = np.array(exp, float), np.array(une, float)
        boots = [rng.choice(e, e.size).mean() - rng.choice(u, u.size).mean() for _ in range(n_boot)]
        out["ci95"] = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    return out


def first_line_convergence(revs, feature, n_windows=4):
    """Lutje Fig. 3: share of newcomers' first revision carrying the feature, per
    equal-width arrival window; convergence = last non-empty minus first non-empty."""
    firsts = _first_per_label(revs)
    if not firsts:
        return {"shares": [], "n_per_window": [], "convergence": None}
    t = np.array([r["time"] for r in firsts], float)
    edges = np.linspace(t.min(), t.max(), n_windows + 1)
    idx = np.clip(np.searchsorted(edges, t, side="right") - 1, 0, n_windows - 1)
    shares, ns = [], []
    for w in range(n_windows):
        members = [firsts[i] for i in range(len(firsts)) if idx[i] == w]
        ns.append(len(members))
        shares.append(float(np.mean([feature in extract(r.get("delta", r["body"])) for r in members]))
                      if members else None)
    filled = [s for s in shares if s is not None]
    conv = filled[-1] - filled[0] if len(filled) >= 2 else None
    return {"shares": shares, "n_per_window": ns, "convergence": conv}


def _ll(choices, w):
    total = 0.0
    for c in choices:
        k = len(c["options"])
        p = (1 - w) / k + w * c["visible_share"].get(c["choice"], 0.0)
        total += math.log(max(p, 1e-300))
    return total


def fit_copying_w(choices):
    """De Marzo-style one-parameter copying model: P(o) = (1-w)/k + w * share(o)."""
    if not choices:
        return {"w": None, "ll_gain": None, "n": 0}
    grid = np.linspace(0, 1, 201)
    lls = [_ll(choices, w) for w in grid]
    i = int(np.argmax(lls))
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    fine = np.linspace(lo, hi, 101)
    lls_f = [_ll(choices, w) for w in fine]
    j = int(np.argmax(lls_f))
    return {"w": float(fine[j]), "ll_gain": float(lls_f[j] - _ll(choices, 0.0)), "n": len(choices)}


def occupancy(revs):
    pages = {}
    for r in revs:
        pages.setdefault(r["name"], set()).add(r["label"])
    counts = {k: len(v) for k, v in pages.items()}
    x = np.sort(np.array(list(counts.values()), float))
    if x.size == 0 or x.sum() == 0:
        gini = 0.0
    else:
        n = x.size
        gini = float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))
    return {"labels_per_page": counts, "gini": gini, "n_pages": len(counts)}
