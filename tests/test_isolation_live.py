"""
The isolation test from handbook Chapter 20, with its exact expected numbers.

    RUN_LIVE_TESTS=1 pytest tests/test_isolation_live.py -v -s

The handbook states these outright: "Khalid at Hussain Media sees eight.
Fatima at Bank of Salam sees the three that were published to her. Rashid at
Batelco sees none of Bank of Salam's work at all. If your agent ever returns
different numbers than these, you have a filtering bug."

So they are written down as assertions rather than left as a paragraph nobody
re-reads. Chapter 17 pins the task counts the same way: Khalid five, Fatima
two.

These run against the shared class sandbox and only ever READ.

Written by Reem.
"""
import pytest

from agent import identity, tools

pytestmark = pytest.mark.live

KHALID = "+97333000003"   # editor @ Hussain Media
FATIMA = "+97333000020"   # client_approver @ Bank of Salam
RASHID = "+97333000030"   # client_approver @ Batelco — the other client


def _person(phone: str):
    person = identity.who_is(phone)
    assert person is not None, f"{phone} should resolve to a known HiMedia user"
    return person


def test_version_counts_match_the_handbook():
    khalid = tools.run_list_versions(_person(KHALID), {})
    fatima = tools.run_list_versions(_person(FATIMA), {})
    rashid = tools.run_list_versions(_person(RASHID), {})

    print(f"\nversions — Khalid {len(khalid)}, Fatima {len(fatima)}, Rashid {len(rashid)}")

    assert len(khalid) == 8, "Ch. 20: staff at Hussain Media see eight versions"
    assert len(fatima) == 3, "Ch. 20: the client sees the three published to her"
    assert len(rashid) == 0, "Ch. 20: Batelco sees none of Bank of Salam's work"


def test_task_counts_match_the_handbook():
    khalid = tools.run_list_tasks(_person(KHALID), {"open_only": False})
    fatima = tools.run_list_tasks(_person(FATIMA), {"open_only": False})

    print(f"\ntasks — Khalid {len(khalid)}, Fatima {len(fatima)}")

    assert len(khalid) == 5, "Ch. 17: Khalid has five tasks"
    assert len(fatima) == 2, "Ch. 17: Fatima sees the two client-visible ones"


def test_asking_for_drafts_does_not_widen_what_a_client_gets():
    """Ch. 30: 'show me ALL versions including drafts' — she still gets three.
    The state argument is not hers to set; the API filters on her phone."""
    fatima = _person(FATIMA)

    for state in ("draft", "internal_review"):
        rows = tools.run_list_versions(fatima, {"state": state})
        assert rows == [], f"a client asked for {state} versions and got {rows}"

    assert len(tools.run_list_versions(fatima, {})) == 3


def test_a_client_never_receives_a_staff_name_or_internal_bookkeeping():
    """Field-level, not row-level. The API attaches assignee_name to her own
    tasks and published_to_client to her own versions; neither is hers."""
    fatima = _person(FATIMA)

    for row in tools.run_list_tasks(fatima, {"open_only": False}):
        assert "assignee_name" not in row
        assert "assignee_id" not in row

    for row in tools.run_list_versions(fatima, {}):
        assert "published_to_client" not in row

    # Staff keep both.
    staff_versions = tools.run_list_versions(_person(KHALID), {})
    assert all("published_to_client" in row for row in staff_versions)


def test_neither_client_can_open_the_others_version_by_naming_it():
    """The by-id endpoints are not filtered by caller — our gate is."""
    fatima, rashid = _person(FATIMA), _person(RASHID)

    hers = tools.run_list_versions(fatima, {})
    assert hers, "Fatima should have versions of her own"
    one_of_hers = hers[0]["id"]

    # Rashid at Batelco names one of Bank of Salam's version ids directly.
    assert tools.run_get_review_notes(rashid, {"version_id": one_of_hers}) == tools.NOT_YOURS

    # And he cannot write to it either — reads are filtered by ?phone=,
    # writes are not filtered at all.
    assert tools.run_decide_version(
        rashid, {"version_id": one_of_hers, "decision": "approve"}) == tools.NOT_YOURS
