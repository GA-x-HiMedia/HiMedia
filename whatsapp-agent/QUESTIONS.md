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
- **Status:** open

- **Question:**
- **Why it matters:**
- **Already tried:**
- **Status:** open
