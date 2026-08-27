"""
Terminal test harness. Run with:

    python -m agent.cli

Drives brain.reply_to directly — no WhatsApp, no webhook, no tunnel.

Type a phone number at any time to become that person (handbook Ch. 14 —
"watching the answer change is the moment the whole project clicks"). Type
`who` to see the current identity, permissions and the tools they are offered,
which works with no model key at all.

Status indicator: while waiting for a reply, this prints "Thinking…" /
"Calling <tool_name>…" on a single line that overwrites itself in place
(via \\r), instead of scrolling the terminal. The line is cleared right
before the final reply is printed.
"""
from . import brain, identity, tools


def _make_status_printer():
    """Returns a callback that overwrites one terminal line per status
    update, padding with spaces to erase any leftover characters from a
    longer previous message (e.g. "Calling update_task_status…" -> "Thinking…")."""
    last_len = [0]

    def _status(text: str) -> None:
        pad = max(last_len[0] - len(text), 0)
        print(f"\r{text}{' ' * pad}", end="", flush=True)
        last_len[0] = len(text)

    return _status


# edited by reem — type a number to switch person, `who` to see access.
def _looks_like_a_phone(text: str) -> bool:
    """A message made only of digits and phone punctuation is a request to
    switch person, not a question. Real questions always contain letters."""
    stripped = text.replace("whatsapp:", "")
    digits = [ch for ch in stripped if ch.isdigit()]
    return len(digits) >= 6 and all(
        ch.isdigit() or ch in "+-() ." for ch in stripped.strip())


def _announce(person: dict) -> None:
    print(
        f"Signed in as {person['user']['full_name']} "
        f"— {person['role']['key']} @ {person['company']['name']} "
        f"({person['audience']})"
    )
    counts = person.get("counts", {})
    if counts:
        print("Pending:", ", ".join(f"{v} {k}" for k, v in counts.items()))


def _describe_access(person: dict) -> None:
    """Identity, permissions and the offered tool list. Needs no model key, so
    this is the useful half of the CLI while a key is still being sorted out."""
    granted = sorted(f"{m}:{lvl}" for m, lvl in person.get("permissions", {}).items())
    offered = [t["function"]["name"] for t in tools.tools_for(person)]
    print(f"  permissions : {', '.join(granted) or 'none'}")
    print(f"  approval    : rank {person['role'].get('approval_rank')}")
    print(f"  tools ({len(offered)}/{len(tools.ALL_TOOLS)}) : {', '.join(offered)}")


def main() -> None:
    raw = input("Pretend to be which number? ").strip()
    person = identity.who_is(raw)
    if person is None:
        print(f"No HiMedia identity for {raw}.")
        return

    phone = identity.tidy(raw)
    _announce(person)
    print("(type a different number to switch person, `who` for access, "
          "'quit' to exit)\n")

    while True:
        message = input("> ").strip()
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue

        if _looks_like_a_phone(message):
            switched = identity.who_is(message)
            if switched is None:
                print(f"No HiMedia identity for {message}.\n")
                continue
            person, phone = switched, identity.tidy(message)
            _announce(person)
            print()
            continue

        if message.lower() in {"who", "whoami", "access"}:
            _announce(person)
            _describe_access(person)
            print()
            continue

        status = _make_status_printer()
        try:
            reply = brain.reply_to(person, message, phone, on_status=status)
        except RuntimeError as no_key:
            # No model key yet. Say so plainly instead of a stack trace — the
            # identity and permission half of the CLI still works.
            print("\r" + " " * 40 + "\r" + f"[no model key] {no_key}")
            print("  `who` still works, and so does switching person.\n")
            continue
        print("\r" + " " * 40 + "\r" + reply)  # clear the status line, then show the answer


if __name__ == "__main__":
    main()