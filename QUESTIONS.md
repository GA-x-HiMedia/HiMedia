# API Questions & Blockers

Log anything unclear or blocking here as it comes up, then bring the list
to office hours or the client/instructional check-in (Handbook Ch. 36
— "paste the exact request, the exact response, and what you expected").

## Format

- **Question:**
- **Why it matters:**
- **Already tried:**
- **Status:** open / answered / blocked

## Current list

- **Question:** Does `GET /tasks/{id}/comments` filter out
  `client_visible: false` comments automatically for a client caller, or
  do we have to pass `client_visible_only=true` ourselves every time?
- **Why it matters:** If the API doesn't enforce this and trusts our API
  key instead, this is the single easiest way to accidentally leak
  internal comments to a client.
- **Already tried:** Re-read Chapter 19 — the handbook says explicitly
  "the API will happily return internal comments if you ask for them...
  applying the audience rule is your job." Confirm this is still true
  against the live sandbox before assuming it.
- **Status:** OPEN — but no longer load-bearing. See below.

  **What the code does now, either way.** `tools.run_get_task_notes` sets
  `client_visible_only` from the caller's own audience
  (`identity.is_client`), never from a tool argument, and it is the only
  path in the project that reads task comments. So a client cannot be
  handed a `client_visible: false` comment whether the API filters or not.
  Pinned by `tests/test_leak_regressions.py::test_leak_internal_task_comment_reaches_a_client`,
  which asserts the flag is actually passed as `True` for a client and
  `False` for staff.

  **Why it is still marked open.** The experiment the question asks for —
  same task, one call as a client, one as staff, on a task carrying a
  `client_visible: false` comment — has been written as
  `tests/test_comment_visibility_live.py` but has never produced a result,
  because the sandbox is unreachable from this checkout:

      $ RUN_LIVE_TESTS=1 pytest tests/test_comment_visibility_live.py -v -s
      E   agent.himedia.ApiRefused: ERROR: Something went wrong.
      (GET /v1/projects -> 404)

      $ curl https://ga-sandbox-production.up.railway.app/
      {"status":"error","code":404,"message":"Application not found"}

  That 404 is Railway's edge error on `/`, `/health` and `/docs` as well as
  every `/v1/` path, so it is the host, not the route — and no
  `HIMEDIA_API_KEY` is set here either. Recording this as unproven rather
  than closing it on the handbook's word: the whole point of the entry was
  to check the handbook against reality.

  **To close it:** point `HIMEDIA_BASE_URL` at a live sandbox, set
  `HIMEDIA_API_KEY`, then run

      python -m tests.test_comment_visibility_live

  and paste its output here. It prints both calls side by side and states
  the answer outright. If a task with an internal comment does not exist in
  the current seed data it says so rather than guessing.

- **Question:**
- **Why it matters:**
- **Already tried:**
- **Status:** open
