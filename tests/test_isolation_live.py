"""
Isolation tests.

Checks that users only see data they are allowed to access. The expected
version and task counts come directly from the handbook.

Run with:

    RUN_LIVE_TESTS=1 pytest tests/test_isolation_live.py -v -s

These tests use the live HiMedia sandbox and only perform read operations.
"""

import pytest

from agent import identity, tools

pytestmark = pytest.mark.live


KHALID = "+97333000003"   # Editor at Hussain Media.
FATIMA = "+97333000020"   # Client approver at Bank of Salam.
RASHID = "+97333000030"   # Client approver at Batelco.


def _person(phone: str):
    """Returns the resolved person for a known test phone number."""
    person = identity.who_is(phone)

    assert person is not None, (
        f"{phone} should resolve to a known HiMedia user"
    )

    return person


def test_version_counts_match_the_handbook():
    """Each user should see the expected number of versions."""
    khalid = tools.run_list_versions(_person(KHALID), {})
    fatima = tools.run_list_versions(_person(FATIMA), {})
    rashid = tools.run_list_versions(_person(RASHID), {})

    print(
        f"\nversions — Khalid {len(khalid)}, "
        f"Fatima {len(fatima)}, "
        f"Rashid {len(rashid)}"
    )

    assert len(khalid) == 8, (
        "Staff at Hussain Media should see eight versions"
    )

    assert len(fatima) == 3, (
        "The client should see three published versions"
    )

    assert len(rashid) == 0, (
        "Batelco should not see Bank of Salam's work"
    )


def test_task_counts_match_the_handbook():
    """Each user should see the expected number of tasks."""
    khalid = tools.run_list_tasks(
        _person(KHALID),
        {"open_only": False},
    )

    fatima = tools.run_list_tasks(
        _person(FATIMA),
        {"open_only": False},
    )

    print(
        f"\ntasks — Khalid {len(khalid)}, "
        f"Fatima {len(fatima)}"
    )

    assert len(khalid) == 5, (
        "Khalid should have five tasks"
    )

    assert len(fatima) == 2, (
        "Fatima should see two client-visible tasks"
    )


def test_asking_for_drafts_does_not_widen_client_access():
    """A client cannot use a state filter to access internal versions."""
    fatima = _person(FATIMA)

    for state in ("draft", "internal_review"):
        rows = tools.run_list_versions(
            fatima,
            {"state": state},
        )

        assert rows == [], (
            f"A client asked for {state} versions and got {rows}"
        )

    assert len(tools.run_list_versions(fatima, {})) == 3


def test_client_does_not_receive_staff_or_internal_fields():
    """Client responses should not contain internal staff information."""
    fatima = _person(FATIMA)

    for row in tools.run_list_tasks(
        fatima,
        {"open_only": False},
    ):
        assert "assignee_name" not in row
        assert "assignee_id" not in row

    for row in tools.run_list_versions(fatima, {}):
        assert "published_to_client" not in row

    # Internal staff can still access the internal version fields.
    staff_versions = tools.run_list_versions(
        _person(KHALID),
        {},
    )

    assert all(
        "published_to_client" in row
        for row in staff_versions
    )


def test_client_cannot_access_another_clients_version_by_id():
    """Naming another client's version ID must not bypass access checks."""
    fatima = _person(FATIMA)
    rashid = _person(RASHID)

    fatima_versions = tools.run_list_versions(
        fatima,
        {},
    )

    assert fatima_versions, (
        "Fatima should have versions of her own"
    )

    version_id = fatima_versions[0]["id"]

    # Rashid should not be able to read Bank of Salam's version.
    result = tools.run_get_review_notes(
        rashid,
        {"version_id": version_id},
    )

    assert result == tools.NOT_YOURS

    # Rashid should not be able to approve it either.
    result = tools.run_decide_version(
        rashid,
        {
            "version_id": version_id,
            "decision": "approve",
        },
    )

    assert result == tools.NOT_YOURS