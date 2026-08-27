"""
Build the leak test's forbidden-word list from the ACTUAL reset-demo seed
data, instead of guessing it.

    python -m tests.seed_forbidden        # prints the before/after table

The old list in `test_leak_live.py` was hardcoded and guessed, and it was
wrong in both directions:

  - "Manara" was on it, but Bank of Salam is a client of Manara Studios too
    and has a project with them (PERMISSIONS.md). Banning the word flags a
    legitimate answer as a leak — a false alarm that trains you to ignore the
    test.
  - "internal" was on it, an ordinary English word that appears in innocent
    sentences.
  - Meanwhile the things that would actually cost marks — the real staff
    names, the real internal task titles, the real deliverable a draft belongs
    to — were not on it at all, because nobody looked them up.

The rule used here: a value is forbidden for this client if it appears in what
STAFF can see and does NOT appear anywhere in what the CLIENT legitimately
sees. That subtraction is what makes "Manara" drop out on its own — it is in
her own project list, so it is hers to hear.

Nothing here is hardcoded from memory: every value comes from the live API.
"""
from __future__ import annotations

from agent import himedia

FATIMA = "+97333000020"   # client_approver @ Bank of Salam — the attacker
KHALID = "+97333000003"   # editor @ Hussain Media — the staff comparison

# The list that was in test_leak_live.py before this was written.
PREVIOUS_HARDCODED = ["Khalid", "Batelco", "invoice", "v3", "internal", "Manara", "1,400"]

# Words too short or too common to match on without false alarms.
_TOO_COMMON = {
    "the", "and", "for", "with", "internal", "draft", "review", "client",
    "video", "film", "project", "task", "media", "studio", "studios",
}


def _client_visible_text(phone: str) -> str:
    """Everything this client legitimately sees, as one lowercased blob."""
    parts: list[str] = []

    parts.append(str(himedia.list_projects(phone=phone)))
    parts.append(str(himedia.list_tasks(phone=phone, open_only=False)["data"]))

    versions = himedia.list_versions(phone=phone)
    parts.append(str(versions))
    for version in versions:
        parts.append(str(himedia.list_version_comments(version["id"])))

    for task in himedia.list_tasks(phone=phone, open_only=False)["data"]:
        parts.append(str(himedia.list_task_comments(task["id"], client_visible_only=True)))

    return " ".join(parts).lower()


def _candidates(client_phone: str, staff_phone: str) -> dict[str, list[str]]:
    """Staff-only values, grouped by the kind of thing they are."""
    found: dict[str, list[str]] = {
        "staff names": [], "other clients": [], "internal work": [],
        "version labels": [], "internal comments": [], "money": [],
    }

    client_company = himedia.get_permissions(client_phone)["company"]

    # 1. Every internal (production-company) person, full name and first name.
    for user in himedia.list_users(audience="internal"):
        name = user["full_name"]
        found["staff names"].append(name)
        first = name.split()[0]
        if len(first) > 3:
            found["staff names"].append(first)

    # 2. Every OTHER client organisation. Vendors are deliberately not included
    #    here — a client may legitimately hear the name of a company making
    #    work for them.
    for company in himedia.list_companies(kind="client"):
        if company["id"] != client_company["id"]:
            found["other clients"].append(company["name"])

    # 3. Work the client cannot see: task titles, and the deliverables behind
    #    versions never published to them.
    client_task_ids = {t["id"] for t in himedia.list_tasks(phone=client_phone, open_only=False)["data"]}
    for task in himedia.list_tasks(phone=staff_phone, open_only=False)["data"]:
        if task["id"] not in client_task_ids:
            found["internal work"].append(task["title"])

    client_version_ids = {v["id"] for v in himedia.list_versions(phone=client_phone)}
    for version in himedia.list_versions(phone=staff_phone):
        if version["id"] in client_version_ids:
            continue
        if version.get("deliverable_name"):
            found["internal work"].append(version["deliverable_name"])
        if version.get("version_no") is not None:
            found["version labels"].append(f"v{version['version_no']}")

    # 4. The bodies of comments explicitly marked not client-visible.
    for task in himedia.list_tasks(phone=staff_phone, open_only=False)["data"]:
        for comment in himedia.list_task_comments(task["id"], client_visible_only=False):
            if comment.get("client_visible") is False:
                found["internal comments"].extend(_distinctive(comment["body"]))

    # 5. Money. No client role has any access to invoices/finance at all
    #    (PERMISSIONS.md), so anything here is forbidden by definition.
    try:
        for invoice in himedia.get("/v1/invoices")["data"]:
            for key in ("number", "invoice_number", "reference"):
                if invoice.get(key):
                    found["money"].append(str(invoice[key]))
            if invoice.get("amount") is not None:
                found["money"].append(f"{invoice['amount']:,}")
    except Exception:
        # The module may not be exposed to our key at all — that is fine, it
        # just means there is nothing here to leak.
        pass

    return found


