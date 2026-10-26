"""Load the real German Wiki Incident export (collusion.wiki) into the internal schema."""
import json
from datetime import datetime


def _epoch(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def delta_from_hunks(body, hunks):
    """Text a revision added: the new-side lines of insert and replace hunks."""
    lines = body.split("\n")
    if hunks is None:
        return body
    if not hunks:
        return ""
    added = []
    for h in hunks:
        if h["op"] in ("insert", "replace"):
            added.extend(lines[h["b0"]:h["b1"]])
    return "\n".join(added)


def load_real(path, wiki="dse"):
    rows = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if wiki and r.get("wiki") != wiki:
                continue
            rows.append(r)
    rows.sort(key=lambda r: (r["time"], r["name"], r["seq"]))
    latest, out = {}, []
    for r in rows:
        body = r.get("body") or ""
        hunks = None if r.get("diff_base_reason") == "page_created" else r.get("hunks")
        unknown = r.get("diff_base_reason") == "earlier_revisions_not_published"
        out.append({"name": r["name"], "label": r.get("label") or None, "time": _epoch(r["time"]),
                    "body": body, "delta": delta_from_hunks(body, hunks), "seq": r["seq"],
                    "prev_body": None if unknown else latest.get(r["name"], ""),
                    "rev_id": r["rev_id"], "diff_base": r.get("diff_base")})
        latest[r["name"]] = body
    return out
