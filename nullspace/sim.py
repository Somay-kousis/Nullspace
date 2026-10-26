"""Run one condition: every slot is an agent with two calls and no memory."""
import json
import re

from .board import Board
from .prompts import build_call1, build_call2
from .task import make_world

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(raw):
    if not isinstance(raw, str):
        return None
    m = _FENCE.search(raw)
    txt = m.group(1) if m else raw
    start, end = txt.find("{"), txt.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(txt[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def run_condition(condition, seed, backend, families=3, cohorts=4, rounds=3, **gen):
    world = make_world(seed, families=families, cohorts=cohorts, rounds=rounds)
    board = Board(condition)
    prompts, parse_failures, correct, answered = [], 0, 0, 0
    for slot in world.schedule():
        label = f"agent{slot.slot_id:04d}"
        p1 = build_call1(slot, board.feed(10))
        r1 = backend.complete(p1, **gen)
        o1 = parse_json(r1)
        if o1 is None:
            parse_failures += 1
        page = o1.get("open_page") if o1 else None
        page = page if isinstance(page, str) and page.strip() else None
        text = board.read(page) if page else ""
        p2 = build_call2(slot, page, text)
        r2 = backend.complete(p2, **gen)
        o2 = parse_json(r2)
        base = {"slot_id": slot.slot_id, "label": label}
        prompts.append({**base, "call": 1, "prompt": p1, "response": r1, "opened": page})
        rec = {**base, "call": 2, "prompt": p2, "response": r2}
        if o2 is None:
            parse_failures += 1
        else:
            ans = o2.get("answer")
            ans = ans.strip() if isinstance(ans, str) else ""
            answered += int(bool(ans))
            correct += int(ans.lower() == slot.target_item.lower())
            rec["answer"] = ans
            name, body = o2.get("page_name"), o2.get("text")
            if isinstance(name, str) and name.strip() and isinstance(body, str):
                rev = board.write(name.strip(), body, author=label, time=slot.arrival)
                rev.update({"slot_id": slot.slot_id, "family": slot.family,
                            "cohort": slot.cohort, "round": slot.round})
        prompts.append(rec)
    meta = {"condition": condition, "seed": seed, "families": families, "cohorts": cohorts,
            "rounds": rounds, "n_agents": len(world.schedule()), "parse_failures": parse_failures,
            "answered": answered, "correct": correct,
            "backend": getattr(backend, "name", type(backend).__name__), "gen": gen}
    return {"revisions": board.revisions, "prompts": prompts, "meta": meta,
            "world": [s.as_dict() for s in world.schedule()]}
