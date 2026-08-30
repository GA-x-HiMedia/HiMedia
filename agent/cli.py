"""
Terminal interface for testing the HiMedia agent.

Run with:

    python -m agent.cli
"""

from . import brain, identity, tools


def _make_status_printer():
    # Update the current status on one terminal line.
    last_len = [0]

    def _status(text: str) -> None:
        pad = max(last_len[0] - len(text), 0)
        print(f"\r{text}{' ' * pad}", end="", flush=True)
        last_len[0] = len(text)

    return _status


def _looks_like_a_phone(text: str) -> bool:
    """Checks whether the input looks like a phone number."""
    stripped = text.replace("whatsapp:", "")
    digits = [ch for ch in stripped if ch.isdigit()]
    return len(digits) >= 6 and all(
        ch.isdigit() or ch in "+-() ." for ch in stripped.strip()
    )


def _announce(person: dict) -> None:
    """Displays the current user's identity."""
    print(
        f"Signed in as {person['user']['full_name']} "
        f"— {person['role']['key']} @ {person['company']['name']} "
        f"({person['audience']})"
    )
    counts = person.get("counts", {})
    if counts:
        print("Pending:", ", ".join(f"{v} {k}" for k, v in counts.items()))


def _describe_access(person: dict) -> None:
    """Displays the user's permissions and available tools."""
    granted = sorted(
        f"{m}:{lvl}" for m, lvl in person.get("permissions", {}).items()
    )
    offered = [t["function"]["name"] for t in tools.tools_for(person)]
    print(f"  permissions : {', '.join(granted) or 'none'}")
    print(f"  approval    : rank {person['role'].get('approval_rank')}")
    print(
        f"  tools ({len(offered)}/{len(tools.ALL_TOOLS)}) : "
        f"{', '.join(offered)}"
    )


def main() -> None:
    raw = input("Pretend to be which number? ").strip()
    person = identity.who_is(raw)

    if person is None:
        print(f"No HiMedia identity for {raw}.")
        return

    phone = identity.tidy(raw)
    _announce(person)

    print(
        "(type a different number to switch person, `who` for access, "
        "'quit' to exit)\n"
    )

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
            reply = brain.reply_to(
                person, message, phone, on_status=status
            )

        except RuntimeError as no_key:
            # Show a clear message when the model key is missing.
            print("\r" + " " * 40 + "\r" + f"[no model key] {no_key}")
            print("  `who` still works, and so does switching person.\n")
            continue

        # Clear the status line before showing the reply.
        print("\r" + " " * 40 + "\r" + reply)


if __name__ == "__main__":
    main()