# HiMedia WhatsApp Agent

**General Assembly × JoinFuture Solutions W.L.L. — Two-Week Capstone**
Students: Sara Alnajjar, Reem AlShehabi, Zainab Mohammed.

## What it does

A production company called Hussain Media makes films for clients such as
Bank of Salam. Their staff and their clients both want quick answers —
*what am I working on today? has the client replied? which version are
they waiting for?* — over WhatsApp, without opening a dashboard. This
backend answers those questions correctly for whoever is asking, changes
data only after they explicitly say yes, and never shows anyone more than
they're allowed to see.

No website here — a Python backend talking to three things: WhatsApp, the
HiMedia sandbox API, and OpenAI.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: HIMEDIA_API_KEY is the shared class key from the handbook;
# add a real OPENAI_API_KEY; WhatsApp values only needed for Phase 4
```

## Phase 1 — Understand the System

**Gate:** one command prints all 13 seeded people's role, permissions,
and task count — real data, from the live API.

```bash
python -m agent.roster
```

**Also covers the API-exploration checklist** (5+ endpoints called
manually, real response shapes inspected, internal vs. client proven to
return different data):

```bash
python -m agent.explore
```

See `PERMISSIONS.md` for the tenant-isolation rules this confirmed.

## Phase 2 — Identity and Permissions

**Gate:** hold a real conversation in a terminal, as three different
people, and each one gets a correctly different answer.

```bash
python -m agent.cli
```

Five read-only tools, filtered per caller's live permissions:

| Tool | Needs |
|---|---|
| `who_am_i` | — |
| `list_tasks` | `tasks:read` |
| `get_task_notes` | `tasks:read` |
| `list_projects` | `projects:read` |
| `list_versions` | `reviews:read` |
| `get_review_notes` | `reviews:read` |

`get_task_notes` reads the comments on one task. It is the only tool that
touches `client_visible` data, so it always passes `client_visible_only` from
the caller's own audience — see `QUESTIONS.md`.

## Phase 3 — Actions and Safety

**Gate:** the agent changes real data only after a human says yes, and
the leak test runs clean as a client account. **This gate carries 30% of
the grade.**

Four write tools, added to the same catalogue:

| Tool | Needs | Audience |
|---|---|---|
| `update_task_status` | `tasks:write` | internal |
| `comment_on_task` | `tasks:write` | internal |
| `comment_on_version` | `reviews:write` | both |
| `decide_version` | `reviews:write` | both |

**Confirm-before-write (`agent/brain.py` + `agent/memory.py`):** when the
model requests a write tool, it is not run. The request is held
(`memory.hold`), a one-line preview goes back to the person, and the
action only actually executes on an explicit yes in the *next* message.
Anything that's neither a clear yes nor no gets a reminder of what's
still pending — never silently dropped, never silently run.

```bash
python -m agent.cli
# sign in as Khalid (+97333000003) and try:
#   "move task tsk_0001 to done"
# then confirm with "yes" — or cancel with "no"
```

**Writes you can't take back need an exact phrase, not a yes.** The rule: a
write needs the typed phrase when it is *irreversible*, or when it *crosses the
line to the client* and can't be un-sent. Anything else — including "yes" and
"تمام" — cancels it and says why.

Which writes those are is decided from the tool **and its arguments**
(`tools.is_destructive`), because the same tool can be either: moving a task to
`in_progress` is ordinary work, moving it to `cancelled` is the closest thing to
deleting something this API offers.

| Action | Needs `تأكيد نهائي`? | Why |
|---|---|---|
| `decide_version` (approve / request changes) | **yes** | decides on the client's behalf, no undo |
| `update_task_status` → `cancelled` | **yes** | nearest thing to destroying work here |
| `update_task_status` → `client_review` | **yes** | the client can see it; can't un-send |
| `comment_on_task` with `client_visible: true` | **yes** | publishes a line to the client |
| `update_task_status` → `todo`/`in_progress`/`in_review`/`done` | no | internal, and reversible |
| `comment_on_task` (internal) | no | cheap to get wrong, cheap to correct |
| `comment_on_version` | no | highest-frequency write; only *adds* information |

The phrase is one constant, `brain.CONFIRM_PHRASE`, used both by the check and
by the message that asks for it. Write tools must declare which side of the
line they fall on; anything unclassified is treated as destructive, and a test
enforces that every write tool has decided.

**Deliberately not gated by role.** Permissions already decide *who may* act
(`identity.allowed`, plus `approval_rank` enforced server-side by HiMedia). The
phrase answers a different question — *did you mean it?* — which applies to
everyone who can do the action, managers included.

**Graceful refusals per role:** a caller whose scope doesn't include a
tool never sees it offered at all (Layer 1). A caller who somehow gets
past that — or whose `approval_rank` is too low for a given review
decision even with `reviews:write` scope — gets a clean refusal from the
real API (`ApiRefused`, Layer 2), which `agent/brain.py` passes straight
to the person in their own language. It never retries a different way
to get around a refusal.

**The leak test** — the adversarial suite the grading explicitly targets:

The suite is split by what it needs, so a missing model key never hides a
test that would have run without one:

```bash
pytest -q                                            # no network, no key
RUN_LIVE_TESTS=1 pytest -q                           # + the live sandbox
RUN_LIVE_TESTS=1 pytest tests/test_leak_live.py -v -s   # + a model key
```

| Layer | File | Needs |
|---|---|---|
| Filtering, against a fake sandbox | `test_leak_regressions.py` | nothing |
| The data layer, against real data | `test_leak_data_live.py` | sandbox |
| Tenant isolation, Ch. 20's numbers | `test_isolation_live.py` | sandbox |
| `client_visible` proof, Ch. 19 | `test_comment_visibility_live.py` | sandbox |
| The seven attack messages, end to end | `test_leak_live.py` | sandbox + model |

The forbidden-word list is no longer hardcoded. `tests/seed_forbidden.py`
derives it from the live `reset-demo` data — every value staff can see minus
everything this client legitimately sees — so it cannot rot into a guess:

```bash
python -m tests.seed_forbidden      # prints the before/after table
```

That subtraction is why "Manara" is *not* forbidden: Bank of Salam is
genuinely a client of Manara Studios (Ch. 7), so banning the word would flag a
correct answer.

**Timing per stage** (`audit.log_stage`) goes to the same log: each model
round, each tool call, `identity.who_is` with cache hit or miss, rounds used
out of `MAX_ROUNDS`, and the total per message, each tagged `ar` or `en`.
`python -m tests.measure_latency` sends five matched Arabic and English
messages and prints the comparison.

**Every tool call is logged** (`agent/audit.py`) to `audit.log` — who
asked, which tool, with what arguments, what came back, how long it
took, whether it was allowed or refused. This is the trace record for
debugging and for the conversation-log submission requirement.

## Phase 4 — WhatsApp and Ship

**Gate:** a real phone messages the agent and gets a correct answer.
Someone outside the team clones the repo, follows this README, and runs
it.

### Connect WhatsApp (Chapter 28)

1. Go to `developers.facebook.com`, log in, **My Apps → Create App**
   (Business type).
2. Find **WhatsApp** on the app dashboard, click **Set up** — lands on
   API Setup. Copy the temporary access token, Phone number ID, and test
   From number into `.env` (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`).
