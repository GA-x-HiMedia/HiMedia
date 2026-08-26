"""
Terminal test harness. Run with:

    python -m agent.cli

Drives brain.reply_to directly — no WhatsApp, no webhook, no tunnel.

Status indicator: while waiting for a reply, this prints "Thinking…" /
"Calling <tool_name>…" on a single line that overwrites itself in place
(via \\r), instead of scrolling the terminal. The line is cleared right
before the final reply is printed.
"""
from . import brain, identity


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


def main() -> None:
    raw = input("Pretend to be which number? ").strip()
    person = identity.who_is(raw)
    if person is None:
        print(f"No HiMedia identity for {raw}.")
        return

    phone = identity.tidy(raw)
    print(
        f"Signed in as {person['user']['full_name']} "
        f"— {person['role']['key']} @ {person['company']['name']} "
        f"({person['audience']})"
    )
    counts = person.get("counts", {})
    if counts:
        print("Pending:", ", ".join(f"{v} {k}" for k, v in counts.items()))
    print("(type 'quit' to exit)\n")

    while True:
        message = input("> ").strip()
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue

        status = _make_status_printer()
        reply = brain.reply_to(person, message, phone, on_status=status)
        print("\r" + " " * 40 + "\r" + reply)  # clear the status line, then show the answer


if __name__ == "__main__":
    main()