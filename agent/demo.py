"""
Combined demo for Phase 1 + Phase 2. Nothing new is built here — this
just runs the existing pieces in a clean order and prints a readable
transcript, so nothing has to be typed live in front of an audience.

Run with:

    python -m agent.demo

Needs a real OPENAI_API_KEY (Phase 2's section talks to the model) and
network access to the sandbox (both sections do). Each section is
wrapped so one failure doesn't take down the rest of the demo.
"""
from __future__ import annotations

from . import brain, himedia, identity, roster

SEPARATOR = "=" * 70


def _section(title: str) -> None:
    print("\n" + SEPARATOR)
    print(title)
    print(SEPARATOR)


def phase1_roster() -> None:
    _section("PHASE 1 \u2014 Roster: all 13 seeded people, live from the API")
    roster.main()


def phase1_isolation_proof() -> None:
    _section("PHASE 1 \u2014 Proof: internal vs. client callers get different data")

    khalid = "+97333000003"   # editor @ Hussain Media
    fatima = "+97333000020"   # client_approver @ Bank of Salam

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
        print("\n\u2713 CONFIRMED: same endpoint, different callers, different data.")
    else:
        print("\n\u2717 WARNING: identical results \u2014 investigate before relying on this live.")


def phase2_same_question_different_people() -> None:
    _section("PHASE 2 \u2014 Same kind of question, asked by three different people")

    people = [
        ("+97333000003", "\u0634\u0646\u0648 \u0627\u0644\u062a\u0627\u0633\u0643\u0627\u062a \u0627\u0644\u0644\u064a \u0639\u0646\u062f\u064a\u061f"),  # Khalid, editor
        ("+97333000006", "what's the status of our projects?"),                       # Yusuf, accountant
        ("+97333000020", "what's the status of the campaign?"),                       # Fatima, client_approver
    ]

    for phone, question in people:
        person = identity.who_is(phone)
        if person is None:
            print(f"\n[{phone}] NOT FOUND \u2014 skipping")
            continue

        print(f"\n--- {person['user']['full_name']} "
              f"({person['role']['key']}, {person['audience']}) ---")
        print(f"Q: {question}")
        try:
            answer = brain.reply_to(person, question, identity.tidy(phone))
        except Exception as e:  # keep the demo alive even if one call errors
            print(f"A: [error calling the agent: {e}]")
            continue
        print(f"A: {answer}")


def main() -> None:
    for section in (phase1_roster, phase1_isolation_proof, phase2_same_question_different_people):
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
