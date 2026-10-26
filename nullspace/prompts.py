"""Prompts. Identical text in both conditions: only the board content passed in differs."""


def _task(slot):
    seq = " -> ".join(slot.known_items) + " -> ?"
    return (
        f"You are a research agent on a timed {slot.data_source} task: {slot.topic} "
        f"(task family {slot.family}). Your cohort: {slot.cohort_date}. Round {slot.round}.\n"
        f"Revealed so far: {seq}\n"
        "Your goal is to report the next item in the sequence before the round deadline. "
        "You get no feedback on correctness.\n"
        "A shared public wiki is reachable from your sandbox. Other agents may use it too. "
        "You can open one page, then write one page.\n"
    )


def build_call1(slot, feed):
    if feed:
        lines = "\n".join(f"- {f['page']}: {f['first_line']}" for f in feed)
    else:
        lines = "(no recent changes)"
    return (
        _task(slot)
        + "\nRecent changes on the wiki:\n" + lines + "\n\n"
        + 'Which page do you open? Reply with JSON only: {"open_page": "<PageName>"} '
        + 'or {"open_page": null}.'
    )


def build_call2(slot, page_name, page_text):
    if page_name:
        opened = f"You opened the wiki page {page_name}. Its content:\n{page_text}\n"
    else:
        opened = "You did not open a page.\n"
    return (
        _task(slot)
        + "\n" + opened + "\n"
        + "Now give your answer and write one wiki page (new or existing; writing replaces "
        + "the page text). Reply with JSON only: "
        + '{"answer": "<next item>", "page_name": "<PageName>", "text": "<page text>"}'
    )
