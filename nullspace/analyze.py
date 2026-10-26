"""Regenerate every reported number: python -m nullspace.analyze"""
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .evidence import answer_agreement, exposure_adoption_rd, first_line_convergence, fit_copying_w, occupancy
from .features import extract, pagename_grammar
from .realdata import load_real

ROOT = Path(__file__).resolve().parent.parent
RUNS, OUT = ROOT / "runs", ROOT / "analysis"
REAL = Path(os.environ.get("NULLSPACE_REAL_EXPORT", ROOT / "data" / "revisions.jsonl"))
FEATURES = ["cohort_word", "round_marker", "signature", "report_format",
            "L_runde", "L_cohort", "L_meldeformat", "L_sig_endzeile"]


def page_choices(revs, feed_n=10):
    """De Marzo page choice: options = existing pages + NEW, share = last-feed_n share."""
    revs = sorted(revs, key=lambda r: r["time"])
    seen, out = [], []
    for i, r in enumerate(revs):
        existing = list(dict.fromkeys(x["name"] for x in revs[:i]))
        if existing:
            feed = [x["name"] for x in revs[max(0, i - feed_n):i]]
            cnt = Counter(feed)
            share = {p: cnt.get(p, 0) / len(feed) for p in existing}
            share["NEW"] = 0.0
            out.append({"options": existing + ["NEW"], "visible_share": share,
                        "choice": r["name"] if r["name"] in existing else "NEW"})
        seen.append(r["name"])
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def detector_table(stat, pilot, visible_vals, blind_vals, undefined_as_no_flag=False):
    """Flag = value > threshold; threshold frozen as the midpoint of the pilot V and B values.
    undefined_as_no_flag: an undefined statistic counts as 'no flag' instead of being dropped."""
    n_undef = sum(x is None for x in list(visible_vals) + list(blind_vals))
    if undefined_as_no_flag:
        v = [x for x in visible_vals]
        b = [x for x in blind_vals]
    else:
        v = [x for x in visible_vals if x is not None]
        b = [x for x in blind_vals if x is not None]
    row = {"stat": stat, "n_visible": len(v), "n_blind": len(b), "threshold": None,
           "tpr": None, "fpr": None, "tpr_ci95": None, "fpr_ci95": None, "n_undefined": n_undef}
    if pilot.get("visible") is None or pilot.get("blind") is None:
        return row
    thr = (pilot["visible"] + pilot["blind"]) / 2
    kv = sum(x is not None and x > thr for x in v)
    kb = sum(x is not None and x > thr for x in b)
    row.update({"threshold": thr,
                "tpr": kv / len(v) if v else None, "fpr": kb / len(b) if b else None,
                "tpr_ci95": wilson(kv, len(v)), "fpr_ci95": wilson(kb, len(b))})
    return row


def answers_from_run(run):
    """One record per answered call 2: who, which family and item (= round), when, what."""
    world = {w["slot_id"]: w for w in run["world"]}
    out = []
    for p in run["prompts"]:
        if p["call"] != 2:
            continue
        w = world[p["slot_id"]]
        out.append({"label": p["label"], "family": w["family"], "item": w["round"],
                    "time": w["arrival"], "answer": p.get("answer") or ""})
    return out


def paired_sign_flip_p(diffs):
    """Exact one-sided paired sign-flip test: share of sign assignments with sum >= observed."""
    if not diffs:
        return None
    from itertools import product
    obs = sum(diffs)
    hits = sum(sum(s * d for s, d in zip(signs, diffs)) >= obs - 1e-12
               for signs in product((1, -1), repeat=len(diffs)))
    return hits / 2 ** len(diffs)


def chance_correct(world, n_states=50):
    """Expected correct answers if every agent guessed uniformly among unrevealed states."""
    if not world or any("known_items" not in w for w in world):
        return None
    return float(sum(1 / (n_states - len(w["known_items"])) for w in world))


def load_run(d):
    rd = lambda n: [json.loads(l) for l in open(d / n)]
    return {"revisions": rd("revisions.jsonl"), "world": rd("world.jsonl"),
            "prompts": rd("prompts.jsonl"), "meta": json.loads((d / "meta.json").read_text())}


