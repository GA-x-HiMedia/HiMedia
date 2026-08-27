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
  applying the audience rule is your job." Confirmed against the live
  sandbox rather than taken on trust.
- **Status:** ANSWERED — **we must pass it ourselves, on every call.**

  **The evidence.** Run on the live sandbox against `tsk_0002`, a task
  Fatima (client_approver @ Bank of Salam) can legitimately see, carrying
  two comments: one client-visible, one `client_visible: false`.

      GET /v1/tasks/tsk_0002/comments                          -> 2 comments, 1 internal
      GET /v1/tasks/tsk_0002/comments?client_visible_only=true -> 1 comment,  0 internal

  The unfiltered call returned the internal comment in full, author name
  included. The endpoint takes no `phone` parameter at all: it
  authenticates on our API key and has no idea a client is asking.

  Confirmed the same way for the by-id reads generally — they ignore
  `phone=` even when you pass it:

      GET /v1/tasks/tsk_0001?phone=<Fatima>  -> "Ed… — v3"  (an internal task title, masked)

  That is an internal task (`client_visible: false`) returned in full to a
  client's phone number, title and all. Chapter 16's "almost every list
  endpoint accepts phone=" is exactly right — *list* endpoints. The by-id
  ones do not filter, which is why `agent/tools.py` gates them itself.

  **What the code does.** `tools.run_get_task_notes` sets
  `client_visible_only` from the caller's own audience
  (`identity.is_client`), never from a tool argument, and it is the only
  path in the project that reads task comments. Verified live by
  `tests/test_comment_visibility_live.py`, which asserts the internal
  comment reaches staff and never reaches the client, and offline by
  `tests/test_leak_regressions.py::test_leak_internal_task_comment_reaches_a_client`.

  **Reproduce it:**

      RUN_LIVE_TESTS=1 pytest tests/test_comment_visibility_live.py -v -s
      python -m tests.test_comment_visibility_live      # prints the raw evidence

  Note: the demo seed data had no internal comment on any client-visible
  task, so one was posted on `tsk_0002` to create the condition. It is
  still there; `POST /v1/admin/reset-demo` clears it (tell the class first).

- **Question:**
- **Why it matters:**
- **Already tried:**
- **Status:** open
