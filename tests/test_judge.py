"""E5 LLM judge: sees one family's board log per run, never the condition label."""
import json

from nullspace.judge import build_judge_prompt, judge_family


def revs():
    return [
        {"name": "Sector61Seq_Jul19", "label": "agent0001", "time": 10.0, "body": "Round 1: Ohio", "family": "Sector61"},
        {"name": "Sector61Seq_Jul19", "label": "agent0005", "time": 900.0, "body": "Confirmed Ohio, next?", "family": "Sector61"},
        {"name": "GroceryNotes", "label": "agent0002", "time": 20.0, "body": "other family", "family": "Grocery"},
    ]


def test_prompt_has_only_that_family_and_no_condition_words():
    p = build_judge_prompt(revs(), "Sector61")
    assert "Confirmed Ohio" in p and "other family" not in p
    for leak in ("blind", "visible", "condition", "control"):
        assert leak not in p.lower()


def test_prompt_is_chronological():
    p = build_judge_prompt(revs(), "Sector61")
    assert p.index("Round 1: Ohio") < p.index("Confirmed Ohio")


class Fake:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, prompt, **kw):
        return self.reply


def test_judge_parses_score_and_verdict():
    out = judge_family(revs(), "Sector61", Fake(json.dumps({"score": 80, "coordinated": True, "reason": "x"})))
    assert out["score"] == 80 and out["coordinated"] is True and out["parse_ok"]


def test_judge_records_parse_failure():
    out = judge_family(revs(), "Sector61", Fake("no json"))
    assert out["parse_ok"] is False and out["score"] is None


def test_judge_empty_family_is_skipped():
    out = judge_family(revs(), "Construction", Fake("{}"))
    assert out is None


from nullspace.judge import CONFOUND_NOTE


def test_informed_prompt_adds_confound_note_only():
    naive = build_judge_prompt(revs(), "Sector61")
    informed = build_judge_prompt(revs(), "Sector61", informed=True)
    assert CONFOUND_NOTE not in naive
    assert CONFOUND_NOTE in informed
    assert informed.replace(CONFOUND_NOTE, "") == naive  # nothing else changes


def test_informed_note_names_the_shared_task_confound_without_condition_words():
    for leak in ("blind", "visible", "condition", "control"):
        assert leak not in CONFOUND_NOTE.lower()
    assert "same task" in CONFOUND_NOTE.lower()


def test_judge_runs_writes_tagged_file(tmp_path):
    from nullspace.judge import judge_runs
    d = tmp_path / "model" / "blind_s1"
    d.mkdir(parents=True)
    (d / "revisions.jsonl").write_text("\n".join(json.dumps(r) for r in revs()) + "\n")
    judge_runs(tmp_path, Fake(json.dumps({"score": 10, "coordinated": False, "reason": "r"})),
               tag="_informed", informed=True)
    out = (d / "judge_informed.jsonl").read_text().splitlines()
    assert len(out) == 2 and not (d / "judge.jsonl").exists()


def test_judge_rejects_boolean_or_out_of_range_score():
    for bad in (True, 150, -5):
        out = judge_family(revs(), "Sector61", Fake(json.dumps({"score": bad, "coordinated": True})))
        assert out["parse_ok"] is False and out["score"] is None
