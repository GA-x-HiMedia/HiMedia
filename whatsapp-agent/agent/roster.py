"""
Phase 1 gate script (Chapter 31 — end-of-Day-2 gate):

    "One command prints a table of all thirteen people with their role,
    their permissions and how many tasks they can see. Real data, from
    the live API."

Run with:

    python -m agent.roster

Needs a working .env (HIMEDIA_BASE_URL + HIMEDIA_API_KEY) and network
access to the sandbox. Does NOT need OPENAI_API_KEY — no model is called
here, this only exercises identity.py and himedia.py.
"""
from __future__ import annotations

from . import himedia, identity

# The thirteen seeded people, straight from Chapter 8 of the handbook.
PHONES = [
    "+97333000001",  # Ahmed Al-Dosari, owner — Hussain Media
    "+97333000002",  # Sara Al-Ansari, supervisor — Hussain Media
    "+97333000003",  # Khalid Mansoor, editor — Hussain Media
    "+97333000004",  # Noor Habib, photographer — Hussain Media
    "+97333000005",  # Layla Ebrahim, account_manager — Hussain Media
    "+97333000006",  # Yusuf Rashed, accountant — Hussain Media
    "+97333000007",  # Maryam Salman, company_director — Hussain Media
    "+97333000010",  # Omar Al-Sayed, owner — Manara Studios
    "+97333000011",  # Hala Jassim, editor — Manara Studios
    "+97333000020",  # Fatima Al-Kooheji, client_approver — Bank of Salam
    "+97333000021",  # Ali Hasan, client_reviewer — Bank of Salam
    "+97333000022",  # Dana Fakhro, client_owner — Bank of Salam
    "+97333000030",  # Rashid Buali, client_approver — Batelco
]


def _granted_scopes(person: dict) -> str:
    """Prefer the API's own flat `scopes` list (Chapter 12); fall back to
    deriving it from `permissions` if that field isn't present."""
    scopes = person.get("scopes")
    if scopes:
        return ", ".join(scopes)
    perms = person.get("permissions", {})
    return ", ".join(f"{m}:{lvl}" for m, lvl in perms.items() if lvl != "none")


def _task_count(phone: str) -> int:
    """How many tasks this person can see — internal staff get their own
    assigned tasks, clients get the shared tasks on their projects
    (Chapter 17). Either way it's the same endpoint, filtered by the API
    itself based on who `phone` resolves to."""
    try:
        return himedia.get("/v1/tasks", phone=phone)["total"]
    except himedia.ApiRefused:
        return 0


def main() -> None:
    rows = []
    for phone in PHONES:
        person = identity.who_is(phone)
        if person is None:
            rows.append((phone, "\u2014 NOT FOUND \u2014", "", "", "", 0, None))
            continue
        rows.append((
            phone,
            person["user"]["full_name"],
            person["company"]["name"],
            person["role"]["key"],
            person["audience"],
            _task_count(phone),
            person,
        ))

    name_w = max(len(r[1]) for r in rows) + 2
    company_w = max(len(r[2]) for r in rows) + 2
    role_w = max(len(r[3]) for r in rows) + 2

    header = (
        f"{'PHONE':<15} {'NAME':<{name_w}} {'COMPANY':<{company_w}} "
        f"{'ROLE':<{role_w}} {'AUDIENCE':<10} {'TASKS':>5}"
    )
    print(header)
    print("-" * len(header))
    for phone, name, company, role, audience, tasks, _ in rows:
        print(f"{phone:<15} {name:<{name_w}} {company:<{company_w}} "
              f"{role:<{role_w}} {audience:<10} {tasks:>5}")

    found = sum(1 for r in rows if r[6] is not None)
    print(f"\n{found} of {len(PHONES)} people resolved against the live sandbox.")

    print("\nGranted scopes, per person:")
    for phone, name, company, role, audience, tasks, person in rows:
        if person is None:
            print(f"  {phone:<15} NOT FOUND")
            continue
        print(f"  {name:<20} {_granted_scopes(person)}")


if __name__ == "__main__":
    main()
