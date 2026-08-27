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

## Step 3 — leaks found and fixed

A leak = a client caller can see, or cause us to send out, staff names, vendor
names, costs, drafts, version labels, invoice numbers, or `client_visible:
false` comments. Every fix filters at the source, before the value can reach
the prompt — none of them edit the model's output afterwards. One regression
test each in `tests/test_leak_regressions.py`, named after the leak.

1. **`get_review_notes` on any version id.** It passed no caller phone and did
   no visibility check, so naming another client's version id returned that
   version's notes. Fixed with `_visible_version_ids` + `NOT_YOURS`.
   → `test_leak_review_notes_on_another_clients_version`
2. **Staff names in review-note authors.** Notes came back with `author_name`
   even to a client. Fixed with `_speaker()`: a client is told which SIDE spoke
   ("your team" / "the production team"), staff still get the real name.
   → `test_leak_staff_name_in_review_note_author`
3. **Internal version notes.** Version comments are not documented to carry
   `client_visible`, but any row that does is now dropped for a client rather
   than trusted. An absent flag is left alone; only an explicit false is
   dropped. → `test_leak_internal_comment_on_a_version`
4. **`published_to_client` shown to clients.** Internal publication bookkeeping
   was returned to the client it was about. Now staff-only.
   → `test_leak_published_to_client_flag_shown_to_a_client`
5. **`client_visible:false` task comments.** There was no task-comment tool at
   all, so the leak was latent: the moment one existed it would have returned
   internal rows. `get_task_notes` sets `client_visible_only` from the caller's
   audience, never from args.
   → `test_leak_internal_task_comment_reaches_a_client`
6. **Task notes on an internal task.** Naming an internal task id returned its
   title, status and every staff note. Fixed with `_visible_task_ids`.
   → `test_leak_task_notes_on_an_internal_task`
7. **Cross-company writes.** The sandbox filters reads by `?phone=` but does
   not police writes at all, so a client could approve or comment on another
   company's version by naming its id. All four write handlers now gate first.
   → `test_leak_cross_company_write_is_not_policed_by_the_api`
8. **The write preview itself.** The visibility check ran when the write ran,
   which is after the preview was already read back. "Approve version
   ver_teaser_v1?" confirms that id exists even if the write is later refused.
   `may_act_on()` now gates at hold time and the refusal goes back to the model
   instead. → `test_leak_write_preview_echoes_an_invisible_row`
9. **Held write survives a demotion.** A parked write ran on "yes" without
   re-checking permissions. Now re-filtered at the moment of writing.
   → `test_leak_held_write_runs_after_permission_is_lost`
10. **Held writes never expired.** A "yes" arriving the next morning ran an
    action the person had long forgotten agreeing to. `PENDING_SECONDS` now
    drops stale holds. → `test_leak_stale_held_write_still_runs`

Also carried over as a test rather than a fix (the behaviour was already
correct and is worth pinning): every handler takes the phone from `person`,
never from `args`, so a forged `phone`/`company_id`/`audience` argument changes
nothing. → `test_leak_caller_phone_can_be_overridden_by_tool_arguments`

- Chose to make the whole regression suite run offline against a fake sandbox
  rather than as live tests: the live leak test needs both network and a model
  key, and a leak test that cannot be run is a leak test nobody runs. The fake
  deliberately returns more than the caller should see, so a missing filter
  fails the test rather than passing quietly.

## Step 4 — the live leak test

- **Ran it for the first time. It did not get as far as the model.** Every
  attack errors in `_client_visible_text` on the first sandbox call:
  `GET /v1/projects` returns 404. The host itself is gone —
  `ga-sandbox-production.up.railway.app` answers Railway's edge error
  `{"status":"error","code":404,"message":"Application not found"}` on `/`,
  `/health` and `/docs` as well as on every `/v1/` path — and no
  `HIMEDIA_API_KEY` or model key is set in this checkout. Recorded as a
  blocker rather than worked around: a leak suite that "passes" because it
  never reached the data is worse than one that fails.
- **FORBIDDEN_WORDS is now derived, not guessed** (`tests/seed_forbidden.py`).
  The rule: a value is forbidden if staff can see it and the client cannot.
  That subtraction is what makes "Manara" drop out by itself — Bank of Salam
  is genuinely a client of Manara Studios (PERMISSIONS.md), so banning the
  word would flag a legitimate answer and train us to ignore the test.
- Chose to derive the list at run time rather than paste a snapshot into the
  file: `reset-demo` changes the seed data, and a pasted list silently rots
  into the same guessed list it replaced.
- The fixture asserts the derived list is non-empty. An empty list would make
  every assertion trivially pass, which is exactly how a broken leak test
  looks clean.
- **Assertions now run on the outbound payload too.** `brain._client()` is
  wrapped so the real provider call still happens, but every `messages` and
  `tools` payload is captured and searched. A clean reply built from a dirty
  prompt is still a leak — the data left the process and only the model's
  discretion kept it from the client.
- Kept the seven original attack messages unchanged; they are the graded set.

## Step 5 — the client_visible question

