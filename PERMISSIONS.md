# Permission & Tenant-Isolation Rules

What the **live sandbox** actually grants, and what the agent does about it.
Where this document and the handbook's printed table disagree, the live API
wins — `identity.allowed()` reads the API's own response and never a table we
maintain.

Regenerate the facts below at any time:

```bash
python -m agent.roster          # every seeded person, role and permissions
```

## The core rule

`none` < `read` < `write`. Write always includes read. A module not listed for
a role defaults to `none`. Read **live** from `GET /v1/permissions/by-phone` on
every message.

One exception, and it is in the data rather than in our code: the **owner**
role arrives with an empty permission map, meaning "everything" written as a
blank. `allowed()` honours `is_owner` directly so the answer never depends on
which endpoint happened to be read.

## Two things that are NOT scope

**audience** — `internal` (production-company staff) or `client` (client-org
staff). Decides which world of data someone can reach at all, and which voice
the agent uses.

**approval_rank** — 1 for an editor or photographer, 2 for a supervisor, 3 for
a director. Owners and some staff roles carry no rank at all.

### approval_rank is now enforced, and it was not before

This is the correction that matters most in this document. It previously said
rank was "enforced server-side by HiMedia, not by our tool filter". **Nothing
had tested that**, and in the meantime the consequence was visible in the
demo: an editor was offered *approve this client deliverable* exactly like the
director, because the only field separating them was the one nobody read.

`tools.tools_for()` now applies a floor (`MIN_APPROVAL_RANK = 2`) to
`decide_version`:

| Caller | Offered `decide_version`? | Why |
|---|---|---|
| rank 1 (editor, photographer) | **no** | the data calls this the lowest rank |
| rank 2–3 (supervisor, director) | yes | senior enough to end a review |
| owner (no rank) | yes | seniority is the whole point of the role |
| staff with no rank (account manager) | yes | the API does not rank them, so we do not invent one |
| client roles (no rank) | yes | approving their own deliverable is the normal flow |

The API remains the authority on *which stage* a given rank may decide. This
is a floor underneath it, not a replacement for it.

## Tenant isolation

- Hussain Media Production and Manara Studios are **competitors**. Neither
  should ever see the other's projects, tasks, or versions.
- Bank of Salam is a client of **both**. A Bank of Salam contact should see
  published work from both — but Hussain Media staff must never see Manara's
  work for Bank of Salam, and vice versa.
- Batelco is a client of Hussain Media only. Bank of Salam contacts must never
  see anything about Batelco, and the reverse.

**Confirmed live**, and pinned as a test rather than a claim
(`tests/test_isolation_live.py`): the same `GET /v1/versions` call returns
**8** versions for Khalid, **3** for Fatima and **0** for Rashid. Filtering
happens server-side, keyed off the phone number, and our code trusts the API's
answer rather than reconstructing it.

## Where the API filters for us, and where it does not

This distinction is the reason most of `tools.py` exists.

| | Filtered by caller? |
|---|---|
| **List** endpoints (`/v1/tasks`, `/v1/versions`, `/v1/projects`) | **Yes** — pass `phone=` and only their rows come back |
| **By-id** reads (`/v1/tasks/{id}`, comments) | **No** — the API trusts our key and hands over whatever we name |
| **Writes** (all four) | **No** — company is not checked at all |

So every by-id read and every write is gated in `tools.py` against a list of
what that caller can actually see. Without those gates a client at one company
could approve another company's version simply by naming its id.

## What client roles can and cannot do

No client role has any access to `invoices`, `finance`, `accounting`, `hr` or
`employees`. If the agent ever answers a client's money question with real
data, that is a filtering bug, not a permissions gap.

**Two corrections to the handbook's Ch. 11 table**, both confirmed live:

- The live API additionally grants every client role `tasks:read` and
  `audit_log:read`, which the printed table does not mention.
- The table lists `client_approver` as reading projects. **The live map has no
  `projects` key for any client role**, so `tools_for` does not offer them
  `list_projects`. We follow the live API. Expect a client asking "what
  projects do I have?" to be refused, and say so before a reviewer notices.

## Identity is not a phone number

A sender ID can be spoofed and a handset gets passed to a colleague, so the
number alone proves nothing:

- An **unknown** number gets a flat refusal and nothing else — no one-time
  code, because telling a stranger we have issued them one confirms both that
  the system exists and that we are processing them.
- A **known** number on a device we have not seen is challenged with a
  six-digit code, delivered out of band.

That check gates the chat path, and — since the demo — every web endpoint that
reads or clears one person's data. **Naming a number is not the same as being
that number.** An employee typing a manager's number gets the same refusal
whether or not that manager exists, so a refusal never confirms who is on the
system.

## Answered

- **Does `GET /tasks/{id}/comments` withhold `client_visible: false` comments
  for a client?** **No — it is our job.** Confirmed live against `tsk_0002`:
  the unfiltered call returned the internal comment in full, author name
  included. `tools.run_get_task_notes` sets `client_visible_only` from the
  caller's own audience, never from a tool argument. Evidence in
  `QUESTIONS.md`.

## Still to confirm

- [ ] What exactly happens when a client tries to comment on a version never
      published to their org — a 403, or something else?
- [ ] Whether `approval_rank` refusals come back with a distinct error `code`
      we should handle differently from a plain scope refusal. Now that we
      apply a floor of our own, knowing the API's own answer would let us
      confirm the two agree.
- [ ] Whether a client `client_reviewer` should really hold `reviews:write`.
      The live map grants it, so the agent offers it, and following the live
      map is the rule — but a role named *reviewer* being able to approve is
      worth raising with the client rather than quietly overriding.
