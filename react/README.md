# The chat interface

A React front end for the agent in `agent/`. It is a second face on the same
thing WhatsApp talks to — not a second agent. Every answer, every refusal and
every held write comes from `brain.reply_to`, reached over HTTP.

```
browser  ->  react (vite, :5173)
                 |  /api/... proxied
                 v
             agent/web.py (uvicorn, :8000)
                 |  identity.device_gate  ->  brain.reply_to
                 v
             the same agent the WhatsApp webhook calls
```

## Running it

Two processes. **The API first**, from the repository root:

```bash
uvicorn agent.web:app --reload --port 8000
```

Then the interface, from this folder:

```bash
npm install
npm run dev
```

Open <http://localhost:5173>.

There is no sign-in screen — it opens straight into a conversation. The agent
still needs a number, because a number is the only thing that decides what
anyone can see, so it starts as Khalid Mansoor (editor) and the rail on the
left switches to anyone else. To open as somebody else:

```bash
VITE_DEFAULT_PHONE=+97333000020 npm run dev   # Fatima, client approver
```

`npm install` needs Node 18 or newer. Nothing else is installed — the only
dependencies are React and Vite.

If the API is on a different port:

```bash
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev
```

## What is on the screen

**Left — who is asking.** All thirteen seeded people, grouped by company.
Clicking one switches to them. Switching mid-demo is the fastest way to show
what the project is for: ask the same question as Khalid and then as Fatima,
and read the two answers next to each other.

**Middle — the conversation.** While the agent works, the line under the
transcript shows what it is doing: *Thinking…*, then *Calling `list_tasks`…*.
Those are not invented for the UI — they come from `brain.reply_to`'s own
`on_status` callback, the same strings `agent/cli.py` prints. The API forwards
each one as a server-sent event as it happens.

**Right — access and audit.** The tool list is `tools_for(person)`, the same
filtered list the model is handed on every message; struck-through rows were
removed *before* the model was called, which is why it cannot claim a power it
does not have. The audit tab reads the tail of `audit.log`.

## The two gates, on screen

**Device verification.** A number the API recognises, on a device it has not
seen, is challenged before anything else happens. The six-digit code is
printed by the API process — look in the terminal running uvicorn. It is
delivered out of band on purpose: a code sent down the same channel proves
nothing, because whoever holds the number would simply read it. The composer
turns into a six-digit field while this is outstanding. *Reset device* in the
right-hand panel makes a number verify again, so the challenge can be
demonstrated twice in one run.

An unknown number is refused flatly and never gets a code — telling a stranger
that a code has been sent confirms the system exists and is processing them.

**Confirm before write.** When the model asks for a write, the write does not
run. It is described, held in `memory.py`, and the description comes back as
the reply. The banner above the composer shows what is waiting, in two shapes:

| | |
|---|---|
| ordinary write | Yes / أي / No |
| point of no return | the exact phrase `تأكيد نهائي`, typed |

Every button sends an ordinary message down the ordinary path. There is no
"confirmed" flag anywhere in the API — `brain.py` reads the word in code, and
re-checks permissions at the moment the write actually runs, not at the moment
it was parked.

One deliberate softening, worth knowing about before the demo: the final-write
banner offers a **copy** button for the phrase. Typing Arabic on a keyboard
that has no Arabic layout is a real barrier, and the demo has to be runnable.
The gate still does its job — the phrase has to be in the box, the box has to
match exactly, and the button stays disabled until it does — but a copy button
is a smaller obstacle than typing it out. If that trade is wrong for your
demo, delete the `<button onClick={copy}>` in
`src/components/PendingBanner.jsx`; nothing else depends on it.

## Colours

`src/styles/theme.css` holds the brand palette and nothing else uses a colour
literal. The status colours carry the same meaning they carry in the deck, and
the interface uses them that way rather than decoratively:

| | |
|---|---|
| orange `#FF5A2B` | the person's own messages, active state, anything that writes |
| green `#259563` | a write that went through, a tool that is allowed |
| red `#BE3F46` | a refusal, and a point of no return |
| peach `#F7E8E0` | something to read before acting — the device challenge, a held write |

## Files

```
react/
├── index.html
├── package.json
├── vite.config.js          proxies /api to the Python process
└── src/
    ├── main.jsx
    ├── App.jsx             all the state; one turn from end to end
    ├── api.js              fetch + the SSE reader for the status line
    ├── format.jsx          direction, initials, and a small Markdown renderer
    ├── styles/
    │   ├── theme.css       the brand palette — the only place colours live
    │   └── app.css
    └── components/
        ├── Rail.jsx        switch person mid-conversation
        ├── Message.jsx     one bubble
        ├── StatusLine.jsx  Thinking… / Calling list_tasks…
        ├── PendingBanner.jsx   the held write, and the phrase gate
        ├── Composer.jsx    the message box, and the six-digit code box
        ├── ToolPanel.jsx   tools_for(), and the live permission map
        ├── AuditPanel.jsx  the tail of audit.log
        ├── PersonButton.jsx
        └── Logo.jsx
```

The model replies in Markdown, so `format.jsx` renders `**bold**`, `` `code` ``
and lists — as React elements, never as raw HTML, so a tool result that
happens to contain markup stays text.

## What this front end does not do

- **There is no password on the API.** It binds to localhost and is a
  development tool. Anyone who can reach it can be any of the thirteen people,
  which is exactly what makes it useful for a demo and exactly why it must not
  be exposed to a network without a door on it first.
- **State lives in the Python process.** History and held writes are in
  `memory.py`, so restarting the API forgets every conversation and every
  device verification. That is the documented limitation of the agent, not a
  new one — but note it would also need solving before this could be deployed
  somewhere serverless, where the process does not survive between requests.
- **Reloading the page is safe.** The transcript is restored from the server's
  own history when the page comes back, so a refresh mid-demo does not lose the
  conversation.
