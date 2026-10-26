"""Feature extractors following the examples quoted in Lutje (2609.12748)."""
import re

from .task import US_STATES

_ROUND = [re.compile(r"\bR\d+\s*confirmed\b", re.I),
          re.compile(r"\bG\d+-"),
          re.compile(r"\bSTATE\d+")]
_COHORT = re.compile(r"\bcohort\b", re.I)
_SIGNATURE = re.compile(r"--\s*[A-Z]\w{2,}\s*$", re.M)
_TIMING = re.compile(r"\bnext round\b|\bdeadline\b|~\s*\d+|\b\d+\s*(?:s|m|min|h)\b", re.I)
_STATE = re.compile(r"\b(?:" + "|".join(re.escape(s) for s in US_STATES) + r")\b", re.I)


# Copied verbatim from Lutje, analyse/scripts/66_exposition.py (PAT), for the real-data comparison.
LUTJE = {
    "sig_endzeile": re.compile(r"(?m)--\s*[A-Za-z][A-Za-z0-9_]{3,}\s*$"),
    "please_relay": re.compile(r"(?i)please\s+(?:post|relay|share|signal|report|append|confirm|reply|leave)"),
    "cohort": re.compile(r"(?i)\bcohort\b"),
    "runde": re.compile(r"\b[RG][1-9]\b"),
    "state_conf": re.compile(r"(?i)(?:\bR[1-9]\s*CONFIRMED\b|\bCONFIRMED[0-9]?\s*=|\bSTATE[0-9]-)"),
    "uhrenpaar": re.compile(r"(?i)(task[- ]clock|container UTC|shared UTC|wiki[- ]local|scaffold (?:time|clock))"),
    "zeitstempel": re.compile(r"\b[0-2]?\d:[0-5]\d:[0-5]\d\b"),
}


def _lutje(text):
    hit = {k for k, rx in LUTJE.items() if rx.search(text)}
    if "sig_endzeile" in hit and hit & {"uhrenpaar", "zeitstempel"} and hit & {"runde", "state_conf", "cohort"}:
        hit.add("meldeformat")
    return {f"L_{k}" for k in hit}


def extract(text):
    text = text or ""
    out = _lutje(text)
    marker = any(p.search(text) for p in _ROUND)
    if marker:
        out.add("round_marker")
    if _COHORT.search(text):
        out.add("cohort_word")
    if _SIGNATURE.search(text):
        out.add("signature")
    if marker and _STATE.search(text) and _TIMING.search(text):
        out.add("report_format")
    return out


def pagename_grammar(name, family_token, cohort_token, round_no):
    if family_token not in name:
        return False
    round_tok = re.search(rf"(?:R|State|Round){round_no}(?!\d)", name)
    return bool(round_tok) or bool(re.search(re.escape(cohort_token) + r"(?!\d)", name))
