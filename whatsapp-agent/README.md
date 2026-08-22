# HiMedia WhatsApp Agent — Phase 1 + Phase 2

**General Assembly × JoinFuture Solutions W.L.L. — Two-Week Capstone**

This bundle contains only what Phases 1 and 2 need. No write tools, no
WhatsApp integration — those are Phase 3 and Phase 4. Adding them before
these two gates are green would be building ahead of the plan the
handbook itself warns against (Chapter 31).

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: paste in HIMEDIA_API_KEY (the shared class key from the
# handbook) and, once you reach Phase 2, a real OPENAI_API_KEY
```

## Phase 1 — Understand the System (Days 1–2)

**Gate:** one command prints a table of all 13 seeded people with their
role, permissions, and task count — real data, from the live API.

```bash
python -m agent.roster
```

**Also closes the "explore the API" checklist items** (5+ endpoints
called manually, real response shapes inspected, internal vs. client
proven to return different data):

```bash
python -m agent.explore
```

See `PERMISSIONS.md` for the tenant-isolation rules this confirmed, and
`QUESTIONS.md` for anything still open to raise with JoinFuture.

## Phase 2 — Identity and Permissions (Days 3–5)

**Gate:** hold a real conversation in a terminal, as three different
people, and each one gets a correctly different answer. No WhatsApp yet.

```bash
python -m agent.cli
```

Try the same question as different people and compare:

| Phone | Person | Role | Audience |
|---|---|---|---|
| `+97333000003` | Khalid Mansoor | editor | internal |
| `+97333000002` | Sara Al-Ansari | supervisor | internal |
| `+97333000006` | Yusuf Rashed | accountant | internal |
| `+97333000020` | Fatima Al-Kooheji | client_approver | client |
| `+97333000021` | Ali Hasan | client_reviewer | client |

Ask each one something like "what are my tasks?" / "شنو التاسكات اللي
عندي؟" and confirm the answers genuinely differ.

## What's in the Phase 2 tool catalogue

Five read-only tools — nothing that changes data yet:

| Tool | Needs | Audience |
|---|---|---|
| `who_am_i` | — | both |
| `list_tasks` | `tasks:read` | both |
| `list_projects` | `projects:read` | both |
| `list_versions` | `reviews:read` | both |
| `get_review_notes` | `reviews:read` | both |

`agent/tools.py::tools_for(person)` filters this list per caller, live,
based on their actual permissions from the API — never a hardcoded
table. `agent/brain.py` runs the model/tool loop; since nothing here
writes anything, there's no confirmation step yet either. Both arrive in
Phase 3 alongside the write tools.

## Tests

```bash
pytest -v                        # 14 pure-logic tests, no network needed
RUN_LIVE_TESTS=1 pytest -v -s    # + live tests against the real sandbox/model
```

`test_correctness_live.py` needs a real `OPENAI_API_KEY` and network
access to the sandbox — this build environment couldn't reach either, so
run it yourself before calling Phase 2 done.

## Project layout

```
agent/
  config.py     # reads .env
  himedia.py    # the only file that knows the sandbox exists
  identity.py   # phone -> person, live permissions, 60s cache
  roster.py     # Phase 1 gate script
  explore.py    # Phase 1 API-exploration script
  tools.py      # Phase 2: 5 read-only tools + filtering
  brain.py      # Phase 2: the agent loop (no write-confirmation yet)
  memory.py     # conversation history only, for now
  cli.py        # terminal test harness — Phase 2's whole interface
tests/
  test_identity.py           # pure logic
  test_tools_filtering.py     # pure logic — fabricated permission payloads
  test_correctness_live.py     # real API + real model
PERMISSIONS.md   # tenant-isolation rules, confirmed live in Phase 1
QUESTIONS.md     # running log for office hours / client check-in
TEAM.md          # ownership + conventions — fill in together
```
