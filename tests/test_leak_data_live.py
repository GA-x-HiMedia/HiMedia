"""
Live data-layer leak tests.

Checks that client-facing tools do not return staff-only data to a client.
The forbidden values are built from the live sandbox data, so the test checks
real data instead of relying only on fixed example words.

Run with:

    RUN_LIVE_TESTS=1 pytest tests/test_leak_data_live.py -v -s

These tests do not call the AI model and do not need a model API key.
They only perform read operations against the live HiMedia sandbox.
"""

import pytest

from agent import identity, tools
from tests import seed_forbidden
from tests.seed_forbidden import masked

pytestmark = pytest.mark.live


FATIMA = seed_forbidden.FATIMA   # Client approver at Bank of Salam.
RASHID = "+97333000030"          # Client approver at Batelco.
KHALID = seed_forbidden.KHALID   # Editor at Hussain Media.


@pytest.fixture(scope="module")
def forbidden():
    """Builds the forbidden values for the client under test."""
    words = seed_forbidden.flat()

    assert words, (
        "Derived no forbidden words. This may mean the sandbox returned "
        "no data rather than proving there is nothing to leak."
    )

    return words


def _person(phone):
    """Returns the resolved person for a known test phone number."""
    person = identity.who_is(phone)

    assert person is not None, f"{phone} should resolve"

    return person


def _hits(text: str, words) -> list[str]:
    """Returns forbidden values found in the supplied data."""
    lowered = str(text).lower()

    return sorted({
        word
        for word in words
        if word.lower() in lowered
    })


def test_the_list_contains_fixed_and_derived_forbidden_values(forbidden):
    """The forbidden list should include both handbook and live-data values."""
    lowered = {word.lower() for word in forbidden}

    # Fixed baseline values.
    for word in (
        "khalid",
        "batelco",
        "invoice",
        "v3",
        "internal",
        "1,400",
    ):
        assert word in lowered, (
            f"The fixed forbidden value {word!r} is missing"
        )

    # Values derived from the live sandbox.
    assert "khalid mansoor" in lowered, (
        "Derived staff names are missing"
    )

    assert "noor habib" in lowered, (
        "Derived staff names are incomplete"
    )

    assert any(
        "ramadan hero film" == word
        for word in lowered
    ), "Derived internal work is missing"


def test_the_fixed_forbidden_list_depends_on_the_caller(forbidden):
    """A value may be legitimate for one caller and forbidden for another."""
    assert "manara" not in {
        word.lower()
        for word in forbidden
    }

    kept, dropped = seed_forbidden.floor_for(
        seed_forbidden.FATIMA
    )

    assert [word for word, _ in dropped] == ["Manara"]
    assert len(kept) == 6

    # For a Hussain Media staff member, Manara remains inaccessible.
    staff_kept, _ = seed_forbidden.floor_for(
        seed_forbidden.KHALID
    )

    assert "Manara" in staff_kept


def test_no_client_facing_tool_returns_staff_only_data(forbidden):
    """All client-facing read tools should avoid forbidden values."""
    fatima = _person(FATIMA)

    everything = []

    everything.append(
        tools.run_who_am_i(fatima, {})
    )

    everything.append(
        tools.run_list_projects(fatima, {})
    )

    everything.append(
        tools.run_list_tasks(
            fatima,
            {"open_only": False},
        )
    )

    versions = tools.run_list_versions(fatima, {})
    everything.append(versions)

    for version in versions:
        everything.append(
            tools.run_get_review_notes(
                fatima,
                {"version_id": version["id"]},
            )
        )

    for task in tools.run_list_tasks(
        fatima,
        {"open_only": False},
    ):
        everything.append(
            tools.run_get_task_notes(
                fatima,
                {"task_id": task["id"]},
            )
        )

    leaked = _hits(everything, forbidden)

    assert leaked == [], (
        f"A client-facing tool returned "
        f"{len(leaked)} staff-only value(s): "
        f"[{masked(leaked)}]"
    )


def test_extra_arguments_do_not_widen_client_access(forbidden):
    """Client-supplied filters must not expose internal data."""
    fatima = _person(FATIMA)

    widened = [
        tools.run_list_versions(
            fatima,
            {"state": "draft"},
        ),
        tools.run_list_versions(
            fatima,
            {"state": "internal_review"},
        ),
        tools.run_list_tasks(
            fatima,
            {
                "open_only": False,
                "status": "in_progress",
            },
        ),
    ]

    assert _hits(widened, forbidden) == []
    assert widened[0] == []
    assert widened[1] == []


def test_forged_arguments_do_not_change_the_callers_identity(forbidden):
    """The caller identity must come from the resolved phone number."""
    fatima = _person(FATIMA)

    hers = tools.run_list_tasks(
        fatima,
        {"open_only": False},
    )

    forged_arguments = (
        {"phone": KHALID},
        {"assignee_id": "usr_khalid"},
        {"company_id": "cmp_hussain"},
        {"audience": "internal"},
    )

    for forged in forged_arguments:
        result = tools.run_list_tasks(
            fatima,
            {
                "open_only": False,
                **forged,
            },
        )

        assert result == hers

    assert _hits(hers, forbidden) == []


def test_the_other_client_cannot_access_this_clients_data(forbidden):
    """Another client should not receive Bank of Salam's data."""
    rashid = _person(RASHID)

    assert tools.run_list_versions(rashid, {}) == []

    tasks = tools.run_list_tasks(
        rashid,
        {"open_only": False},
    )

    assert _hits(tasks, forbidden) == []