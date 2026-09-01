"""Displays all seeded HiMedia users and their access details.

Run with:

    python -m agent.roster
"""

from __future__ import annotations

from . import himedia, identity


# Seeded users used for testing the API.

PHONES = [ 
    "+97333000001", # Ahmed Al-Dosari, owner — Hussain Media 
    "+97333000002", # Sara Al-Ansari, supervisor — Hussain Media 
    "+97333000003", # Khalid Mansoor, editor — Hussain Media 
    "+97333000004", # Noor Habib, photographer — Hussain Media 
    "+97333000005", # Layla Ebrahim, account_manager — Hussain Media 
    "+97333000006", # Yusuf Rashed, accountant — Hussain Media 
    "+97333000007", # Maryam Salman, company_director — Hussain Media 
    "+97333000010", # Omar Al-Sayed, owner — Manara Studios 
    "+97333000011", # Hala Jassim, editor — Manara Studios 
    "+97333000020", # Fatima Al-Kooheji, client_approver — Bank of Salam 
    "+97333000021", # Ali Hasan, client_reviewer — Bank of Salam 
    "+97333000022", # Dana Fakhro, client_owner — Bank of Salam 
    "+97333000030", # Rashid Buali, client_approver — Batelco 
]


def _granted_scopes(person: dict) -> str:
    """Returns the user's granted permission scopes."""
    scopes = person.get("scopes")

    if scopes:
        return ", ".join(scopes)

    # Build scopes from permissions if needed.
    perms = person.get("permissions", {})
    return ", ".join(
        f"{module}:{level}"
        for module, level in perms.items()
        if level != "none"
    )


def _task_count(phone: str) -> int:
    """Returns the number of tasks visible to a user."""
    try:
        return himedia.get("/v1/tasks", phone=phone)["total"]

    except himedia.ApiRefused:
        return 0


def main() -> None:
    rows = []

    # Get identity and task data for each seeded user.
    for phone in PHONES:
        person = identity.who_is(phone)

        if person is None:
            rows.append(
                (phone, "— NOT FOUND —", "", "", "", 0, None)
            )
            continue

        rows.append(
            (
                phone,
                person["user"]["full_name"],
                person["company"]["name"],
                person["role"]["key"],
                person["audience"],
                _task_count(phone),
                person,
            )
        )

    # Calculate column widths for the output table.
    name_w = max(len(r[1]) for r in rows) + 2
    company_w = max(len(r[2]) for r in rows) + 2
    role_w = max(len(r[3]) for r in rows) + 2

    header = (
        f"{'PHONE':<15} {'NAME':<{name_w}} "
        f"{'COMPANY':<{company_w}} "
        f"{'ROLE':<{role_w}} "
        f"{'AUDIENCE':<10} {'TASKS':>5}"
    )

    print(header)
    print("-" * len(header))

    # Print user information.
    for phone, name, company, role, audience, tasks, _ in rows:
        print(
            f"{phone:<15} "
            f"{name:<{name_w}} "
            f"{company:<{company_w}} "
            f"{role:<{role_w}} "
            f"{audience:<10} "
            f"{tasks:>5}"
        )

    found = sum(1 for r in rows if r[6] is not None)

    print(
        f"\n{found} of {len(PHONES)} people "
        "resolved against the live sandbox."
    )

    print("\nGranted scopes, per person:")

    # Print permissions for each user.
    for phone, name, company, role, audience, tasks, person in rows:
        if person is None:
            print(f"  {phone:<15} NOT FOUND")
            continue

        print(
            f"  {name:<20} "
            f"{_granted_scopes(person)}"
        )


if __name__ == "__main__":
    main()
