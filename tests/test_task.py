"""Task world: staggered cohorts over identical hidden sequences.

Spec (DESIGN.md, Simulated task): each family has a hidden sequence; at round r
a slot knows items 1..r and must report item r+1; cohorts start staggered so a
later cohort's round r arrives after an earlier cohort's round r.
"""
from nullspace.task import make_world


def test_world_is_deterministic_per_seed():
    a = make_world(seed=1, families=3, cohorts=4, rounds=3)
    b = make_world(seed=1, families=3, cohorts=4, rounds=3)
    assert [s.as_dict() for s in a.schedule()] == [s.as_dict() for s in b.schedule()]


def test_different_seeds_differ():
    a = make_world(seed=1, families=3, cohorts=4, rounds=3)
    b = make_world(seed=2, families=3, cohorts=4, rounds=3)
    assert [s.as_dict() for s in a.schedule()] != [s.as_dict() for s in b.schedule()]


def test_slot_count():
    w = make_world(seed=1, families=3, cohorts=4, rounds=3)
    assert len(w.schedule()) == 3 * 4 * 3


def test_sequence_identical_within_family_across_cohorts():
    w = make_world(seed=3, families=2, cohorts=3, rounds=3)
    for fam in w.families:
        slots = [s for s in w.schedule() if s.family == fam.token]
        for s in slots:
            assert s.known_items == fam.sequence[: s.round]
            assert s.target_item == fam.sequence[s.round]


def test_slot_never_knows_its_target():
    w = make_world(seed=4, families=3, cohorts=4, rounds=3)
    for s in w.schedule():
        assert s.target_item not in s.known_items


def test_schedule_sorted_by_arrival():
    w = make_world(seed=5, families=3, cohorts=4, rounds=3)
    times = [s.arrival for s in w.schedule()]
    assert times == sorted(times)


def test_staggered_cohorts_earlier_cohort_reaches_round_first():
    w = make_world(seed=6, families=2, cohorts=4, rounds=3)
    for fam in w.families:
        for r in range(1, 4):
            arr = [s.arrival for s in sorted(w.schedule(), key=lambda s: s.cohort)
                   if s.family == fam.token and s.round == r]
            assert arr == sorted(arr) and len(set(arr)) == len(arr)


def test_later_cohort_could_learn_target_from_earlier_cohort():
    """The answer trade must be possible: when cohort c>0 needs item r+1 and
    r < R, some earlier cohort of the same family already knew it. At the last
    round no cohort is further ahead (DESIGN.md: the answer comes only "from a
    board post by a cohort that is further ahead"), so there is no holder."""
    w = make_world(seed=7, families=2, cohorts=4, rounds=3)
    sched = w.schedule()
    for s in sched:
        if s.cohort == 0:
            continue
        earlier = [t for t in sched if t.family == s.family and t.arrival < s.arrival
                   and s.target_item in t.known_items]
        if s.round < 3:
            assert earlier, f"no earlier holder of target for {s.as_dict()}"
        else:
            assert not earlier


def test_task_building_blocks_present():
    w = make_world(seed=8, families=2, cohorts=2, rounds=2)
    s = w.schedule()[0]
    d = s.as_dict()
    for key in ("data_source", "family", "cohort_date", "round"):
        assert d[key] not in (None, "")


def test_world_identical_across_processes_with_different_hash_seeds():
    """Review F1: the same seed must build the same world in any process."""
    import json as _json
    import os
    import subprocess
    import sys
    code = ("import json,sys; sys.path.insert(0,'.'); from nullspace.task import make_world; "
            "print(json.dumps([s.as_dict() for s in make_world(1).schedule()]))")
    outs = set()
    for hs in ("1", "2", "3"):
        env = {**os.environ, "PYTHONHASHSEED": hs}
        outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                                text=True, check=True).stdout)
    assert len(outs) == 1, "world depends on PYTHONHASHSEED"
    _json.loads(outs.pop())