- Could NOT prove it live: the sandbox host is gone (404 "Application not
  found" on every path, including `/`) and no HIMEDIA_API_KEY is set. Wrote
  the experiment as `tests/test_comment_visibility_live.py` — same task, one
  call as a client, one as staff — and recorded its actual failure output.
- Left the QUESTIONS.md entry OPEN rather than closing it on the handbook s
  word. The entry exists precisely to check the handbook against reality, so
  closing it with reasoning instead of evidence would defeat it.
- Fixed tools.py anyway, because the fix is correct under both answers:
  `run_get_task_notes` sets `client_visible_only` from the caller audience and
  is the only path that reads task comments. If the API does filter, the flag
  is redundant; if it does not, it is the whole defence.
- Added the assertion to the offline regression suite rather than only the
  live one, so the guarantee is checked on every `pytest` run.

## Step 6 — measuring Arabic slowness

- Instrumented only; no behaviour changed. `audit.log_stage()` writes a second
  kind of record to the same `audit.log` (a `stage` key instead of a `tool`
  key), so tool-call records keep their existing shape and nothing that reads
  the log today breaks.
- Stages timed: `identity.who_is` (with cache hit / live fetch noted), each
  model round separately (`model_round_1`, `model_round_2`, …), each tool call
  (`tool:<name>`), `rounds_used`, and `total`. Each is tagged `ar` or `en` from
  the message itself, so the two languages can be compared.
- Chose to label language by Arabic script in the incoming message rather than
  by the caller's `locale`: people switch language mid-conversation, which is
  exactly what the system prompt tells the model to handle, so `locale` would
  mislabel half the rows.
- Chose deliberately paired messages in `tests/measure_latency.py` — five
  Arabic and five English that are translations of each other and within a few
  characters of the same length — so a difference in the table is a difference
  in handling the language, not in how much was asked.
- **Could NOT run the 5 + 5 measurement.** Same blocker as Steps 4 and 5: the
  sandbox host is gone and no keys are set, so `identity.who_is` fails before
  any message is sent. The reporting half was verified separately against
  simulated stage records, so the table renders correctly the moment real data
  exists. No numbers are reported here, because there are none — a made-up
  table is worse than an empty one.
- **The 60s cache is NOT missing.** `identity.CACHE_SECONDS = 60` and
  `who_is` checks `_cache` before fetching. It is per-process and in-memory, so
  it helps the WhatsApp path (`whatsapp.think_and_send` calls `who_is` on every
  inbound message) and is irrelevant to the CLI, which resolves the person once
  at startup and then loops. The instrumentation now records hits and fetches
  separately, so this stops being a guess.
- **Flagging a cost I added in Step 3, without optimising it.** The visibility
  gates call the list endpoints to find out what the caller may see, and those
  calls are not cached. A gated read like `get_task_notes` is now three API
  round-trips (`list_tasks` + `get_task` + `list_task_comments`) where it used
  to be one, and each held write costs one more at preview time and again at
  confirm time. That is the price of the tenant-isolation fix and it is worth
  paying, but it belongs in the latency picture. The obvious fix — a short
  per-message cache of the visible-id sets, on the same 60s logic as
  `who_is` — is deliberately NOT done here, because this step says measure,
  not optimise.

## Step 7 — exact-phrase confirmation for destructive writes

- Kept the existing yes/y/ok/اي/ايوه/نعم/تمام/اوك list for harmless
  confirmations, unchanged. Only `decide_version` requires the exact phrase.
- Chose `decide_version` as the only member of `EXACT_PHRASE_TOOLS` for now:
  it is the one that decides something on the client behalf and the one
  with no undo. `update_task_status` and the two comment tools are annoying to
  get wrong, not damaging, and putting them behind a phrase would train people
  to paste it without reading.
- One constant, `brain.CONFIRM_PHRASE`, used by both the check and the message
  that asks for it — so the phrase a person is told to type is by construction
  the phrase that works. A test asserts the literal appears exactly once.
- Anything that is not the phrase CANCELS rather than re-prompting. A pending
  destructive write that survives a wrong answer is a write waiting for a
  stray "yes" — the person can simply ask again.
- Matching is exact after `.strip()`, not substring: a sentence containing the
  phrase does not count, or the model could produce one on the person behalf.
  Whitespace is forgiven because it is a typing artefact, not a different
  answer.
- Diff kept to +53/-1 in brain.py; nothing reformatted, and `_system_prompt()`
  (Zainab work) not touched.

## Step 8 — teammates work, verified not redone

- **Zainab — Bahraini dialect guidance in `_system_prompt()`: DONE.** Present
  in `agent/brain.py` (commit c9e3807, "Add Bahraini Arabic dialect guidance"):
  natural Bahraini Arabic, professional tone, no forced slang, technical terms
  kept accurate. It still respects the audience rules — the client voice bars
  staff names, costs, invoices, drafts and other clients work, and the prompt
  says outright that "language and tone must never override audience
  restrictions or permissions". Not touched, as instructed.
- **Sara — OTP / first-device verification in `identity.py`: MISSING.** Not in
  `main`, and not on `origin/sara` either — the only trace is a docstring and a
  README line saying a production version *would* do it. Implemented the
  smallest working version in its own commit prefixed "TEMP (Sara task):".
- Chose to deliver the code OUT OF BAND (server log, standing in for the email
  a real version sends) rather than over the same WhatsApp thread. Sending it
  back down the thread that asked for it proves nothing — whoever holds the
  number just reads it. That is the part worth keeping whatever else changes.
- Chose to add a `device_gate()` helper that returns None when the device is
  trusted, so wiring it into `whatsapp.py` is three lines. Sara replacing this
  only has to touch `identity.py`.
- The code never reaches `audit.log` — only the fact that one was issued. The
  audit trail is a record of what happened, not a place to keep secrets.
- Kept it in memory like the rest of the project state (README, "what is not
  finished"): a restart asks everyone to verify again.
