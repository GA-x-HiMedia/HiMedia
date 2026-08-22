"""
Terminal test harness (Chapter 29). Run with:

    python -m agent.cli

Drives brain.reply_to directly — no WhatsApp, no webhook, no tunnel. This
is where most development should happen through Day 7; only Day 8 wires up
WhatsApp (Chapter 31 — "teams that wire up WhatsApp on day one spend three
days debugging tunnels instead of building an agent").
"""
from . import brain, identity


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
        print(brain.reply_to(person, message, phone))


if __name__ == "__main__":
    main()
