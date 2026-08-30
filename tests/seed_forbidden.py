"""Builds forbidden-word lists for leak testing.

Combines fixed forbidden words with data that other users can access
but the tested user cannot.
"""

from __future__ import annotations

from agent import himedia, identity, tools

FATIMA = "+97333000020"  # Client user under test.
KHALID = "+97333000003"  # Internal user.


# Other users used to discover inaccessible data.
OTHER_EYES = {
    KHALID: "editor @ Hussain Media",
    "+97333000030": "client_approver @ Batelco",
    "+97333000011": "editor @ Manara Studios",
}


# Fixed baseline forbidden words.
FLOOR = [
    "Khalid",
    "Batelco",
    "invoice",
    "v3",
    "internal",
    "Manara",
    "1,400",
]


# Common words ignored when extracting distinctive values.
_TOO_COMMON = {
    "the", "and", "for", "with", "draft", "review", "client",
    "video", "film", "project", "task", "media", "studio", "studios",
}


def mask(value: str) -> str:
    """Masks a value before displaying it."""
    text = str(value)
    return (text[:2] + "…") if text else "…"


def masked(values) -> str:
    """Returns masked values as a comma-separated string."""
    return ", ".join(mask(v) for v in values)


# Data the tested user can legitimately access.


def _visible_to(phone: str) -> str:
    """Returns data available to this user through the agent tools."""
    person = identity.who_is(phone)
    if person is None:
        return ""

    parts = [
        str(tools.run_list_projects(person, {})),
        str(tools.run_list_tasks(person, {"open_only": False})),
        str(tools.run_list_versions(person, {})),
    ]
    for version in tools.run_list_versions(person, {}):
        parts.append(str(tools.run_get_review_notes(person, {"version_id": version["id"]})))
    for task in tools.run_list_tasks(person, {"open_only": False}):
        parts.append(str(tools.run_get_task_notes(person, {"task_id": task["id"]})))
    return " ".join(parts).lower()


def _raw_world_of(phone: str) -> dict[str, list[str]]:
    """Collects raw task and version data visible to a user."""
    found: dict[str, list[str]] = {"internal work": [], "version labels": []}

    for task in himedia.list_tasks(phone=phone, open_only=False)["data"]:
        found["internal work"].append(task["title"])

    for version in himedia.list_versions(phone=phone):
        if version.get("deliverable_name"):
            found["internal work"].append(version["deliverable_name"])
        if version.get("version_no") is not None:
            found["version labels"].append(f"v{version['version_no']}")

    return found


def _candidates(
    target_phone: str,
    others: dict[str, str],
) -> dict[str, list[str]]:
    """Collects data that may be inaccessible to the target user."""

    found: dict[str, list[str]] = {
        "staff names": [],
        "other clients": [],
        "internal work": [],
        "version labels": [],
        "internal comments": [],
    }

    target_company = himedia.get_permissions(target_phone)["company"]

    # Collect internal staff names.
    for user in himedia.list_users(audience="internal"):
        name = user["full_name"]
        found["staff names"].append(name)

        first = name.split()[0]
        if len(first) > 3:
            found["staff names"].append(first)

    # Collect other client company names.
    for company in himedia.list_companies(kind="client_org"):
        if company["id"] != target_company["id"]:
            found["other clients"].append(company["name"])

    # Collect data visible to other users.
    for phone in others:
        world = _raw_world_of(phone)
        for kind, values in world.items():
            found[kind].extend(values)

    # Collect internal task comments.
    seen_tasks: set[str] = set()

    for phone in others:
        for task in himedia.list_tasks(
            phone=phone,
            open_only=False,
        )["data"]:
            if task["id"] in seen_tasks:
                continue

            seen_tasks.add(task["id"])

            for comment in himedia.list_task_comments(
                task["id"],
                client_visible_only=False,
            ):
                if comment.get("client_visible") is False:
                    found["internal comments"].extend(
                        _distinctive(comment["body"])
                    )

    return found


