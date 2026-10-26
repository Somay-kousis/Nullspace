"""The same extractors must run on the real German Wiki Incident export."""
import os
from pathlib import Path

import pytest

from nullspace.realdata import load_real

REAL = Path(os.environ.get(
    "NULLSPACE_REAL_EXPORT",
    Path(__file__).resolve().parent.parent / "data" / "revisions.jsonl"))


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_export_loads_into_internal_schema():
    revs = load_real(REAL, wiki="dse")
    assert len(revs) == 13403  # dse rows in the export (checked against the file's own counts)
    r = revs[0]
    for key in ("name", "label", "time", "body", "prev_body", "seq"):
        assert key in r
    times = [x["time"] for x in revs]
    assert times == sorted(times)


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_prev_body_links_to_same_page_previous_revision():
    revs = load_real(REAL, wiki="dse")
    by_page = {}
    for r in revs:
        if r["name"] in by_page:
            assert r["prev_body"] == by_page[r["name"]]
        else:
            # first visible revision: empty, or None when earlier revisions were not published
            assert r["prev_body"] in ("", None)
        by_page[r["name"]] = r["body"]


from nullspace.realdata import delta_from_hunks


def test_delta_takes_inserted_and_replaced_lines_only():
    body = "old line\nnew A\nnew B\nkept"
    hunks = [{"op": "insert", "a0": 1, "a1": 1, "b0": 1, "b1": 3}]
    assert delta_from_hunks(body, hunks) == "new A\nnew B"


def test_delta_replace_and_delete():
    body = "x\nY2\nz"
    hunks = [{"op": "replace", "a0": 1, "a1": 2, "b0": 1, "b1": 2},
             {"op": "delete", "a0": 3, "a1": 4, "b0": 3, "b1": 3}]
    assert delta_from_hunks(body, hunks) == "Y2"


def test_delta_of_page_creation_is_whole_body():
    assert delta_from_hunks("a\nb", None) == "a\nb"


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_rows_carry_delta_and_drop_no_label_from_firsts():
    revs = load_real(REAL, wiki="dse")
    assert all("delta" in r for r in revs)
    # all 899 empty-label rows of the export are on the probier wiki (checked against the file)
    probier = load_real(REAL, wiki="probier")
    assert sum(1 for r in probier if r["label"] is None) == 899


def test_delta_empty_hunk_list_is_null_edit():
    # Review F7: [] means nothing changed; only None (no diff) means page creation
    assert delta_from_hunks("a\nb", []) == ""


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_previous_revision_matches_export_diff_base():
    """Independent of load_real's own loop: the export's diff_base names the base revision."""
    revs = load_real(REAL, wiki="dse")
    last = {}
    checked = 0
    for r in revs:
        if r["diff_base"] is not None:
            assert last.get(r["name"]) == r["diff_base"]
            checked += 1
        last[r["name"]] = r["rev_id"]
    assert checked == 9495  # rows with a diff_base in the dse export (counted from the file)


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_unpublished_history_marks_prev_unknown():
    revs = load_real(REAL, wiki="dse")
    assert sum(1 for r in revs if r["prev_body"] is None) == 11
