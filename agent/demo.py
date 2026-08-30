"""Runs a combined demonstration of the HiMedia agent.

Run with:

    python -m agent.demo
"""

from __future__ import annotations

from . import brain, himedia, identity, roster

SEPARATOR = "=" * 70


def _section(title: str) -> None:
    print("\n" + SEPARATOR)
    print(title)
    print(SEPARATOR)


def phase1_roster() -> None:
    _section("PHASE 1 — Roster: all 13 seeded people, live from the API")
    roster.main()


def phase1_isolation_proof() -> None:
    _section("PHASE 1 — Proof: internal vs. client callers get different data")

    khalid = "+97333000003"  # Internal editor.
    fatima = "+97333000020"  # Client approver.

    khalid_projects = himedia.get("/v1/projects", phone=khalid)["data"]
    fatima_projects = himedia.get("/v1/projects", phone=fatima)["data"]

    print(f"\nKhalid (internal, Hussain Media) sees {len(khalid_projects)} project(s):")
    for p in khalid_projects:
        print(f"  - {p['name']}")

    print(f"\nFatima (client, Bank of Salam) sees {len(fatima_projects)} project(s):")
    for p in fatima_projects:
        print(f"  - {p['name']}")

    khalid_ids = {p["id"] for p in khalid_projects}
    fatima_ids = {p["id"] for p in fatima_projects}

    if khalid_ids != fatima_ids:
        print("\n✓ CONFIRMED: same endpoint, different callers, different data.")
    else:
        print("\n✗ WARNING: identical results — investigate before relying on this live.")


def phase2_same_question_different_people() -> None:
    _section("PHASE 2 — Same kind of question, asked by three different people")

    people = [
        ("+97333000003", "شنو التاسكات اللي عندي؟"),  # Khalid
        ("+97333000006", "what's the status of our projects?"),  # Yusuf
        ("+97333000020", "what's the status of the campaign?"),  # Fatima
    ]

    for phone, question in people:
        person = identity.who_is(phone)

        if person is None:
            print(f"\n[{phone}] NOT FOUND — skipping")
            continue

        print(
            f"\n--- {person['user']['full_name']} "
            f"({person['role']['key']}, {person['audience']}) ---"
        )
        print(f"Q: {question}")

        try:
            answer = brain.reply_to(person, question, identity.tidy(phone))
        except Exception as e:  # Continue if one request fails.
            print(f"A: [error calling the agent: {e}]")
            continue

        print(f"A: {answer}")


def main() -> None:
    for section in (
        phase1_roster,
        phase1_isolation_proof,
        phase2_same_question_different_people,
    ):
        try:
            section()
        except Exception as e:
            print(f"\n[section failed, continuing: {e}]")

    _section("Demo complete.")

    print(
        "For live audience questions, hand off to `python -m agent.cli` and "
        "let someone pick a number from the README table themselves."
    )


if __name__ == "__main__":
    main()