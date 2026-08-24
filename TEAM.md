# Team Decisions

Fill this in together, then commit it — it's the record of who owns what
and how the team works, not just a formality.

## Ownership

- **API integration owner:**
- **Permissions & identity owner:**
- **Testing, documentation & evaluation owner:**

(One person can own more than one area on a 3-person team — the point is
that every area has a name attached, not that they're evenly split.)

## Conventions

- **Naming:** snake_case for Python, matching the API's own field-naming
  convention (Handbook Ch. 6 — "always `full_name`, never `fullName`").
- **API URLs live in exactly one file:** `agent/himedia.py`. If a URL
  needs typing anywhere else in the project, it belongs here instead —
  no exceptions, this is what Chapter 22 calls "the one rule for it."
- **Branch workflow:** feature branches off `main`, PR + one review
  before merge. Each of us has a personal branch (`sara`, `reem`,
  `zainab`) for work in progress; short-lived `chore/*` or `feat/*`
  branches for anything self-contained. Nobody pushes directly to
  `main`, and nobody force-pushes a branch someone else can see.
  Merge `origin/main` into your branch often — small merges never
  conflict badly, one big merge at the end always does.
- **Commit style:** imperative mood ("Add roster filter", not "added"),
  one logical change per commit. Say *why* in the body when the reason
  isn't obvious from the diff.

## Blockers / questions for the client or instructional team

See `QUESTIONS.md` — keep that file as the running log, don't duplicate
it here.