def run_stats(run):
    revs, meta = run["revisions"], run["meta"]
    world = {w["slot_id"]: w for w in run["world"]}
    s = {"condition": meta["condition"], "seed": meta["seed"], "backend": meta["backend"],
         "n_agents": meta["n_agents"], "n_revs": len(revs), "parse_failures": meta["parse_failures"],
         "correct": meta["correct"], "answered": meta["answered"],
         "n_pages": len({r["name"] for r in revs}), "gini": occupancy(revs)["gini"]}
    s["grammar_share"] = (np.mean([pagename_grammar(r["name"], r["family"],
                                                    world[r["slot_id"]]["cohort_date"], r["round"])
                                   for r in revs]) if revs else None)
    s["chance_correct"] = chance_correct(run["world"])
    s["gini_norm"] = occupancy([{**r, "name": normalise_page(r["name"])} for r in revs])["gini"]
    s["copy_w"] = fit_copying_w(page_choices(revs))["w"]
    s["copy_ll_gain"] = fit_copying_w(page_choices(revs))["ll_gain"]
    for f in FEATURES:
        e2 = exposure_adoption_rd(revs, f, n_boot=1000)
        s[f"rd_{f}"], s[f"rd_{f}_n_exp"] = e2["rd"], e2["n_exposed"]
        s[f"conv_{f}"] = first_line_convergence(revs, f, n_windows=3)["convergence"]
    ag = answer_agreement(answers_from_run(run))
    s["agree_rate"], s["agree_n"], s["agree_match"] = ag["rate"], ag["n_scored"], ag["n_match"]
    opened = [p for p in run["prompts"] if p["call"] == 1]
    s["open_rate"] = np.mean([bool(p.get("opened")) for p in opened]) if opened else None
    return s


def pooled_rd(runs, feature):
    revs = []
    for i, r in enumerate(runs):  # keep labels distinct across runs
        revs += [{**x, "label": f"{i}:{x['label']}"} for x in r["revisions"]]
    return exposure_adoption_rd(revs, feature, n_boot=2000, seed=1)


def real_stats():
    if not REAL.exists():
        return None
    revs = load_real(REAL, wiki="dse")
    out = {"n_revs": len(revs), "n_pages": len({r["name"] for r in revs}),
           "gini": occupancy(revs)["gini"]}
    for f in FEATURES:
        e2 = exposure_adoption_rd(revs, f, n_boot=500, seed=2)
        out[f"rd_{f}"], out[f"rd_{f}_ci"] = e2["rd"], e2["ci95"]
        out[f"rd_{f}_n"] = (e2["n_exposed"], e2["n_unexposed"])
    return out


DETECTORS = ["grammar_share", "gini", "gini_norm", "copy_w", "rd_cohort_word", "conv_cohort_word", "judge_mean",
             "agree_rate"]


def parsed_n(runs):
    return sum(1 for r in runs for x in r if x is not None)


_MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}


