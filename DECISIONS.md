# DECISIONS.md

One line per judgement call, with the reason. Newest step at the bottom.

## Step 0 — find and protect earlier work

- Working repo is `shared repo/HiMedia`; `whatsapp-agent` is a separate
  personal repo already wired in as the git remote `mine` — treated it as
  "my earlier work" rather than a stray copy, because its 3 commits are
  authored by me and predate the shared repo's history.
- Both working trees were clean and both stash lists empty, so there was
  nothing uncommitted to rescue — the earlier work was whole-repo, not
  loose files.
- Created `reem-local-backup` at `mine/main` (61c8fae) instead of leaving
  the old work in a second repo, so Step 2 can diff my older version
  against main inside one repository.
- Found a dangling commit af2b9a3 ("ex", a single empty file) orphaned by
  an earlier `reset --hard`; tagged it `rescued-dangling-ex` rather than
  ignoring it, so it can never be garbage-collected. It contains no real
  work.
- Fast-forwarded `main` to origin/main (22 commits); `reem` was already
  level with origin/reem. Deleted nothing, force-pushed nothing.

## Step 1 — project doc

- Treated README.md as the spec and PERMISSIONS.md as the authoritative
  permission/visibility ruling, with TEAM.md for conventions — these are
  the tiebreaker for every Step 2 choice.
