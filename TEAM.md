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
- **Branch workflow:**
  _(agree and fill in — e.g. feature branches off `main`, PR + one
  review before merge, or trunk-based with direct small commits — either
  is fine, just agree on one)_
- **Commit style:**
  _(agree and fill in — e.g. imperative mood, one logical change per
  commit)_

## Blockers / questions for the client or instructional team

See `QUESTIONS.md` — keep that file as the running log, don't duplicate
it here.
