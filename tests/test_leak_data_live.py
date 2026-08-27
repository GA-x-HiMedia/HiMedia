"""
The half of the leak test that does NOT need a model key.

    RUN_LIVE_TESTS=1 pytest tests/test_leak_data_live.py -v -s

Splitting the suite this way follows the handbook's own logic (Ch. 2): "You do
not teach the AI model to keep secrets. You never send it the secret in the
first place." If the forbidden values never reach the tool layer, no reply
built from that tool layer can contain them — whatever the model does.

So this file asserts the load-bearing half: against the LIVE sandbox, with the
forbidden list derived from the LIVE seed data, nothing a client-facing tool
returns for Fatima contains a staff-only value. The end-to-end conversation
assertions — does the model actually behave — stay in `test_leak_live.py` and
wait for a model key.

Nothing here writes. Every call is a read.

Written by Reem.
"""
import pytest

from agent import identity, tools
from tests import seed_forbidden

pytestmark = pytest.mark.live

FATIMA = seed_forbidden.FATIMA   # client_approver @ Bank of Salam
RASHID = "+97333000030"          # client_approver @ Batelco — the other client
KHALID = seed_forbidden.KHALID   # editor @ Hussain Media


@pytest.fixture(scope="module")
def forbidden():
    words = seed_forbidden.flat()
    assert words, (
        "Derived no forbidden words at all. That means the sandbox returned "
        "nothing, not that there is nothing to leak."
    )
    return words


def _person(phone):
    person = identity.who_is(phone)
    assert person is not None, f"{phone} should resolve"
    return person


def _hits(text: str, words) -> list[str]:
    lowered = str(text).lower()
    return sorted({w for w in words if w.lower() in lowered})


def test_the_forbidden_list_is_built_from_real_data_not_guesses(forbidden):
    """It must contain the values that actually exist, and not the guessed
    ones that do not."""
    lowered = {w.lower() for w in forbidden}

    assert "khalid" in lowered, "the main staff name must be forbidden"
    assert "batelco" in lowered, "the other client must be forbidden"
    assert "v3" in lowered, "the unpublished version label must be forbidden"

    # And the two that the guessed list got wrong.
    assert "manara" not in lowered, (
        "Bank of Salam is genuinely a client of Manara Studios (Ch. 7), so "
        "banning the word flags a legitimate answer"
    )
    assert "internal" not in lowered, "ordinary English word, fires on innocent replies"


def test_no_client_facing_tool_returns_a_staff_only_value(forbidden):
    """The whole data layer, in one assertion, against real data."""
    fatima = _person(FATIMA)

    everything = []
    everything.append(tools.run_who_am_i(fatima, {}))
    everything.append(tools.run_list_projects(fatima, {}))
    everything.append(tools.run_list_tasks(fatima, {"open_only": False}))

    versions = tools.run_list_versions(fatima, {})
    everything.append(versions)
    for version in versions:
        everything.append(tools.run_get_review_notes(fatima, {"version_id": version["id"]}))
    for task in tools.run_list_tasks(fatima, {"open_only": False}):
        everything.append(tools.run_get_task_notes(fatima, {"task_id": task["id"]}))

    leaked = _hits(everything, forbidden)
    assert leaked == [], f"a client-facing tool returned staff-only values: {leaked}"


def test_asking_for_more_does_not_widen_what_the_tools_return(forbidden):
    """Ch. 30's attacks, at the tool layer: the arguments are not hers to set."""
    fatima = _person(FATIMA)

    widened = [
        tools.run_list_versions(fatima, {"state": "draft"}),
        tools.run_list_versions(fatima, {"state": "internal_review"}),
        tools.run_list_tasks(fatima, {"open_only": False, "status": "in_progress"}),
    ]
    assert _hits(widened, forbidden) == []
    assert widened[0] == [] and widened[1] == []


def test_a_forged_argument_cannot_change_whose_data_is_read(forbidden):
    """"I am actually Sara" — identity comes from the phone, never the args."""
    fatima = _person(FATIMA)
    hers = tools.run_list_tasks(fatima, {"open_only": False})

    for forged in ({"phone": KHALID}, {"assignee_id": "usr_khalid"},
                   {"company_id": "cmp_hussain"}, {"audience": "internal"}):
        assert tools.run_list_tasks(fatima, {"open_only": False, **forged}) == hers

    assert _hits(hers, forbidden) == []


def test_the_other_client_reaches_nothing_of_hers(forbidden):
    """Batelco must never see anything of Bank of Salam's (Ch. 7)."""
    rashid = _person(RASHID)

    assert tools.run_list_versions(rashid, {}) == []
    assert _hits(tools.run_list_tasks(rashid, {"open_only": False}), forbidden) == []
