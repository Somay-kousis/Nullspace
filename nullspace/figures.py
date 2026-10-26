"""Figures from analysis/ outputs: python -m nullspace.figures"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .analyze import OUT, RUNS, judge_scores  # noqa: E402

VIS, BLD = "#2a78d6", "#eb6834"      # validated categorical slots 1-2 (dataviz palette)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
MODELS = [("groq:openai/gpt-oss-20b@low", "gpt-oss-20b"), ("groq:qwen/qwen3.8-27b", "qwen3.8-27b")]
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "font.family": "DejaVu Sans"})


def _judge_units():
    from .analyze import run_dirs
    units = {}
    dirs, _ = run_dirs(RUNS)
    for d in dirs:
        if "_pilot" in d.parent.name:
            continue
        meta = json.loads((d / "meta.json").read_text())
        units.setdefault((meta["backend"], meta["condition"]), []).extend(
            x for x in judge_scores(d) if x is not None)
    return units


def fig_judge(path):
    units = _judge_units()
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    rng = np.random.default_rng(0)
    for i, (b, label) in enumerate(MODELS):
        for j, (cond, col, mk) in enumerate([("visible", VIS, "o"), ("blind", BLD, "D")]):
            ys = units.get((b, cond), [])
            xs = i + (j - 0.5) * 0.36 + rng.uniform(-0.07, 0.07, len(ys))
            ax.scatter(xs, ys, s=34, marker=mk, facecolor=col if cond == "visible" else "none",
                       edgecolor=col, linewidth=1.6, zorder=3,
                       label=("can read board" if cond == "visible" else "cannot read board") if i == 0 else None)
            flagged = sum(y > 50 for y in ys)
            ax.text(i + (j - 0.5) * 0.36, 108, f"{flagged}/{len(ys)}", ha="center", color=INK, fontsize=8)
    ax.axhline(50, color=MUTED, ls="--", lw=1, zorder=1)
    ax.text(1.55, 51.5, "flag threshold", color=MUTED, fontsize=7.5, ha="right")
    ax.set_xticks(range(len(MODELS)), [m[1] for m in MODELS])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(-5, 116)
    ax.set_ylabel("LLM judge score (0-100)")
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def fig_stats(path):
    s = json.loads((OUT / "summary.json").read_text())["groups"]
    panels = [("correct", "correct answers per run\n(ground truth: transmission)"),
              ("copy_w", "copying-model weight w\n(De Marzo page choice)"),
              ("grammar_share", "page names built from own\ntask blocks (share)"),
              ("rd_cohort_word", "exposure-adoption gap,\n'cohort' (Lutje)")]
    fig, axes = plt.subplots(2, 2, figsize=(6.5, 5.0))
    for ax, (key, title) in zip(axes.flat, panels):
        for i, (b, label) in enumerate(MODELS):
            for j, (cond, col, mk) in enumerate([("visible", VIS, "o"), ("blind", BLD, "D")]):
                vals = s.get(f"{b}|{cond}", {}).get(key, {}).get("values", [])
                x = i + (j - 0.5) * 0.36
                ax.scatter([x] * len(vals), vals, s=30, marker=mk, edgecolor=col, linewidth=1.5,
                           facecolor=col if cond == "visible" else "none", zorder=3)
                if vals:
                    ax.hlines(np.mean(vals), x - 0.13, x + 0.13, color=col, lw=2, zorder=4)
        if key == "correct":
            ch = [v for b, _ in MODELS for v in s.get(f"{b}|blind", {}).get("chance_correct", {}).get("values", [])]
            if ch:
                ax.axhline(np.mean(ch), color=MUTED, ls="--", lw=1, zorder=1)
                ax.text(1.55, np.mean(ch) + 0.15, "chance", color=MUTED, fontsize=7, ha="right")
        ax.set_title(title, fontsize=8.5, color=INK)
        ax.set_xticks(range(len(MODELS)), [m[1] for m in MODELS], fontsize=7.5)
        ax.set_xlim(-0.6, 1.6)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    handles = [plt.Line2D([], [], marker="o", ls="", color=VIS, label="can read board"),
               plt.Line2D([], [], marker="D", ls="", markerfacecolor="none", color=BLD, label="cannot read board")]
    fig.legend(handles=handles, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def fig_judge_variants(path):
    s = json.loads((OUT / "summary.json").read_text())["judge_family_level"]
    variants = [("naive", "Flash-Lite\nnaive"), ("_informed", "Flash-Lite\nconfound-aware"),
                ("_strong", "gpt-oss-120b\nnaive"), ("_strong_informed", "gpt-oss-120b\nconfound-aware")]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.2), sharey=True)
    for ax, (b, label) in zip(axes, MODELS):
        for i, (tag, vlabel) in enumerate(variants):
            row = s.get(f"{b}|{tag}")
            if not row:
                continue
            for rate, ci, col, mk, dx in [(row["tpr"], row["tpr_ci95_runboot"], VIS, "o", -0.12),
                                         (row["fpr"], row["fpr_ci95_runboot"], BLD, "D", 0.12)]:
                if rate is None:
                    continue
                ax.vlines(i + dx, ci[0], ci[1], color=col, lw=1.6)
                ax.scatter([i + dx], [rate], marker=mk, s=40, edgecolor=col, linewidth=1.6,
                           facecolor=col if col == VIS else "none", zorder=3)
        ax.set_xticks(range(len(variants)), [v[1] for v in variants], fontsize=7)
        ax.set_title(f"agents: {label}", fontsize=9, color=INK)
        ax.set_ylim(-0.03, 1.03)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("share of task-family logs flagged")
    handles = [plt.Line2D([], [], marker="o", ls="", color=VIS, label="detection (can read board)"),
               plt.Line2D([], [], marker="D", ls="", markerfacecolor="none", color=BLD,
                          label="false alarm (cannot read board)")]
    fig.legend(handles=handles, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def fig_bridge(path):
    b = json.loads((OUT / "bridge.json").read_text())
    s = json.loads((OUT / "summary.json").read_text())["groups"]
    rng = np.random.default_rng(1)
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.3), sharey=True)
    for ax, key, title in [(axes[0], "gini", "page names as written"),
                           (axes[1], "gini_norm", "cohort-date and round tokens removed")]:
        cols = [("real\nbefore", [w[key] for w in b["windows"] if w["side"] == "before"], MUTED, "s", "none"),
                ("real\nafter", [w[key] for w in b["windows"] if w["side"] == "after"], INK, "s", "none")]
        for b_, label in MODELS:
            short = {"gpt-oss-20b": "gpt-oss", "qwen3.8-27b": "qwen"}[label]
            cols.append((f"{short}\nread", s[f"{b_}|visible"][key]["values"], VIS, "o", VIS))
            cols.append((f"{short}\nblind", s[f"{b_}|blind"][key]["values"], BLD, "D", "none"))
        for i, (lab, vals, col, mk, fc) in enumerate(cols):
            xs = i + rng.uniform(-0.18, 0.18, len(vals))
            ax.scatter(xs, vals, s=10 if i < 2 else 26, marker=mk, edgecolor=col, facecolor=fc,
                       linewidth=1.1, alpha=0.6 if i < 2 else 1, zorder=3)
            if vals:
                ax.hlines(np.median(vals), i - 0.3, i + 0.3, color=col, lw=2, zorder=4)
        ax.set_xticks(range(len(cols)), [c[0] for c in cols], fontsize=7)
        ax.set_title(title, fontsize=8.5, color=INK)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("page concentration (Gini), 36-agent units")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def main():
    figs = OUT / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig_judge(figs / "fig1_judge_false_alarms.png")
    fig_judge_variants(figs / "fig2_judge_variants.png")
    fig_stats(figs / "fig3_statistics_by_condition.png")
    if (OUT / "bridge.json").exists():
        fig_bridge(figs / "fig4_real_archive_bridge.png")
    print(sorted(p.name for p in figs.iterdir()))


if __name__ == "__main__":
    main()
