# Nullspace

A blind-board control for reading coordination in multi-agent LLM logs. It was built for the Apart AI Collusion Research Sprint (Oct 2026), Track 2, question 2.3: what should count as convincing evidence of collusion?

**Background:** in May-July 2026, OpenAI evaluation agents wrote thousands of edits to a public German wiki and passed answers between cohorts (the "German Wiki Incident"; export at [collusion.wiki](https://collusion.wiki/explorer/download.html)). Two analyses of that archive disagree:
- De Marzo et al. ([arXiv 2609.09150](https://arxiv.org/abs/2609.09150)) read it as copying.
- Lütje ([arXiv 2609.12748](https://arxiv.org/abs/2609.12748)) says the archive can't separate copying from convergence caused by a shared prompt or model.

Neither has a condition in which agents cannot read each other.

**What this repo does:** it rebuilds the setup in miniature and runs it twice with everything identical except one switch.
- **visible:** agents see the board.
- **blind:** agents see nothing other agents wrote, though their own writes are still stored.

The published evidence statistics and an LLM judge are computed on both conditions. Whatever they report for blind runs is a false positive by construction. The same statistics also run on the real export.

**Report:** [report/Nullspace_final.pdf](report/Nullspace_final.pdf). Design, conditions, statistics and limitations: [DESIGN.md](DESIGN.md).

## Findings

- **Transmission happens only when agents can read.** Correct answers to future rounds: 3.67 (gpt-oss-20b) and 2.50 (qwen3.8-27b) per visible run, 1.00 and 0.33 per blind run, 0.75 by chance. Visible beat their paired blind run in 6 of 9 seeds with no reversals (one-sided sign-flip p = 0.016). `analysis/ground_truth_test.json`
- **A naive LLM judge calls 9 of 27 blind task groups coordinated** (33%, run-bootstrap 15 to 56%), citing a sequence the task gave every agent. Warning it about the shared prompt removes those false alarms and cuts detection from 81% to 30%. `analysis/summary.json`
- **Page concentration separates the conditions only through cohort dates in page names**; with those tokens removed, blind agents converge as much as visible ones.
- **Repeating earlier answers is not evidence of contact:** blind agents match an earlier answer about as often as visible ones (gpt-oss 49% vs 48%, Qwen 34% vs 48%). `analysis/agreement.json`
- **Blind-replay calibration works:** scoring judges against blind runs of the same agents holds every variant to at most 1 false alarm in 27 groups; the best keeps 16 of 27 detections. `analysis/replay.json`
- **Real archive:** the naive judge flags 11 of 17 windows from before the documented coordination onset (0 of 17 when warned). `analysis/bridge.json`

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install pytest numpy openai matplotlib
.venv/bin/python -m pytest -q                      # all tests
sh scripts_runall.sh "groq:openai/gpt-oss-20b@low" # pilot seed 101 + seeds 1-6, both conditions
sh scripts_runall.sh "groq:qwen/qwen3.8-27b"
.venv/bin/python -m nullspace.judge                                    # naive judge, gemini-3.5-flash-lite
.venv/bin/python -m nullspace.judge --informed --tag _informed         # confound-aware judge
.venv/bin/python -m nullspace.judge --provider groq --model openai/gpt-oss-120b --tag _strong
.venv/bin/python -m nullspace.judge --provider groq --model openai/gpt-oss-120b --tag _strong_informed --informed
.venv/bin/python -m nullspace.analyze   # writes analysis/*.json
.venv/bin/python -m nullspace.figures   # writes analysis/figures/
# real-window judges (needs the export): see nullspace/bridge.py judge_real_windows
```

- **Keys:** read from environment variables or `~/.config/nullspace.env`: `GROQ_API_KEYS` (comma-separated) and `GEMINI_API_KEY`.
- **Real-data statistics:** put the export's `revisions.jsonl` at `data/revisions.jsonl` (or set `NULLSPACE_REAL_EXPORT` to its path). The export isn't redistributed here; download it from collusion.wiki.
- **Model outputs:** provider models are not deterministic, so a rerun gives new model outputs. The task world for a given seed is identical in every process (tested).

## Layout

| Path | What |
|---|---|
| `nullspace/task.py` | task world: families, hidden sequences, staggered cohorts |
| `nullspace/board.py` | shared wiki; `visible` vs `blind` differ only in what reads return |
| `nullspace/prompts.py`, `sim.py` | the two-call agent protocol and one condition's run |
| `nullspace/features.py` | feature regexes: ours, plus Lütje's copied verbatim (`L_*`) |
| `nullspace/evidence.py` | exposure-adoption risk difference, first-line convergence, copying-model fit, occupancy |
| `nullspace/judge.py` | LLM judge (naive and confound-aware) |
| `nullspace/realdata.py` | loader for the real export (deltas from diff hunks) |
| `nullspace/analyze.py`, `figures.py` | every reported number and figure |
| `nullspace/bridge.py` | the real archive scored in 36-agent windows, before and after the coordination onset |
| `nullspace/replay.py` | auditor blind-replay test: each seed scored against the other seeds' blind runs (`analysis/replay.json`) |
| `report/` | the sprint report: Markdown source, docx builder, PDF |
| `runs/` | raw logs: every prompt, response and revision, plus the world |
| `superseded/` | first-pass runs, discarded because of a hash-seed bug in world generation (see DESIGN.md) |