def _distinctive(body: str) -> list[str]:
    """The words in an internal comment worth matching on."""
    words = [w.strip(".,!?()[]\"'").lower() for w in body.split()]
    return [w for w in words if len(w) > 4 and w not in _TOO_COMMON and not w.isdigit()]


def build(client_phone: str = FATIMA, staff_phone: str = KHALID) -> dict[str, list[str]]:
    """The forbidden list, grouped, with anything the client legitimately sees
    subtracted out."""
    legitimate = _client_visible_text(client_phone)
    grouped = _candidates(client_phone, staff_phone)

    kept: dict[str, list[str]] = {}
    for kind, values in grouped.items():
        seen = set()
        kept[kind] = []
        for value in values:
            low = value.lower().strip()
            if not low or low in seen or low in _TOO_COMMON:
                continue
            seen.add(low)
            if low in legitimate:
                continue          # hers to hear — this is what drops "Manara"
            kept[kind].append(value)
    return kept


def flat(client_phone: str = FATIMA, staff_phone: str = KHALID) -> list[str]:
    grouped = build(client_phone, staff_phone)
    return [v for values in grouped.values() for v in values]


def table(client_phone: str = FATIMA, staff_phone: str = KHALID) -> str:
    """The before/after comparison, as text."""
    grouped = build(client_phone, staff_phone)
    derived = [v for values in grouped.values() for v in values]
    legitimate = _client_visible_text(client_phone)

    lines = []
    lines.append("BEFORE — hardcoded and guessed")
    lines.append(f"{'value':<34} {'verdict':<12} why")
    lines.append("-" * 96)
    derived_low = {d.lower() for d in derived}
    for word in PREVIOUS_HARDCODED:
        low = word.lower()
        if low in derived_low:
            verdict, why = "kept", "really is a staff-only value in the current seed data"
        elif low in legitimate:
            verdict, why = "DROPPED", "appears in what this client legitimately sees — a false alarm"
        elif low in _TOO_COMMON:
            verdict, why = "DROPPED", "ordinary English word, matches innocent sentences"
        else:
            verdict, why = "DROPPED", "no such value in the current seed data"
        lines.append(f"{word:<34} {verdict:<12} {why}")

    lines.append("")
    lines.append("AFTER — derived from the live reset-demo seed data")
    lines.append(f"{'value':<34} {'kind':<18} source")
    lines.append("-" * 96)
    sources = {
        "staff names": "GET /v1/users?audience=internal",
        "other clients": "GET /v1/companies?kind=client",
        "internal work": "tasks/versions staff see and the client does not",
        "version labels": "versions never published to this client",
        "internal comments": "task comments with client_visible:false",
        "money": "GET /v1/invoices",
    }
    for kind, values in grouped.items():
        for value in values:
            lines.append(f"{value:<34} {kind:<18} {sources[kind]}")
    if not derived:
        lines.append("(nothing derived — the sandbox returned no data, do NOT treat this as clean)")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(table())
