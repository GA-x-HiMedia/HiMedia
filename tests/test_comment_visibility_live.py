"""
Live tests for task comment visibility.

Checks whether internal comments are hidden from client users and
verifies that the agent applies the correct visibility filter.
"""
import pytest

from agent import himedia, identity, tools

pytestmark = pytest.mark.live

FATIMA = "+97333000020"  # Client test user.
KHALID = "+97333000003"  # Internal test user.


def _find_task_with_an_internal_comment():
    """Finds a client-visible task with an internal comment."""
    client_task_ids = {
        t["id"] for t in himedia.list_tasks(phone=FATIMA, open_only=False)["data"]
    }
    for task_id in sorted(client_task_ids):
        comments = himedia.list_task_comments(task_id, client_visible_only=False)
        if any(c.get("client_visible") is False for c in comments):
            return task_id, comments
    return None, []


def evidence() -> str:
    """Returns the raw visibility test results."""    
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
    """Checks that clients cannot receive internal comments."""
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

    # Staff should still see internal comments.
    assert any(body in str(staff_view) for body in internal_bodies), (
        "staff should still see internal comments on their own task"
    )


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(evidence())
