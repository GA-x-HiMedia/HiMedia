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

## Step 2 — merge main into reem, pick the better version

The merge itself was clean: main never touched `himedia.py`, `identity.py` or
`tools.py`, so there were no textual conflicts. Every entry below is instead a
place where my older work on `reem-local-backup` differed from what is now in
main, judged against README.md / PERMISSIONS.md / TEAM.md.

- **agent/himedia.py — named endpoints.** Main: one generic `get/post/patch`,
  with URL paths typed inside `tools.py`. Mine: a named function per endpoint.
  Kept MINE, added on top of main's helpers rather than replacing them —
  TEAM.md says URLs live in exactly one file "no exceptions", and main's shape
  put `/v1/tasks/{id}/comments` in tools.py. Main's `get/post/patch/call` stay
  exactly as they were so `tests/test_himedia.py` still passes.
- **agent/himedia.py — `list_task_comments(client_visible_only=)`.** Main had
  no way to read task comments at all. Kept MINE: it is the only endpoint that
  can return `client_visible: false` rows, and QUESTIONS.md flags it as the
  single easiest way to leak internal comments.
- **agent/himedia.py — `ApiRefused`.** Main carried `.code`/`.message`; mine
  also carried `message_ar`. Kept BOTH — `.message` unchanged for main's tests,
  `.message_ar` added so an Arabic caller can be refused in Arabic.
- **agent/identity.py — `allowed()` owner case.** Main read the permissions map
  only; mine also honoured `role.is_owner`, which arrives with an empty
  permission map from `/v1/roles`. Kept MINE: correct permission behaviour, and
  it cannot loosen anything for a non-owner.
- **agent/identity.py — helpers.** `is_client`, `phone_of`, `forget`,
  `colleagues_who_can`, `describe`, `UNKNOWN_NUMBER_REPLY` existed only in
  mine. Restored all of them; `phone_of` is what keeps the caller's number out
  of the model's reach, and the rest were dropped only because the shared repo
  never had them.
- **agent/tools.py — by-id visibility gate.** Main: none — `get_review_notes`,
  `update_task_status`, `comment_on_version` and `decide_version` acted on any
  id the model named. Mine: `_visible_task_ids` / `_visible_version_ids` +
  `NOT_YOURS`. Kept MINE. This is the tenant-isolation rule in PERMISSIONS.md;
  list endpoints filter on `?phone=`, by-id endpoints do not.
- **agent/tools.py — `published_to_client`.** Main returned it to everyone;
  mine hid it from clients. Kept MINE — it is always true in a client's own
  results, so it is noise to them and a staff-side signal otherwise.
- **agent/tools.py — `get_task_notes`.** Existed only in mine; main had no
  task-comment tool. Restored as a tenth tool. The README's tables list nine,
  but dropping it would leave `client_visible` filtering with nothing to apply
  to, and Step 5 needs it. Noted as a README correction rather than silently
  keeping the count at nine.
- **agent/tools.py — `comment_on_task`.** Existed only in main; mine had no
  such tool. Kept MAIN's — the README's Phase 3 table names it as one of the
  four write tools.
- **agent/tools.py — tool names.** Mine called it `list_my_tasks`; main calls
  it `list_tasks`. Kept MAIN's name — the README's Phase 2 table is the
  tiebreaker, and the rename is cosmetic where the permission behaviour is not.
- **agent/tools.py — `describe()` previews.** Mine had per-tool
  `describe_*(person, args)` builders with Arabic and real task titles; main
  has one `describe(name, args)`. Kept MAIN's for now — mine fetches the task
  by id to render its title, which would defeat the visibility gate by leaking
  the title of an item the caller cannot see.
- **agent/memory.py — pending expiry.** Main held a write forever; mine expired
  it. Kept MINE (`PENDING_SECONDS`, stale holds dropped by `peek_pending`) —
  a "yes" arriving hours later is answering a question the person no longer
  remembers. Main's `hold/peek/pop/has` signatures are unchanged.
- **agent/brain.py — permission re-check at confirm time.** Main ran the held
  tool without re-checking; mine re-filtered on the way out. Kept MINE —
  permissions are re-read every 60s precisely so a demotion takes effect, and
  a parked write is exactly where that gap opens.
- **agent/prompts.py — NOT restored, deliberately.** My older branch built the
  system prompt there. Zainab now owns `_system_prompt()` in `brain.py` and the
  brief says not to touch it; two prompt builders would be a real bug, not a
  merge artefact. Recording it here so the drop is logged, not silent — the
  file remains on `reem-local-backup` if it is ever wanted.
- **tests — old script-style suites.** `test_leaks.py`, `test_phase2.py` and
  `test_phase3.py` on my old branch are `main()`-style scripts, not pytest.
  Their unique coverage is being ported into real pytest tests in Step 3 rather
  than copied across as-is; nothing they covered is dropped.