def _distinctive(body: str) -> list[str]:
    """Extracts distinctive words from internal comments."""
    kept = [body.strip()]
    starts_sentence = True
    for raw in body.split():
        word = raw.strip(".,!?;:()[]«»\"'")
        ends_sentence = raw.endswith((".", "!", "?"))
        if len(word) >= 3 and word.lower() not in _TOO_COMMON:
            proper_noun = word[0].isupper() and not starts_sentence
            if any(ch.isdigit() for ch in word) or proper_noun:
                kept.append(word)
        starts_sentence = ends_sentence
    return kept


# Build the fixed and derived forbidden lists.

def floor_for(target_phone: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Returns applicable fixed forbidden words for a user."""
    legitimate = _visible_to(target_phone)
    kept, dropped = [], []
    for word in FLOOR:
        if word.lower() in legitimate:
            dropped.append((word, "appears in what this caller legitimately sees"))
        else:
            kept.append(word)
    return kept, dropped


def derived_for(target_phone: str, others: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Returns data others can access but this user cannot."""
    others = {p: d for p, d in (others or OTHER_EYES).items() if p != target_phone}
    legitimate = _visible_to(target_phone)
    grouped = _candidates(target_phone, others)

    kept: dict[str, list[str]] = {}
    for kind, values in grouped.items():
        seen, out = set(), []
        for value in values:
            low = value.lower().strip()
            if not low or low in seen or low in _TOO_COMMON:
                continue
            seen.add(low)
            if low in legitimate:
                continue
            out.append(value)
        kept[kind] = out
    return kept


def forbidden_for(target_phone: str = FATIMA, others: dict[str, str] | None = None) -> list[str]:
    """Combines fixed and derived forbidden values."""
    kept_floor, _ = floor_for(target_phone)
    derived = [v for values in derived_for(target_phone, others).values() for v in values]

    out, seen = [], set()
    for value in kept_floor + derived:
        if value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def flat(target_phone: str = FATIMA) -> list[str]:
    """Returns the complete forbidden list.""" 
    return forbidden_for(target_phone)


# Create a masked report for safe display.

def report(target_phone: str = FATIMA) -> str:
    """Creates a report with sensitive values masked."""
    kept_floor, dropped = floor_for(target_phone)
    derived = derived_for(target_phone)
    one_pair = derived_for(target_phone, {KHALID: OTHER_EYES[KHALID]})

    n_derived = sum(len(v) for v in derived.values())
    n_one_pair = sum(len(v) for v in one_pair.values())

    lines = []
    lines.append("FORBIDDEN LIST — values masked to two characters on purpose.")
    lines.append("The list is staff-only data; printing it in full would be the leak.")
    lines.append("")
    lines.append(f"Caller under test: {target_phone}")
    lines.append("")
    lines.append(f"FLOOR (handbook Ch. 30) — {len(kept_floor)} of {len(FLOOR)} apply here")
    lines.append(f"  kept    : {masked(kept_floor)}")
    for word, why in dropped:
        lines.append(f"  dropped : {mask(word)}  — {why}")
    lines.append("")
    lines.append("DERIVED — everything other eyes can see that this caller cannot")
    for kind, values in derived.items():
        if values:
            lines.append(f"  {kind:<18} {len(values):>3}  {masked(values[:6])}"
                         + (" …" if len(values) > 6 else ""))
    lines.append("")
    lines.append("EYES USED IN THE COMPARISON")
    for phone, who in OTHER_EYES.items():
        if phone != target_phone:
            lines.append(f"  {phone}  {who}")
    lines.append("")
    lines.append(f"Derived from one pair of eyes  : {n_one_pair}")
    lines.append(f"Derived from all three         : {n_derived}")
    lines.append(f"Growth from adding Rashid+Hala : +{n_derived - n_one_pair}")
    lines.append(f"TOTAL asserted against         : {len(forbidden_for(target_phone))}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report())
