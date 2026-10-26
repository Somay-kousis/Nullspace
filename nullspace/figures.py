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
    fig, axes = plt.subplots(1, 4, figsize=(9.6, 2.7))
    for ax, (key, title) in zip(axes, panels):
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
    fig.legend(handles=handles, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def fig_judge_variants(path):
    s = json.loads((OUT / "summary.json").read_text())["judge_family_level"]
    variants = [("naive", "Flash-Lite\nnaive"), ("_informed", "Flash-Lite\nconfound-aware"),
                ("_strong", "gpt-oss-120b\nnaive"), ("_strong_informed", "gpt-oss-120b\nconfound-aware")]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.0), sharey=True)
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
        ax.set_xticks(range(len(variants)), [v[1] for v in variants], fontsize=7.5)
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


def main():
    figs = OUT / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    fig_judge(figs / "fig1_judge_false_alarms.png")
    fig_stats(figs / "fig2_statistics_by_condition.png")
    fig_judge_variants(figs / "fig3_judge_variants.png")
    print(sorted(p.name for p in figs.iterdir()))


if __name__ == "__main__":
    main()
