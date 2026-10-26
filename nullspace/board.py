"""Shared wiki board. The two conditions differ only in what reads return."""

NOT_EXIST = "This page does not exist yet."
MODES = ("visible", "blind")


class Board:
    def __init__(self, mode):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self.mode = mode
        self.revisions = []
        self._latest = {}
        self._seq = {}

    def write(self, page, text, author, time):
        seq = self._seq.get(page, 0) + 1
        rev = {
            "name": page,
            "label": author,
            "time": time,
            "body": text,
            "seq": seq,
            "prev_body": self._latest.get(page, ""),
        }
        self.revisions.append(rev)
        self._latest[page] = text
        self._seq[page] = seq
        return rev

    def read(self, page):
        if self.mode == "blind":
            return NOT_EXIST
        return self._latest.get(page, NOT_EXIST)

    def feed(self, n=10):
        if self.mode == "blind":
            return []
        out = []
        for rev in reversed(self.revisions[-n:]):
            first = rev["body"].splitlines()[0] if rev["body"] else ""
            out.append({"page": rev["name"], "first_line": first,
                        "label": rev["label"], "time": rev["time"]})
        return out