3. Under **To**, add your own number and teammates' numbers as test
   recipients — each confirms via a WhatsApp code.
4. Start the server and a tunnel:
   ```bash
   uvicorn agent.whatsapp:app --reload --port 8000
   ngrok http 8000   # separate terminal
   ```
5. In the dashboard's **WhatsApp → Configuration**, set the Callback URL
   to `https://<your-ngrok-domain>/whatsapp` and the Verify token to
   whatever you put in `WHATSAPP_VERIFY_TOKEN`. Click Verify and save,
   then subscribe to the `messages` field.

**Known gotchas (Chapter 28):** the temporary access token expires after
24 hours — get a fresh one from API Setup, or set up a permanent System
User token once this stops being annoying. The ngrok URL changes on
every free-plan restart — update the Callback URL each time.

### Demo

```bash
python -m agent.demo
```

Scripted, non-interactive walkthrough: the Phase 1 roster, the
internal-vs-client isolation proof, and the same kind of question asked
by three different people with real answers printed. Safe to run live —
each section is wrapped so one failure doesn't take down the rest.

For live audience questions during the actual 7-minute demo, hand off to
`python -m agent.cli` (or a real WhatsApp message) so someone can ask
something unscripted.

## Tests

```bash
pytest -v                        # pure-logic tests, no network needed
RUN_LIVE_TESTS=1 pytest -v -s    # + live tests against the real sandbox/model
```

