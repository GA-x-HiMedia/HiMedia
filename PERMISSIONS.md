# Permission & Tenant-Isolation Rules — Working Notes

Draft synthesis from Handbook Chapters 10–11, plus what we've directly
observed against the live sandbox. This is a working doc, not a
substitute for reading the chapters yourselves — update it as the team
learns more, and correct anything here that turns out to be wrong.

## The core rule

`none` < `read` < `write`. Write always includes read. A module not
listed for a role defaults to `none`. These are read **live** from
`GET /v1/permissions/by-phone` on every message — never hardcoded on our
side (`agent/identity.py::allowed`).

## Two things that are NOT permissions

- **audience** — `internal` (production-company staff) or `client`
  (client-org staff). Decides which world of data someone can reach at
  all, and which system-prompt voice we use.
- **approval_rank** — 1 (editor/photographer), 2 (supervisor), 3
  (director). Separate from read/write scope. A role can hold
  `reviews:write` and still get refused by `decide_version` if their rank
  is too low for a given review stage — enforced server-side by HiMedia,
  not by our tool filter (see `agent/tools.py` comments).

## Tenant isolation, concretely

- Hussain Media Production and Manara Studios are **competitors**.
  Neither should ever see the other's projects, tasks, or versions.
- Bank of Salam is a client of **both** vendors. A Bank of Salam contact
  should see published work from both — but Hussain Media staff must
  never see Manara's work for Bank of Salam, and vice versa.
- Batelco is a client of Hussain Media only. Bank of Salam contacts must
  never see anything about Batelco, and Batelco contacts must never see
  anything about Bank of Salam.

**Confirmed live** (`python -m agent.explore`, run on [fill in date]):
Khalid (internal, Hussain Media) and Fatima (client, Bank of Salam) get
different results for the identical `GET /v1/projects?phone=...` call —
filtering happens server-side, keyed off the phone number. Our code does
not reconstruct this filtering itself; it trusts the API's answer.

## What client roles can and cannot do

No client role has any access to `invoices`, `finance`, `accounting`,
`hr`, or `employees` — confirmed against the live scopes in
`agent/roster.py`'s output. If the agent ever answers a client's money
question with real data, that is a filtering bug, not a permissions gap
that needs designing around.

**Correction to the handbook's own summary table (Ch. 11):** the live API
additionally grants every client role `tasks:read` and `audit_log:read`,
which the handbook's table doesn't mention. Our code follows the live
API, not the printed table, since `allowed()` reads the API's response
directly — but worth flagging in review so nobody's surprised by it.

## Still to confirm

- [ ] Task comment visibility (`client_visible` flag) — does
      `GET /tasks/{id}/comments` actually withhold `client_visible: false`
      comments when called on behalf of a client, or is that our job to
      filter client-side? (Handbook Ch. 19 suggests we must pass
      `client_visible_only=true` ourselves — confirm this against a real
      response before trusting it.)
- [ ] What exactly happens when a client tries to comment on a version
      never published to their org — confirmed 403, or something else?
- [ ] Whether `approval_rank` refusals come back with a distinct error
      `code` we should handle differently from a plain scope refusal.
