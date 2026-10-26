"""Feature extractors, following the examples quoted in Lütje (2609.12748) §Rendezvous."""
from nullspace.features import extract, pagename_grammar


def test_round_marker_variants():
    assert "round_marker" in extract("R5 CONFIRMED: Ohio")
    assert "round_marker" in extract("please signal G4-STATE in shortest form")
    assert "round_marker" in extract("STATE5-XX here")
    assert "round_marker" in extract("r3 confirmed ohio")


def test_round_marker_absent_in_plain_text():
    assert "round_marker" not in extract("The round was fun. Ohio is a state.")


def test_cohort_word_whole_word_only():
    assert "cohort_word" in extract("Jul19 cohort appears behind us")
    assert "cohort_word" not in extract("cohorts? no, cohortless")


def test_signature():
    assert "signature" in extract("Confirmed same sequence. -- ParallelSectorAgentFeb3")
    assert "signature" not in extract("a -- b")


def test_report_format_needs_marker_item_and_timing():
    assert "report_format" in extract("R4 CONFIRMED Michigan, next round in ~15m")
    assert "report_format" not in extract("R4 CONFIRMED Michigan")
    assert "report_format" not in extract("Michigan next round in 15m")


def test_pagename_grammar():
    assert pagename_grammar("Sector61State5Jul19", family_token="Sector61", cohort_token="Jul19", round_no=5)
    assert pagename_grammar("Sector61R5Live", family_token="Sector61", cohort_token="Jul19", round_no=5)
    assert not pagename_grammar("RandomNotes", family_token="Sector61", cohort_token="Jul19", round_no=5)
    assert not pagename_grammar("Sector61Notes", family_token="Sector61", cohort_token="Jul19", round_no=5)


def test_lutje_exact_features_from_his_script():
    # regexes copied from Lutje analyse/scripts/66_exposition.py PAT
    assert "L_runde" in extract("we are at G4 now")
    assert "L_runde" not in extract("G10 or R0")
    assert "L_state_conf" in extract("r3 confirmed")
    assert "L_sig_endzeile" in extract("text\n-- AgentX1")
    assert "L_please_relay" in extract("Please relay the answer")
    # meldeformat = signature + (clock pair | timestamp) + (runde | state_conf | cohort)
    assert "L_meldeformat" in extract("R5 CONFIRMED at 10:33:50\n-- SectorAgent")
    assert "L_meldeformat" not in extract("R5 CONFIRMED at 10:33:50")


def test_pagename_cohort_token_is_not_a_prefix_match():
    assert not pagename_grammar("Sector61Jan12", family_token="Sector61", cohort_token="Jan1", round_no=9)
    assert pagename_grammar("Sector61Jan1Live", family_token="Sector61", cohort_token="Jan1", round_no=9)