| File | What it covers | Needs network? |
|---|---|---|
| `test_identity.py` | phone normalization | no |
| `test_tools_filtering.py` | catalogue filtering, all 10 tools, fabricated permission payloads | no |
| `test_confirmation_flow.py` | hold/confirm/cancel logic, stubbed tool (no real write) | no |
| `test_leak_regressions.py` | one test per leak fixed, against a fake sandbox | no |
| `test_exact_phrase_confirmation.py` | the exact-phrase gate on `decide_version` | no |
| `test_device_verification.py` | first-device one-time code (TEMP, Sara's area) | no |
| `test_memory.py`, `test_audit.py`, `test_himedia.py`, `test_whatsapp.py` | history, logging, API wrapper, webhook | no |
| `test_correctness_live.py` | Chapter 30 correctness checklist, real people | **yes** |
| `test_leak_live.py` | adversarial leak suite — 30% of the grade | **yes** |
| `test_comment_visibility_live.py` | settles the `client_visible` question in `QUESTIONS.md` | **yes** |

`test_leak_regressions.py` is the offline half of the leak work: it replaces
the sandbox with a fake that deliberately returns more than the caller should
see, so a missing filter fails the test. It runs on a plain `pytest`, with no
network and no model key — a leak test that needs neither is a leak test that
actually gets run.

This build environment cannot reach the sandbox, so the two live files
have been written correctly against the documented API and model but not
executed here — **run them for real** and save the output for
submission.

## What's not finished

Explicitly out of scope for the two-week capstone, not oversights:

- **A phone number is only as trustworthy as the handset.** Identity is the
  one thing every permission decision keys off: `who_is()` turns a number into
  a person, and everything the agent will say follows from that. But a sender
  ID can be faked, a SIM can be swapped, and a phone gets handed to a colleague
  — so anyone holding Khalid's number inherits Khalid's five tasks.

  **What we built.** A first-device check in `agent/identity.py::device_gate`.
  The order of its two checks is the whole point:

  | Who is asking | What happens |
  |---|---|
  | Number we don't recognise | The flat refusal, and nothing else. No code, no hint that we looked anything up. |
  | Known number, device we've never seen | A six-digit one-time code, then the device is remembered. |
  | Known number, remembered device | Straight through, no friction. |

  A stranger is never sent a code. Telling someone we have issued them one
  confirms both that the system exists and that we are processing them — worse
  security than saying no, and it would fail the "unknown number → polite
  refusal, nothing leaked" case outright. That ordering is pinned by
  `tests/test_device_verification.py`, including end to end through the
  WhatsApp entry point.

  **What is not finished, honestly.** Two things.

  The code is written to the server log, because there is no mail service
  wired up here. A production version sends it to the address already on the
  person's HiMedia record — **out of band, never back down the same WhatsApp
  thread**, since whoever holds the number would simply read it there. That
  single detail is what makes the check worth anything.

  And the record of verified devices lives in a module-level set in
  `identity.py`, in process. **Restarting the server forgets every verified
  device and everyone is challenged again.** That is the same accepted
  limitation as the conversation memory, and acceptable for a two-week
  capstone — but in production it belongs in durable storage, with a way to
  revoke a device centrally when a handset is lost.

- **No persistent memory or durable storage.** `agent/memory.py` is a
  plain dict — restarting the server forgets every conversation and any
  pending confirmation.
- **Confirmation-word matching is a fixed list**
  (`AFFIRMATIVE`/`NEGATIVE` in `agent/brain.py`), not model-interpreted
  intent.

## Project layout

```
agent/
  config.py      # reads .env
  himedia.py     # the only file that knows the sandbox exists
  identity.py    # phone -> person, live permissions, 60s cache
  roster.py      # Phase 1 gate script
  explore.py     # Phase 1 API-exploration script
  audit.py       # Phase 3/4: logs every tool call
  tools.py       # 9-tool catalogue (5 read, 4 write) + filtering + previews
  memory.py      # conversation history + pending-write state
  brain.py       # the agent loop, confirm-before-write flow
  whatsapp.py    # webhook verify/receive/send — thin, no logic of its own
  cli.py         # terminal test harness
  demo.py        # scripted Phase 1+2 walkthrough
tests/
  test_identity.py            # pure logic
  test_tools_filtering.py      # pure logic — all 9 tools
  test_confirmation_flow.py     # pure logic — hold/confirm/cancel
  test_correctness_live.py       # real API + real model
  test_leak_live.py               # real API + real model — the 30% gate
PERMISSIONS.md   # tenant-isolation rules, confirmed live
QUESTIONS.md     # running log for office hours / client check-in
TEAM.md          # ownership + conventions
```

## Submission checklist (Chapter 33)

- [x] Python code, roughly this layout
- [x] `requirements.txt`
- [x] `.env.example`, blank values, real `.env` never committed
- [x] `README.md` — this file
- [ ] Test list + output — run `pytest -v`, save output
- [ ] Leak test + output — run `RUN_LIVE_TESTS=1 pytest tests/test_leak_live.py -v -s`, save output
- [ ] A saved conversation log from a real WhatsApp exchange, showing every tool call (pull from `audit.log`)

Before submitting: `git log -p | grep -i -E "api[_-]?key|sk-|OPENAI|WHATSAPP"`
— should show only variable names/comments, never a real key value.
