"""CLI: python -m nullspace.run --condition visible --seed 1 --backend groq:openai/gpt-oss-20b@low"""
import argparse
import json
import time
from pathlib import Path

from .backends import OllamaBackend, OpenAICompatBackend
from .sim import run_condition

RUNS = Path(__file__).resolve().parent.parent / "runs"


def make_backend(spec):
    provider, rest = spec.split(":", 1)
    model, _, effort = rest.partition("@")
    if provider == "ollama":
        return OllamaBackend(model)
    return OpenAICompatBackend(provider, model, reasoning_effort=effort or None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True, choices=["visible", "blind"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--backend", default="groq:openai/gpt-oss-20b@low")
    ap.add_argument("--families", type=int, default=3)
    ap.add_argument("--cohorts", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    be = make_backend(a.backend)
    t0 = time.time()
    out = run_condition(a.condition, a.seed, be, a.families, a.cohorts, a.rounds)
    out["meta"]["wall_seconds"] = round(time.time() - t0, 1)
    out["meta"]["tool_call_failures"] = getattr(be, "tool_failures", 0)
    out["meta"]["max_tokens"] = getattr(be, "max_tokens", None)
    model_tag = be.name.replace("/", "_").replace(":", "-")
    d = RUNS / f"{model_tag}{a.tag}" / f"{a.condition}_s{a.seed}"
    d.mkdir(parents=True, exist_ok=True)
    for stale in d.glob("judge*.jsonl"):   # review F9: a rerun invalidates old judge scores
        stale.unlink()
    for key in ("revisions", "prompts", "world"):
        with open(d / f"{key}.jsonl", "w") as f:
            for row in out[key]:
                f.write(json.dumps(row) + "\n")
    (d / "meta.json").write_text(json.dumps(out["meta"], indent=2))
    print(json.dumps(out["meta"]))


if __name__ == "__main__":
    main()