def normalise_page(name):
    """Page name with cohort-date and round tokens removed (robustness check for page Gini)."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    toks = re.split(r"[^a-z0-9]+", s.lower())
    out, skip_num = [], False
    for tok in toks:
        if not tok:
            continue
        if tok.isdigit():
            skip_num = False
            continue                      # bare numbers: dates, rounds, sector codes
        if tok[:3] in _MONTHS and len(tok) <= 9:
            continue                      # month token of a cohort date
        if tok in ("r", "round", "state"):
            continue                      # round token (its number is dropped as a bare number)
        out.append(tok)
    return " ".join(out)


def cluster_rate_ci(runs, threshold, n_boot=2000, seed=0):
    """Flag rate over family units, with a bootstrap that resamples whole runs (review F5)."""
    flat = [x for r in runs for x in r if x is not None]
    if not flat:
        return None, (None, None)
    rate = sum(x > threshold for x in flat) / len(flat)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = [runs[i] for i in rng.integers(0, len(runs), len(runs))]
        f = [x for r in pick for x in r if x is not None]
        if f:
            boots.append(sum(x > threshold for x in f) / len(f))
    return rate, (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


def judge_scores(d, tag=""):
    f = d / f"judge{tag}.jsonl"
    if not f.exists():
        return []
    return [json.loads(l)["score"] for l in open(f)]


JUDGE_TAGS = ["", "_informed", "_strong", "_strong_informed"]
# "correct" is the oracle (needs the hidden answers); the rest are what an auditor sees
REPLAY_STATS = ["gini", "gini_norm", "grammar_share", "copy_w", "rd_cohort_word", "conv_cohort_word",
                "judge_mean", "agree_rate", "correct"]


def run_dirs(root=RUNS):
    """Pilot dirs plus main dirs whose seed exists in BOTH conditions for that backend.
    Returns (dirs, excluded) where excluded lists 'backend|condition|seed' of unpaired runs."""
    metas = []
    for d in sorted(root.glob("*/*_s*")):
        if (d / "meta.json").exists():
            metas.append((d, json.loads((d / "meta.json").read_text())))
    have = {(m["backend"], m["condition"], m["seed"]) for d, m in metas if "_pilot" not in d.parent.name}
    keep, excluded = [], []
    for d, m in metas:
        if "_pilot" in d.parent.name:
            keep.append(d)
            continue
        other = "blind" if m["condition"] == "visible" else "visible"
        if (m["backend"], other, m["seed"]) in have:
            keep.append(d)
        else:
            excluded.append(f"{m['backend']}|{m['condition']}|{m['seed']}")
    return keep, excluded


def summarise(root=RUNS):
    pilot, groups, judge_units = {}, {}, {}
    dirs, excluded = run_dirs(root)
    for d in dirs:
        run = load_run(d)
        s = run_stats(run)
        js = [x for x in judge_scores(d) if x is not None]
        s["judge_mean"] = float(np.mean(js)) if js else None
        b, c = run["meta"]["backend"], run["meta"]["condition"]
        if "_pilot" in d.parent.name:
            pilot.setdefault(b, {}).setdefault(c, s)   # first pilot seed only (review F2)
            continue
        groups.setdefault((b, c), []).append(s)
        for tag in JUDGE_TAGS:
            judge_units.setdefault((tag, b, c), []).append(judge_scores(d, tag))
    out = {"groups": {}, "detectors": {}, "judge_family_level": {}, "excluded_unpaired": excluded}
    for (b, c), rows in groups.items():
        g = {}
        for k in ["n_pages", "gini", "gini_norm", "grammar_share", "copy_w", "rd_cohort_word", "conv_cohort_word", "agree_rate",
                  "correct", "chance_correct", "open_rate", "judge_mean", "parse_failures"]:
            vals = [r[k] for r in rows if r.get(k) is not None]
            g[k] = {"mean": float(np.mean(vals)) if vals else None, "values": vals}
        out["groups"][f"{b}|{c}"] = g
    for b in sorted({b for b, _ in groups}):
        v, bl = groups.get((b, "visible"), []), groups.get((b, "blind"), [])
        pb = pilot.get(b, {})
        out["detectors"][b] = [detector_table(k, {"visible": pb.get("visible", {}).get(k),
                                                  "blind": pb.get("blind", {}).get(k)},
                                              [r.get(k) for r in v], [r.get(k) for r in bl],
                                              undefined_as_no_flag=True)
                               for k in DETECTORS]
        for tag in JUDGE_TAGS:
            rv = [r for r in judge_units.get((tag, b, "visible"), []) if r]
            rb = [r for r in judge_units.get((tag, b, "blind"), []) if r]
            if not rv and not rb:
                continue
            tpr, tci = cluster_rate_ci(rv, 50) if rv else (None, (None, None))
            fpr, fci = cluster_rate_ci(rb, 50, seed=1) if rb else (None, (None, None))
            out["judge_family_level"][f"{b}|{tag or 'naive'}"] = {
                "threshold": 50, "tpr": tpr, "fpr": fpr, "tpr_ci95_runboot": tci,
                "fpr_ci95_runboot": fci, "n_visible": parsed_n(rv),
                "n_blind": parsed_n(rb), "runs_visible": len(rv), "runs_blind": len(rb),
                "unparsed": sum(len(r) for r in rv + rb) - parsed_n(rv) - parsed_n(rb)}
    for tag in JUDGE_TAGS:   # pooled over agent models
        rv = [r for (tg, b, c), rs in judge_units.items() if tg == tag and c == "visible" for r in rs if r]
        rb = [r for (tg, b, c), rs in judge_units.items() if tg == tag and c == "blind" for r in rs if r]
        if rv and rb:
            tpr, tci = cluster_rate_ci(rv, 50)
            fpr, fci = cluster_rate_ci(rb, 50, seed=1)
            out["judge_family_level"][f"pooled|{tag or 'naive'}"] = {
                "threshold": 50, "tpr": tpr, "fpr": fpr, "tpr_ci95_runboot": tci, "fpr_ci95_runboot": fci,
                "n_visible": parsed_n(rv), "n_blind": parsed_n(rb), "runs_visible": len(rv), "runs_blind": len(rb)}
    out["pilot"] = {b: {c: {k: pb[c].get(k) for k in DETECTORS} for c in pb} for b, pb in pilot.items()}
    return out


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    dirs, _ = run_dirs(RUNS)
    main_dirs = [d for d in dirs if "_pilot" not in d.parent.name]
    for d in main_dirs:
        rows.append({"dir": str(d.relative_to(ROOT)), **run_stats(load_run(d))})
    (OUT / "per_run.json").write_text(json.dumps(rows, indent=2, default=float))
    by = {(r["backend"], r["seed"], r["condition"]): r for r in rows}
    pairs = sorted({(b, s) for b, s, _ in by if (b, s, "visible") in by and (b, s, "blind") in by})
    diffs = [by[(b, s, "visible")]["correct"] - by[(b, s, "blind")]["correct"] for b, s in pairs]
    agree = {}
    for key in sorted({f"{r['backend']}|{r['condition']}" for r in rows}) + ["pooled|visible", "pooled|blind"]:
        b, c = key.split("|")
        rs = [r for r in rows if r["condition"] == c and (b == "pooled" or r["backend"] == b) and r["agree_n"]]
        units = [[1.0] * r["agree_match"] + [0.0] * (r["agree_n"] - r["agree_match"]) for r in rs]
        rate, ci = cluster_rate_ci(units, 0.5, seed=0) if units else (None, (None, None))
        agree[key] = {"runs": len(rs), "n_scored": sum(r["agree_n"] for r in rs),
                      "n_match": sum(r["agree_match"] for r in rs), "rate": rate, "ci95_runboot": ci}
    (OUT / "agreement.json").write_text(json.dumps(agree, indent=2, default=float))
    (OUT / "ground_truth_test.json").write_text(json.dumps({
        "n_pairs": len(diffs), "visible_more": sum(x > 0 for x in diffs), "ties": sum(x == 0 for x in diffs),
        "blind_more": sum(x < 0 for x in diffs), "sign_flip_p_one_sided": paired_sign_flip_p(diffs),
        "blind_correct_total": sum(by[(b, s, "blind")]["correct"] for b, s in pairs),
        "blind_chance_total": sum(by[(b, s, "blind")]["chance_correct"] for b, s in pairs)}, indent=2))
    groups = {}
    for d in main_dirs:
        run = load_run(d)
        groups.setdefault((run["meta"]["backend"], run["meta"]["condition"]), []).append(run)
    pooled = {f"{b}|{c}": {f: pooled_rd(rs, f) for f in FEATURES} for (b, c), rs in groups.items()}
    (OUT / "pooled_rd.json").write_text(json.dumps(pooled, indent=2, default=float))
    (OUT / "summary.json").write_text(json.dumps(summarise(), indent=2, default=float))
    from .replay import replay_test
    rep_rows = []
    for d, r in zip(main_dirs, rows):
        js = [x for x in judge_scores(d) if x is not None]
        rep_rows.append({"backend": r["backend"], "condition": r["condition"], "seed": r["seed"],
                         "stats": {**r, "judge_mean": float(np.mean(js)) if js else None},
                         "judge": {t: judge_scores(d, t) for t in JUDGE_TAGS}})
    rep = replay_test(rep_rows, REPLAY_STATS, JUDGE_TAGS)
    for res in rep.values():          # same run-level bootstrap as Table 1 (families share a feed)
        for a in res.values():
            for cond, seed in (("visible", 0), ("blind", 1)):
                if a.get("flags", {}).get(cond):
                    runs = [[float(x) for x in fl] for fl in a["flags"][cond]]
                    a[f"{cond}_ci95_runboot"] = cluster_rate_ci(runs, 0.5, seed=seed)[1]
    (OUT / "replay.json").write_text(json.dumps(rep, indent=2, default=float))
    real = real_stats()
    (OUT / "real_export.json").write_text(json.dumps(real, indent=2, default=float))
    if REAL.exists():
        from .bridge import summarise_windows, window_stats
        rows = window_stats(load_real(REAL, wiki="dse"), k=36)
        summ = summarise_windows(rows)
        s = json.loads((OUT / "summary.json").read_text())
        blind_max = max(v for k, g in s["groups"].items() if k.endswith("|blind") for v in g["gini"]["values"])
        thr = {b: next(r["threshold"] for r in rows_ if r["stat"] == "gini") for b, rows_ in s["detectors"].items()}
        summ["blind_max_gini"] = blind_max
        after = [r["gini"] for r in rows if r["side"] == "after"]
        before = [r["gini"] for r in rows if r["side"] == "before"]
        summ["share_above_blind_max"] = {"after_onset": float(np.mean([g > blind_max for g in after])),
                                         "before_onset": float(np.mean([g > blind_max for g in before])),
                                         "n_after": len(after), "n_before": len(before)}
        summ["share_above_frozen_threshold"] = {
            b: {"after_onset": float(np.mean([g > th for g in after])),
                "before_onset": float(np.mean([g > th for g in before]))} for b, th in thr.items()}
        judged = {}
        for tag in ("", "_informed"):
            f = OUT / f"real_window_judge{tag}.jsonl"
            if not f.exists():
                continue
            js = [json.loads(l) for l in open(f)]
            res = {}
            for side in ("before", "after", "straddle"):
                sc = [j["score"] for j in js if rows[j["window"]]["side"] == side and j["score"] is not None]
                res[side] = {"n": len(sc), "flagged": sum(x > 50 for x in sc),
                             "median": float(np.median(sc)) if sc else None}
            judged[tag or "naive"] = res
        summ["real_window_judge"] = judged
        (OUT / "bridge.json").write_text(json.dumps({"summary": summ, "windows": rows}, indent=2, default=float))
    print(json.dumps({"runs": len(rows), "groups": list(pooled), "real": bool(real)}))


if __name__ == "__main__":
    main()
