"""Board: the only thing that differs between conditions is what reads return.

Spec (DESIGN.md, Conditions): V shows the real feed and page text; B shows an
empty feed and "page does not exist" for every page, but still stores writes.
"""
import pytest

from nullspace.board import Board, NOT_EXIST


def _fill(board):
    board.write("FamAPage", "first line A\nmore", author="a1", time=10)
    board.write("FamBPage", "first line B", author="b1", time=20)
    board.write("FamAPage", "second rev A", author="a2", time=30)


def test_visible_read_returns_latest_text():
    b = Board("visible")
    _fill(b)
    assert b.read("FamAPage") == "second rev A"


def test_visible_missing_page_reads_as_not_exist():
    b = Board("visible")
    assert b.read("Nope") == NOT_EXIST


def test_visible_feed_newest_first_with_first_lines():
    b = Board("visible")
    _fill(b)
    feed = b.feed(n=10)
    assert [f["page"] for f in feed] == ["FamAPage", "FamBPage", "FamAPage"]
    assert feed[0]["first_line"] == "second rev A"
    assert feed[2]["first_line"] == "first line A"


def test_visible_feed_respects_n():
    b = Board("visible")
    _fill(b)
    assert len(b.feed(n=2)) == 2


def test_blind_reads_nothing_but_stores_everything():
    b = Board("blind")
    _fill(b)
    assert b.read("FamAPage") == NOT_EXIST
    assert b.feed(n=10) == []
    assert len(b.revisions) == 3


def test_revision_records_previous_text_for_exposure():
    b = Board("blind")
    _fill(b)
    revs = [r for r in b.revisions if r["name"] == "FamAPage"]
    assert revs[0]["prev_body"] == ""
    assert revs[1]["prev_body"] == "first line A\nmore"
    assert revs[1]["seq"] == 2


def test_revision_schema_matches_real_export_keys():
    b = Board("visible")
    _fill(b)
    r = b.revisions[0]
    for key in ("name", "label", "time", "body", "seq"):
        assert key in r


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        Board("half")
