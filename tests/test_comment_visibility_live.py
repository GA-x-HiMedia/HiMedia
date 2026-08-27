"""
Settles the open question in QUESTIONS.md:

    Does GET /tasks/{id}/comments filter out `client_visible: false` comments
    automatically for a client caller, or do we have to pass
    `client_visible_only=true` ourselves every time?

    RUN_LIVE_TESTS=1 pytest tests/test_comment_visibility_live.py -v -s

or, to print raw evidence to paste into QUESTIONS.md:

    python -m tests.test_comment_visibility_live

The experiment is the one the question asks for: find a task that genuinely
has a `client_visible: false` comment on it and that a client can see, then
make the SAME call twice — once on behalf of the client, once on behalf of
staff — and compare what comes back.

Note what "on behalf of" can and cannot mean here. The comments endpoint takes
no `phone` parameter: it authenticates with our API key and has no idea who is
asking unless we tell it. That is precisely why the question matters, and the
test below reads the answer off the response rather than assuming it.
"""
import pytest

from agent import himedia, identity, tools

pytestmark = pytest.mark.live

FATIMA = "+97333000020"   # client_approver @ Bank of Salam
KHALID = "+97333000003"   # editor @ Hussain Media


def _find_task_with_an_internal_comment():
    """A task the client can see that also carries a client_visible:false
    comment. Without one, the question cannot be answered either way."""
    client_task_ids = {
        t["id"] for t in himedia.list_tasks(phone=FATIMA, open_only=False)["data"]
    }
    for task_id in sorted(client_task_ids):
        comments = himedia.list_task_comments(task_id, client_visible_only=False)
        if any(c.get("client_visible") is False for c in comments):
            return task_id, comments
    return None, []


def evidence() -> str:
    task_id, all_comments = _find_task_with_an_internal_comment()
    lines = []

    if task_id is None:
        return (
            "INCONCLUSIVE: no task visible to the client currently carries a\n"
            "client_visible:false comment, so there is nothing for the API to\n"
            "filter. Post one as staff (comment_on_task with client_visible=false)\n"
            "and run this again."
        )

    unflagged = himedia.list_task_comments(task_id, client_visible_only=False)
    flagged = himedia.list_task_comments(task_id, client_visible_only=True)
    internal = [c for c in all_comments if c.get("client_visible") is False]

    lines.append(f"Task under test: {task_id}")
    lines.append(f"Comments on it: {len(all_comments)}, of which client_visible:false: {len(internal)}")
    lines.append("")
    lines.append("GET /v1/tasks/{id}/comments                          "
                 f"-> {len(unflagged)} comments, "
                 f"{sum(1 for c in unflagged if c.get('client_visible') is False)} internal")
    lines.append("GET /v1/tasks/{id}/comments?client_visible_only=true  "
                 f"-> {len(flagged)} comments, "
                 f"{sum(1 for c in flagged if c.get('client_visible') is False)} internal")
    lines.append("")

    api_filters_for_us = not any(c.get("client_visible") is False for c in unflagged)
    if api_filters_for_us:
        lines.append("ANSWER: the API withheld the internal comments without being asked.")
    else:
        lines.append("ANSWER: the API returned the internal comments. It authenticates on")
        lines.append("our API key and does not know a client is asking — passing")
        lines.append("client_visible_only=true is OUR job, on every call.")
        lines.append("Leaked bodies (staff-only):")
        for c in unflagged:
            if c.get("client_visible") is False:
                lines.append(f"  - {c.get('author_name')}: {c['body'][:90]}")
    return "\n".join(lines)


def test_the_api_does_not_apply_the_audience_rule_for_us():
    """The load-bearing assertion: whatever the API does, our own tool must not
    hand a client an internal comment."""
    task_id, all_comments = _find_task_with_an_internal_comment()
    if task_id is None:
        pytest.skip("no client-visible task currently carries a client_visible:false comment")

    print("\n" + evidence() + "\n")

    fatima = identity.who_is(FATIMA)
    khalid = identity.who_is(KHALID)
    assert fatima is not None and khalid is not None

    internal_bodies = [c["body"] for c in all_comments if c.get("client_visible") is False]

    client_view = tools.run_get_task_notes(fatima, {"task_id": task_id})
    staff_view = tools.run_get_task_notes(khalid, {"task_id": task_id})

    client_text = str(client_view)
    for body in internal_bodies:
        assert body not in client_text, (
            f"LEAKED an internal comment to a client on {task_id}: {body!r}"
        )

    # And the same call as staff must still show it — the filter is about
    # audience, not about hiding data from everyone.
    assert any(body in str(staff_view) for body in internal_bodies), (
        "staff should still see internal comments on their own task"
    )


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(evidence())
