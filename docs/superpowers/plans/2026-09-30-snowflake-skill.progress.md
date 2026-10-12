# SDD ledger — plan: docs/superpowers/plans/2026-09-30-snowflake-skill.md

Progress file for the plan (its "How to run" names this path) and the subagent-driven-development ledger.
Spec: docs/superpowers/specs/2026-09-30-snowflake-skill-design.md (read; binding authority).
SDD workspace (briefs, reports, review packages; gitignored): .superpowers/sdd/2026-09-30-snowflake-skill/
Branch: snowflake-skill. Branch start (merge-base with main): ddcb2af.

## Status

- Next task: none — all 35 tasks complete; finishing (merge choice) with the user
- Task order: 1–26, then 31, then 27–30, 32–35 (see ruling R8)

## Pre-flight rulings

- R1 Ruling: work on the existing `snowflake-skill` branch in the main checkout, no separate git worktree — the plan says to work in /Users/jkarnik/Code/Snowflake, and the repo relies on gitignored local state (.venv, runs/, .sfrun/) plus absolute paths in the MCP registration — cost if wrong: none; the branch already keeps the work off main.
- R2 Ruling: this progress file is the SDD ledger and stays untracked (never committed during execution); Task 35's "clean tree" check allows this one untracked file — recording a commit's SHA inside that same commit is impossible, and extra ledger commits add noise — cost if wrong: one untracked file in `git status` that the user can commit or delete.
- R3 Ruling: Task 25's `.gitignore` anchors the runs rule as `/runs/` instead of `runs/` — an unanchored `runs/` also ignores `tests/fixtures/runs/` (checked: `git check-ignore -v tests/fixtures/runs/x` → `.gitignore:9:runs/`), so Task 31's `git add tests/fixtures` would silently commit only expected.md, while spec §7 says the made-up runs are tracked — cost if wrong: none; `/runs/` still ignores the root runs/ folder.
- R4 Ruling: every dispatch tells the subagent to ignore the project CLAUDE.md (old toolkit: never start session_server.py, never use ./q, never write to runs/latest), per the plan's Global Constraints — that file loads into every subagent's context and says the opposite — cost if wrong: none.
- R5 Ruling: the old session_server.py is running again (PID 65591, a parallel session); the user got an early heads-up. At Task 25, if it still runs, do Task 26 first, recheck, and stop to ask only if it's still running (P12: never kill it) — cost if wrong: a short delay.
- R6 Ruling: Task 27 also runs the README recheck Task 26 promises (`test -e tests/live_login_check.py`) — Task 26 says "that task rechecks the README", but Task 27 has no such step — cost if wrong: none.
- R7 Ruling: the title edit in Snowflake.md is already committed (ddcb2af: `# Snowflake Skill`), so the "keep the uncommitted title edit" constraint holds through `git mv` with no extra step — cost if wrong: none; Task 20 rewrites the file with that title anyway.
- R8 Ruling: Task 31 (not live; fixtures only) runs right after Task 26, before the first LIVE task — it depends only on Task 25's .gitignore, and this keeps the live stretch (27–30, 32–34) in one block so the user isn't pulled back more often — cost if wrong: none; no task between 27 and 30 reads or writes the fixtures.
- R9 Ruling: before every LIVE task (27, 28, 29, 30, 32, 33, 34) the controller stops, tells the user how many Okta logins it opens, and waits for a go-ahead (plan "How to run" + the user's own request). LIVE implementers never open a login beyond the approved count: if a task needs more (a re-run, a fix), the implementer stops and reports back, and the controller asks the user — subagents can't talk to the user — cost if wrong: extra pauses.
- R10 Ruling: Tasks 22–23 write outside the repo (~/.snowflake/connections.toml, the user-scope MCP registration, the ~/.claude/skills link) without a separate prompt — they're in the plan the user approved, local, reversible, and the README documents uninstall — cost if wrong: the user runs the README's uninstall commands.
- R11 Ruling: tasks with no commit (22; parts of the LIVE tasks) still get a task review: the reviewer checks the resulting state read-only (file contents, mode, command output in the report) instead of a diff — the skill never skips a task review — cost if wrong: one cheap reviewer run.
- R12 Ruling: keep Task 8's `test_write_never_raises` as written — its only assertion is that no exception escapes, which is the whole contract of `EventLog.write` ("never raises") — cost if wrong: a reviewer finding to adjudicate later.
- R13 Ruling: keep the small repeated constants in standalone scripts (`CLAUDE` path, `REPO`, the `PLACEHOLDER` regex in check_notes.py and run_eval.py, the `anyio_backend` fixture in two test files) as the plan writes them — each script runs on its own, and the fill logic differs (SQL quote doubling vs plain prompt text) — cost if wrong: minor cleanup later.

## Pre-flight scan

### Tasks that share a file or interface

| Tasks | Produces → consumes | Finding |
|---|---|---|
| 2 ↔ 25 | `.gitignore`: 2 appends caches; 25 replaces the file | 25 keeps the cache lines ✓; its unanchored `runs/` is R3 |
| 25 → 31 | 25's `.gitignore` governs 31's `git add tests/fixtures` | defect: fixtures silently ignored → R3 |
| 4 → 5 → 6 → 7 | `results.py` and `test_results.py` grow in sequence; each edits the import lines | cumulative imports line up; counts 7 → 13 → 18 → 20 ✓ |
| 8 → 9, 11, 12, 13 | `EventLog.write`; event names | names match (`server_started`, `login_started`, `logged_in`, `query_finished`, `query_failed`) ✓ |
| 9 → 10 | `connection.py` edit points (`_login` line, `discard` appended after `state()`) | `state()` is the last method after 9 ✓; 9 → 24 tests ✓ |
| 9 (`fakes.py`) → 10–13 | `FakeConnector(delay, error, prints)`, `calls`, `connections`; `FakeConnection.result/fail_with/executed` | every use matches ✓ |
| 10 → 11, 12, 14 | `default_connect`, `classify_error`, `discard` | signatures match ✓ |
| 11 → 12 | `server.py` import block and the single `return server`; `test_server.py` import edits | "13 failed, 6 passed", then suite 106 ✓ |
| 11/12 → 13 | `server.main`; module-global `default_connect` override | `main()` looks it up at call time ✓; suite 107 ✓ |
| 3, 9, 10 → 14 | `check_sql`, `LazyConnection`, `classify_error` | ✓; suite 111 ✓ |
| 14 → 15–19, 28 | `check_notes.py --dry-run` block counts | 8 + 2 (lines 56, 76) + 5 + 4 = 19 ✓ |
| 15–19 → 20 | SKILL.md reference index names six notes | all six created ✓ |
| 20 → 23, 29, 30, 32 | skill name, tool names, `allowed-tools` | consistent ✓ |
| 21 ↔ 27 | `values.toml` keys | 27 writes all 12 P10 keys ✓ |
| 21 → 29, 30 | `run_eval.py` outputs (`facts.json`, `answer.md`, …) | consistent ✓ |
| 22 → 23, 27 | `[newrelic]` connection | consistent ✓ |
| 23 → 26, 35 | `check_install.py` | consistent ✓ |
| 26 ↔ 27 | README names `tests/live_login_check.py`; 26 says 27 rechecks it | 27 has no recheck step → R6 |
| 17, 18 → 24 → 25 | originals read (17, 18), moved (24), `.sfrun/` deleted (25) | order safe ✓; `.sfrun/` holds exactly the expected files today ✓ |
| 20 ↔ Global Constraints | "uncommitted title edit" | already committed → R7 |
| 25 ↔ P12 | old toolkit must not be running | it is running today → R5 |
| 31 → 32, 33, 34 | fixtures, `expected.md`, `$T` set-up | consistent ✓ |
| 28 → 33 | billing.md length after 28, plus 251 | "about 341" is approximate ✓ |
| 35 ↔ this ledger | "clean tree" vs the untracked progress file | → R2 |

### Each task against itself

| Task | Check | Finding |
|---|---|---|
| 1 | dry-run guard, versions line | ✓ |
| 2 | `no tests ran`, exit 5 | ✓ |
| 3 | 18 allowed + 23 refused = 41; every refused reason matches a guard branch | ✓ |
| 4 | 7 tests; slug examples traced through `slugify` | ✓ |
| 5 | 13; round-trip values traced through `_cell` | ✓ |
| 6 | 18; preview escapes and 200-char cut traced | ✓ |
| 7 | 20; stray file and legacy folders excluded | ✓ |
| 8 | 2 tests | ✓; no-assert test → R12 |
| 9 | 9 tests; timeout, late-login and retry paths traced through `get`/`_login` | ✓ |
| 10 | 9 + 1 + 1 + 1 + 11 + 1 = 24 | ✓ |
| 11 | 6 tests; `REPO = parents[3]` | ✓ |
| 12 | 19 in file; suite 106 | ✓ |
| 13 | launcher overrides `default_connect`; suite 107 | ✓ |
| 14 | fence lines 3 and 9; KeyError text; suite 111 | ✓ |
| 15 | 8 blocks; 125 lines | ✓ |
| 16 | blocks at lines 56 and 76; 90 lines | ✓ |
| 17 | 5 blocks; 103 lines | ✓ |
| 18 | 4 blocks; 100 lines | ✓ |
| 19 | no `sql` blocks; 19 PASS total | ✓ |
| 20 | 88 lines; YAML description has no `: ` | ✓ |
| 21 | 3 tests; suite 114 | ✓ |
| 22 | look-before-write, mode 600 | ✓ |
| 23 | look-before-change; symlink fallback | ✓ |
| 24 | 4 fingerprints; `D  company_query.sql` | ✓ |
| 25 | status lines; suite 114 | ✓ with R3 |
| 26 | file-exists loop | ✓ |
| 27 | offline guard check before the login | ✓; README recheck missing → R6 |
| 28–30 | warn-and-wait; extra logins need the user | ✓ with R9 |
| 31 | 14 run files + expected.md = 15; 6 folders | ✓ |
| 32–34 | clean `skills/` check; revert with `git checkout` | ✓ |
| 35 | "clean tree" | → R2 |

Brief extraction: all 35 briefs checked against heading line ranges — every one exact.

## Task log
- Task 1: dispatched (base ddcb2af, implementer a54d263fd41d8a218, haiku)
- Task 1: BLOCKED at Step 3 — auto mode denied `pip install` into the shared .venv while the parallel session's session_server.py (PID 65591) runs; Steps 1–2 done (requirements.txt written, uncommitted; dry run adds 27 new packages, changes neither snowflake-connector-python nor keyring). Waiting on the user.
- Task 1: user chose to close the other session first (2026-09-30); watching for session_server.py to exit, then resume the implementer at Step 3.
- User asked to force close the old session_server.py (overrides P12's never-kill rule); sent its documented QUIT shutdown at 23:22:53.
- Old session_server.py exited cleanly after QUIT (within 5 s). Task 1: resumed implementer at Step 3.
- Task 1: implementer DONE (43f7bd7); review dispatched (reviewer a116c8ade7c46de45, sonnet, package review-ddcb2af..43f7bd7.diff)
- Task 1: minor (deferred): requirements.txt pins only the four top-level packages; transitive dependencies float (P8 as written)
- Task 1: complete (commits ddcb2af..43f7bd7, review clean)
- Task 2: dispatched (base 43f7bd7, haiku)
- Task 2: implementer DONE (240128f); review dispatched
- Task 2: minor (deferred): commit trailers name each subagent's own model (240128f says Claude Haiku 4.5), not the controller's attribution line — metadata only
- Task 2: minor (deferred): task-2 report miscounts lines (pytest.ini is 3 lines, .gitignore gained 4); diff correct
- Task 2: ⚠️ import promise resolved — reviewer proved the config in a scratch project; Task 3's first run confirms in-repo
- Task 2: complete (commits 43f7bd7..240128f, review clean)
- Task 3: dispatched (base 240128f, haiku)
- Task 3: implementer DONE (adbc573, implementer a9d8d7d734548e8f1); review dispatched
- Task 3: review (aa3044366cf42fb22): spec ❌, Needs fixes — 1 Critical (`->>` flow-operator chains pass the guard), 1 Important (false BLOCKED on some DESCRIBE forms and a bare `(SELECT …)`), 6 Minor
- Task 3: Ruling: fix the `->>` bypass (Critical 1) although the plan mandates the guard code verbatim — spec §5.3 refuses "input containing more than one statement", a `->>` chain is several statements with no `;` for sqlglot to split on, and Snowflake has no other `->>` operator, so a token-level refusal blocks no single read — cost if wrong: a read-only `SHOW … ->> SELECT …` chain gets BLOCKED and Claude runs it as two queries.
- Task 3: Ruling: keep refusing DESCRIBE forms sqlglot can't parse (DESC STREAM/TASK/PIPE/SHARE/ALERT/USER, DESCRIBE RESULT, DESC SEARCH OPTIMIZATION) — spec §5.3 says the guard refuses "any statement that sqlglot cannot classify", and a first-token fallback would need its own statement splitting to stay safe; DESCRIBE TABLE/VIEW (what the notes use) pass — cost if wrong: a rare admin-object question gets BLOCKED; SHOW STREAMS/TASKS/PIPES still work.
- Task 3: Ruling: keep refusing a bare parenthesized top-level SELECT (`(SELECT 1)`) — the plan's Verified Facts list `Subquery` as a refused shape, the error names it, and Claude recovers by dropping the parentheses; `(SELECT …) UNION ALL (SELECT …)` passes — cost if wrong: one extra retry on a rare query shape.
- Task 3: Ruling: the `->>` regression tests add 2 guard tests, so every later "N passed" count in the plan is N+2 (106→108, 107→109, 111→113, 114→116); later dispatches carry this — cost if wrong: none.
- Task 3: minor (deferred): RecursionError escapes check_sql on ~60 nested parentheses (fails closed, but run_query would return a bare "Error executing tool")
- Task 3: minor (deferred): SELECT … INTO is caught only at top level (UNION/CTE/subquery forms pass; Snowflake has no table-creating SELECT INTO outside scripting)
- Task 3: minor (deferred): `DESCRIBE <DML statement>` is classified DESCRIBE (Snowflake rejects it as a syntax error)
- Task 3: minor (deferred): test gaps — CTE-wrapped writes, EXECUTE IMMEDIATE, SET, BEGIN/COMMIT, Command-SHOW + second statement, lowercase keywords
- Task 3: minor (deferred): error text uses sqlglot class names ("Alias", "TruncateTable"); pinned by plan-mandated tests
- Task 3: minor (deferred): task-3 report miscounts cases (18 allowed / 23 refused) and says "no concerns"
- Task 3: ⚠️ resolved — "server sends SQL unchanged" is by design (check_sql returns only a kind); re-check in Task 12's review. ⚠️ Snowflake's execution of `->>` chains can't be checked offline; the ruling treats it as real (fail closed).
- Task 3: fix round 1/5 dispatched (resume a9d8d7d734548e8f1; FIX_BASE adbc573) — Critical 1 only
- Task 3: fix round 1 committed (b3abb36, 43 passed in test_guard.py); scoped re-review dispatched (a12fb80e20528ad8a, sonnet)
- Task 3: fix round 1/5 (1 addressed, 0 open — `->>` bypass; commits adbc573..b3abb36)
- Task 3: complete (commits 240128f..b3abb36, review clean after 1 fix round)
- Task 4: dispatched (base b3abb36, haiku)
- Task 4: implementer DONE (a35101b, implementer adc2616afb280425f); review dispatched
- Task 4: minor (deferred): coverage gaps confirmed by mutation — call-site fallbacks "question"/"query", the rstrip after the 60-char cut, question_dir's default date, and utf-8 SQL writes are untested
- Task 4: minor (deferred): parallel test covers threads only (code is also correct across processes, per reviewer probe); barrier.wait()/join() have no timeouts
- Task 4: minor (deferred): task-4 report claims a containment check that doesn't exist (slugify's whitelist is the protection, and suffices)
- Task 4: ⚠️ carried to Task 12's review — run_query must call save_query once per query and use its returned csv_path
- Task 4: complete (commits b3abb36..a35101b, review clean)
- Task 5: dispatched (base a35101b, haiku)
- Task 5: implementer DONE (e7862bb, implementer afb4eaa1aac8d3f2b); review dispatched
- Task 5: minor (deferred): `if count == max_rows` fails open for max_rows < 1 (unreachable through run_query: Pydantic rejects max_rows < 1); `>=` would fail closed
- Task 5: minor (deferred): test gaps — no `\r`/`\r\n` or bytearray in TRICKY, no max_rows < preview_rows case, no-columns test doesn't assert truncated/preview
- Task 5: minor (deferred): CsvResult/write_csv lack one-line contract comments (preview holds raw rows; truncated means more rows existed)
- Task 5: minor (deferred): task-5 report's line counts and "test output" block are hand-built, not real pytest output (GREEN "13 passed" is real)
- Task 5: ⚠️ carried to Task 6's review — "0 rows" and the truncation note are rendered by format_result; ⚠️ carried to Task 12's review — a failure inside write_csv mid-stream must still delete the partial CSV
- Task 5: complete (commits a35101b..e7862bb, review clean)
- Task 6: dispatched (base e7862bb, haiku)
- Task 6: implementer DONE (8396ca0, implementer a293fd030d5d8dac4); review dispatched
- Task 6: minor (deferred): preview escapes only \n and \r (other Unicode line separators pass raw); the 200-char cut applies after escaping and can split an escape pair
- Task 6: minor (deferred): untested — _preview_cell bytes→hex, the 200/201 boundary, a non-default max_cell
- Task 6: minor (deferred): bytes→hex rule duplicated in _cell and _preview_cell
- Task 6: minor (deferred): commit 8396ca0 has its Co-Authored-By trailer glued to the subject (no blank line); standing context now spells out the commit-message layout
- Task 6: ⚠️ carried to Task 12's review — run_query must keep write_csv's default preview_rows=50, and SQL:/CSV: paths come from an absolute runs_dir
- Task 6: complete (commits e7862bb..8396ca0, review clean)
- Task 7: dispatched (base 8396ca0, haiku)
- Task 7: implementer DONE (7e7c69f, implementer a93b79e1294eb8248); review dispatched
- Task 7: review (abc31aa0296fa1c59): spec ✅, Approved, but 1 Important (plan-mandated): the decoy folders in test_unlearned_folders_lists_question_folders_not_yet_learned are empty, so deleting the `_DAY` filter still passes
- Task 7: Ruling: fix the plan-mandated test — give each decoy a child folder so the test fails without the `_DAY` filter — P13 is binding and a test that can't fail doesn't guard it; the change is test-only, keeps the count at 20 and leaves results.py untouched — cost if wrong: none.
- Task 7: minor (deferred): sort order only weakly pinned (removing sorted() gives a flaky, not failing, test)
- Task 7: minor (deferred): learned.txt parsed with .split(), so a hand-made folder name with spaces is never "learned" (tool-made slugs can't contain spaces)
- Task 7: minor (deferred): _DAY uses \d and $ (accepts non-ASCII digits and a trailing newline); re.ASCII + fullmatch would be exact
- Task 7: minor (deferred): task-7 report's line counts are wrong
- Task 7: ⚠️ resolved — updater.md (Task 19) writes one `YYYY-MM-DD/<question>` per line; build_server passes one runs_dir to both question_dir and unlearned_folders (plan Tasks 11–12); re-check in Task 12's review
- Task 7: fix round 1/5 dispatched (resume a93b79e1294eb8248; FIX_BASE 7e7c69f)
- Task 7: fix round 1 committed (7fa8a0e; test-only; mutant run fails, restored run passes; 20 passed); scoped re-review dispatched (a8dca46feb0b3b38a, haiku)
- Task 7: fix round 1/5 (1 addressed, 0 open — decoy test now guards the _DAY filter; commits 7e7c69f..7fa8a0e)
- Task 7: complete (commits 8396ca0..7fa8a0e, review clean after 1 fix round)
- Task 8: dispatched (base 7fa8a0e, haiku)
- Task 8: implementer DONE (2d23bf0, implementer ade43451234fcbe74); review dispatched
- Task 8: review (a68264c2b62a79b48): spec ✅, Needs fixes — 1 Important (plan-mandated): EventLog.write catches only OSError and formats outside the try, so a lone surrogate, a raising __str__ or event=None escapes "never raises"
- Task 8: Ruling: fix it although the plan gives the code verbatim — "never raises" is the shared-interface contract Tasks 9–12 build on (they call write bare, including in the login thread, where an escape would skip `attempt.done.set()` and turn a login failure into a 2-minute LOGIN_TIMEOUT); move the whole body into the try, catch Exception, open with errors="replace", and extend the existing test_write_never_raises so the suite count doesn't change — cost if wrong: none; a broad except in a logger can only hide logging bugs, never break a query.
- Task 8: minor (deferred): only "\n" is flattened in values, so "\r" or Unicode line separators could split a record (no planned caller passes free text; Task 27's parser skips non-matching lines)
- Task 8: minor (deferred): task-8 report's RED traceback looks retyped, not pasted (GREEN run is real)
- Task 8: fix round 1/5 dispatched (resume ade43451234fcbe74; FIX_BASE 2d23bf0)
- Task 8: fix round 1 committed (f9c712a; failing-then-passing evidence; 2 passed); scoped re-review dispatched (a50d99ea03b5d879c, sonnet)
- Task 8: fix round 1/5 (1 addressed, 0 open — write() now swallows every Exception, errors="replace"; commits 2d23bf0..f9c712a)
- Task 8: minor (deferred): a field keyword named event= or self= raises TypeError at call binding, before the try (no planned caller does this; positional-only params would remove it) — final review: grep EventLog.write calls
- Task 8: complete (commits 7fa8a0e..f9c712a, review clean after 1 fix round)
- Task 9: dispatched (base f9c712a, sonnet — threaded, timing-sensitive tests)
- Task 9: implementer DONE_WITH_CONCERNS (b2ffdf2, implementer a2d924c299ed6e765; concerns: process-wide redirect_stdout misrestores on overlapping logins — harmless to MCP stdio, latent for later capsys tests; comment wording; timing slack) — observations, sent to review (opus)
- Task 9: opus reviewer a7719f95e89362de1 failed twice on API timeouts (no review produced); fresh review dispatched on sonnet (a93b1f1ea63ecc00f)
- Task 9: review (a93b1f1ea63ecc00f): spec ✅, Needs fixes — 1 Important (plan-mandated): process-global contextlib.redirect_stdout mis-nests under P3's overlapping logins (stdout left on stderr, or a straggler restores a stale stdout over capsys)
- Task 9: Ruling: fix it with a compare-and-restore helper (`_stdout_to_stderr`: only undo our own change) plus one overlap regression test — Task 10 builds on this file and its insertion point in _login is unaffected, and P3 makes overlap routine (expiry re-logins make it more common); no protocol impact either way, since the stdio transport writes through its own fd — cost if wrong: ~12 extra lines; the suite count offset becomes +3 (106→109, 107→110, 111→114, 114→117).
- Task 9: minor (deferred): get() docstring "at most one login at a time" and the comment "a newer login already won" are inaccurate under P3
- Task 9: minor (deferred): test_concurrent_first_calls_log_in_once doesn't assert len(got) == 5, so a raising worker passes
- Task 9: minor (deferred): no test for the late-older-login wake-up path, the spare-connection close, or the login_timeout/login_failed events
- Task 9: ⚠️ resolved by plan — stdio cleanliness with a printing connector is Task 13's test (NoisyConnector prints and writes raw fd 1); status during a pending login is Task 11's test
- Task 9: fix round 1/5 dispatched (resume a2d924c299ed6e765; FIX_BASE b2ffdf2)
- Task 9: fix round 1 committed (81e96cc; new test fails on old code 10/10, 10 passed ×3, suite 75); scoped re-review dispatched (a1d85250f601fee41, sonnet)
- Task 9: fix round 1/5 (1 addressed, 0 open — compare-and-restore stdout helper + overlap test; commits b2ffdf2..81e96cc)
- Task 9: complete (commits f9c712a..81e96cc, review clean after 1 fix round)
- Task 10: dispatched (base 81e96cc, haiku)
- Task 10: implementer DONE (a58a0d6, implementer ab7a452459bf0fff2; 25 in file, suite 90); review dispatched
- Task 10: minor (deferred): P5 relies on the connector's private `_reauthenticate`; the override assignment sits outside the try (a rejecting connector would kill the login thread → 120 s LOGIN_TIMEOUT); optional canary test hasattr(SnowflakeConnection, "_reauthenticate")
- Task 10: minor (deferred): discard() doesn't close the dead connection (its heartbeat thread lingers until exit; harmless under the override)
- Task 10: minor (deferred): _EXPIRED_ERRNOS = {250002, 390112, 390114}; the connector's re-auth family also has 390113, 390115 (covered via the override for externalbrowser)
- Task 10: minor (deferred): untested — discard's `is conn` guard, the "due to a timeout" message fallback, a lazy-import guard (subprocess)
- Task 10: minor (deferred): task-10 report says "24 new tests" (it's 5 functions / 15 items)
- Task 10: ⚠️ carried to Task 12's review — run_query must classify every failure and discard(conn) on LOGIN_EXPIRED; ⚠️ resolved — check_notes.py (Task 14) goes through LazyConnection(default_connect), so it gets the override too; the live expiry check is Task 35 Step 3
- Task 10: complete (commits 81e96cc..a58a0d6, review clean)
- Task 11: dispatched (base a58a0d6, haiku)
- Task 11: implementer DONE (6c0842b, implementer a7e69a0c7f2880d45; suite 96); review dispatched
- Task 11: minor (deferred): the default --runs-dir (REPO/"runs" regardless of launch folder) is untested; `default=Path("runs")` would pass every test
- Task 11: minor (deferred): test_main_logs_server_start_without_logging_in leaves default_connect unpatched — a regression that logs in from main() would open a real Okta tab (after Task 22) instead of failing fast; --runs-dir reaching build_server is untested
- Task 11: minor (deferred): status() lets unlearned_folders errors escape (learned.txt as a directory, invalid UTF-8, unreadable day folder) → bare "Error executing tool status"
- Task 11: minor (deferred): test_status_during_a_pending_login syncs with sleep(0.05); make()'s login_timeout param unused by Task 11's tests
- Task 11: ⚠️ resolved by plan order — SKILL.md and updater.md (Tasks 19–20) exist before registration (Task 23)
- Task 11: complete (commits a58a0d6..6c0842b, review clean)
- Task 12: first dispatch (sonnet) rejected by the user before it ran; user said "Continue"; re-dispatched (base 6c0842b, haiku — complete code; scope passes the user's sizing rule: one change, 2 files)
- Task 12: implementer DONE (40d41ba, implementer a998aa14d3bca4f60; suite 109); review dispatched
- Task 12: review (a9d818835fa9ebc74): spec ❌, Needs fixes — 2 Important (plan-mandated): (1) a non-Blocked exception from check_sql (RecursionError, e.g. the typo `DESC.RIBE TABLE db.sch.t`) escapes as a bare "Error executing tool" with no code, SQL path or query_failed line; (2) no test covers "a failed query deletes its partial CSV" (the fake raises before write_csv opens the file)
- Task 12: Ruling: fix both — add `except Exception` after `except Blocked` in run_query, raising fail("INTERNAL_ERROR", "<Type>: <msg>"), plus a test with the `DESC.RIBE` typo; and add a mid-stream-failure test (rows generator yields then raises) asserting the code, the .sql, and no .csv — spec §5.5/§5.1 promise a code and a log line for every failed call and "only successful queries produce a CSV"; the plan's structure leaves both unguarded — cost if wrong: none; suite offset becomes +5 (plan 107→112, 111→116, 114→119).
- Task 12: Ruling: the server-level catch-all reports INTERNAL_ERROR rather than changing guard.py to raise Blocked on RecursionError — it guarantees a code for anything the guard raises and stays inside Task 12's file; the more precise guard-level fix stays a deferred Task 3 minor for the final review — cost if wrong: a deeply nested typo reads as INTERNAL_ERROR instead of BLOCKED; Claude still sees the message and fixes the SQL.
- Task 12: minor (deferred): P2 (SQL sent unchanged) unprotected — `SELECT 1 AS n` round-trips through sqlglot identically
- Task 12: minor (deferred): the CSV: line of the result text isn't asserted in server tests
- Task 12: minor (deferred): the query_failed log line is untested; the save-failure branch raises without any log line
- Task 12: minor (deferred): `Seconds:` and query_finished `seconds=` include the Okta login wait on a window's first query
- Task 12: ⚠️ carried to the live tasks (27–28) — the real connector's execute timeout errnos, cursor.description shape and expiry via the patched _reauthenticate are only exercised by fakes
- Task 12: fix round 1/5 dispatched (resume a998aa14d3bca4f60; FIX_BASE 40d41ba)
- Task 12: fix round 1 committed (f4a8440; failing-then-passing evidence for both tests; 21 in file, suite 111); scoped re-review dispatched (af26ab39a326c8a2e, haiku)
- Task 12: fix round 1/5 (2 addressed, 0 open — guard crashes get INTERNAL_ERROR; mid-stream CSV cleanup tested; commits 40d41ba..f4a8440)
- Task 12: complete (commits 6c0842b..f4a8440, review clean after 1 fix round)
- Task 13: dispatched (base f4a8440, haiku)
- Task 13: implementer DONE (0c95c8b, implementer a6d2af49220ed5524; suite 112); review dispatched
- Task 13: review (aaa8f720bb50f292a): spec ✅, Approved with 1 Important (plan-mandated): the stdio test can't fail when login noise reaches the protocol stream — the Client's default message handler silently swallows junk lines (reviewer proved it by defeating the fd-1 diversion: the test still passed)
- Task 13: Ruling: fix it — record what the client's message_handler receives and assert no Exception arrived; spec §10.1 "Clean output" is binding and this is its only offline check; test-only, count unchanged — cost if wrong: none.
- Task 13: minor (deferred): `startswith("Logged in as JKARNIK")` can't tell the fake from a real session; if the default_connect rebinding ever broke, this "offline" test would open a real Okta login (after Task 22) — a `fake-query-` Query ID assertion would at least detect it
- Task 13: minor (deferred): no timeout around the stdio session (anyio.fail_after) — a server deadlock would hang the suite
- Task 13: minor (deferred): the log glob picks one file arbitrarily (midnight split, StopIteration on empty)
- Task 13: fix round 1/5 dispatched (resume a6d2af49220ed5524; FIX_BASE 0c95c8b)
- Task 13: fix round 1 committed (8118562; scratch run with diversion defeated fails on Invalid JSON; real test passes; suite 112); scoped re-review dispatched (aa8d8ae62056eb43e, haiku)
- Task 13: fix round 1/5 (1 addressed, 0 open — the stdio test now fails if junk reaches the protocol; commits 0c95c8b..8118562)
- Task 13: complete (commits f4a8440..8118562, review clean after 1 fix round)
- Task 14: dispatched (base 8118562, haiku)
- Task 14: implementer DONE (b4107fc, implementer ae5a3434bac546bfd; suite 116); review dispatched
- Task 14: review (ad983108aa7390004): spec ✅, Needs fixes — 1 Important (plan-mandated): `message.splitlines()[0]` drops the cause of Snowflake compile errors (line 2: "Object 'X' does not exist…"), the only diagnostic Task 28's live run gives
- Task 14: Ruling: fix it — print the whole message on one line (`" ".join(message.split())`) plus an offline regression test (monkeypatched default_connect with a failing fake connection); spec §10.2's live check exists to find and fix failing notes, and each live run costs an Okta login; value scrubbing skipped (line 1 could echo values before too) — cost if wrong: none; suite offset becomes +6 (plan 114→120).
- Task 14: Ruling: handle the cheap Task-28-relevant minors at dispatch instead of in code — Task 28 runs check_notes with `python -u` (no block buffering through tee) — cost if wrong: none.
- Task 14: minor (deferred): the first PASS time includes the Okta login wait (started is set before lazy.get())
- Task 14: minor (deferred): fences the regex misses (indented, ~~~sql, ```SQL, info strings, unterminated) are skipped silently — a DELETE there passes
- Task 14: minor (deferred): zero blocks checked still prints "0 failed" and exits 0
- Task 14: minor (deferred): no line buffering (output lost if killed mid-run when piped)
- Task 14: minor (deferred): --dry-run still parses --values; a malformed values.toml crashes with a traceback
- Task 14: minor (deferred): `except KeyError` wraps guard/login/execute, so a stray KeyError reads as "missing values"
- Task 14: minor (deferred): the live branch has no tests (beyond the fix round's error-message test)
- Task 14: minor (deferred): task-14 report line counts and "comprehensive" claim overstate
- Task 14: ⚠️ resolved by plan — P10 "every name defined" is enforced by Task 27's write_values (all keys or none) and its values check; a placeholder typo surfaces in Task 28's live run. ⚠️ noted — run_eval.py (Task 21) re-declares PLACEHOLDER (already ruled R13)
- Task 14: fix round 1/5 dispatched (resume ae5a3434bac546bfd; FIX_BASE b4107fc)
- Task 14: fix round 1 committed (e1ffba8; failing-then-passing evidence; 5 in file, suite 117); scoped re-review dispatched (a8a5d2b2c25e62f54, haiku)
- Task 14: fix round 1/5 (1 addressed, 0 open — whole error message on one FAIL line; commits b4107fc..e1ffba8)
- Task 14: complete (commits 8118562..e1ffba8, review clean after 1 fix round)
- Task 15: dispatched (base e1ffba8, haiku)
- Task 15: implementer DONE (8bfdd70, implementer a4d4a4712c23f9455); review dispatched
- Task 15: minor (deferred): two recipes lack a `Use for:` line ("List a database's schemas", "Look at one table"), unlike updater.md's entry format
- Task 15: minor (deferred, watch in evals): `LOWER(col) LIKE '%{{search_term}}%'` misses an uppercase term (false "no such table"); ILIKE would remove the dependency
- Task 15: minor (deferred): "views are most of CONFORMED and REPORTING" overreaches (REPORTING_LOOKER_PDT objects are tables); RAW has no _STAGING/_DEV copies
- Task 15: ⚠️ carried to Task 28 — INFORMATION_SCHEMA recipes may hit "too much data" on REPORTING/CONFORMED (add a TABLE_SCHEMA filter if so); values.toml's search_term ("ingest") is lowercase ✓. ⚠️ carried to Task 19's review — updater.md's entry format vs multi-block recipes
- Task 15: complete (commits e1ffba8..8bfdd70, review clean)
- Task 16: dispatched (base 8bfdd70, haiku)
- Task 16: implementer DONE (8ba4ae5, implementer ab4b56ff0113a72f7); review dispatched
- Task 16: ⚠️ carried to Task 28's checklist — (a) DESCRIBE ALL_DAILY_USAGE for a data-centre column, else drop the US-over-EU pitfall; (b) if it exists, confirm its values sort with US first under ASC (text "EU" < "US"), else use the order that keeps US; (c) fold it into recipe 1's ORDER BY and fix "Applies the de-duplication rule"; also confirm the INSERTED_AT DESC direction if duplicates differ
- Task 16: minor (deferred): "today's rows may be missing until after 2 am PST" is a loose inference not in the source
- Task 16: minor (deferred): cross-reference quotes "Find tables" (heading is "Find tables by name"), and that recipe needs a {{database}} the note doesn't name
- Task 16: minor (deferred): `COUNT(*) AS DAY_ROWS` counts repeated inserts and reads like a day count (COUNT(DISTINCT START_TIME) would be dedup-safe)
- Task 16: minor (deferred): table list omits DAILY_AGGREGATION_PROD
- Task 16: complete (commits 8bfdd70..8ba4ae5, review clean)
- Task 17: dispatched (base 8ba4ae5, haiku)
- Task 17: implementer DONE (bac5eb4, implementer a5c3272fe2c96acb6); review dispatched
- Task 17: ⚠️ carried to Task 28 — the Critical CONCAT_WS pitfall rests on weak evidence; Task 28's probe item 1 decides it (also the "empty parts are skipped" wording). ⚠️ resolved — the npm.md forward reference is Task 18; the CC-/org-name/NR-internal-org pitfalls come from the plan's Verified Facts (parallel-session memories)
- Task 17: minor (deferred): owner recipe uses MAX() per role — two AEs/TSMs collapse to one, and name/email can come from different people
- Task 17: minor (deferred): a CRLF street break becomes two spaces
- Task 17: minor (deferred): the address recipe takes one {{company_name}} (E5 names two); an apostrophe in a typed name needs doubling
- Task 17: minor (deferred): the source's R.ACCOUNT_NAME column was dropped (harmless)
- Task 17: complete (commits 8ba4ae5..bac5eb4, review clean)
- Task 18: dispatched (base bac5eb4, haiku)
- Task 18: implementer DONE (9aa42f6, implementer aed8c8ac5ce27aa4d); review dispatched
- Task 18: ⚠️ carried to Task 28's probe window — (a) is II's `INSTRUMENTATION_NAME = 'juniper-mist'` outside `USAGE_CATEGORY = 'NetworkMonitoring'`? (the "NPM counts exclude Mist" caveat at npm.md:95 assumes so for II too); (b) is ELIA one row per entity per day (COUNT(*) vs COUNT(DISTINCT ENTITY_GUID) on one day)? (npm.md:10); partial-days pitfall unverified, low stakes
- Task 18: minor (deferred): Recipe 2 (per-day trend) has no inline cost cue for long ELIA ranges
- Task 18: minor (deferred): Recipe 4 "Top accounts" groups by SUBSCRIPTION_ACCOUNT_ID (= "clients" per the note); II's account column (SUB_ACCOUNT_ID?) isn't mapped
- Task 18: minor (deferred): the blank-METRIC sentence lacks a rule (recipes' METRIC filter drops those rows)
- Task 18: minor (deferred): INFRA-JUNIPER_MIST_SWITCH is an example DOMAIN_TYPE that the NPM filter can never return
- Task 18: complete (commits bac5eb4..9aa42f6, review clean)
- Task 19: dispatched (base 9aa42f6, haiku)
- Task 19: implementer DONE (6b80265, implementer a661de1d6065735c6); review dispatched
- Task 19: minor (deferred, flag for final review): updater.md "drop any recipe that fails" treats LOGIN_TIMEOUT/LOGIN_EXPIRED/TIMEOUT like a bad recipe, and step 7 still marks the folder learned — a login hiccup during /snowflake learn silently and permanently loses that run's learnings
- Task 19: minor (deferred): placement under-specified (format block shows a pitfall under a recipe, notes keep `## Pitfalls`; no section named for definitions; "None yet." not removed on first table entry)
- Task 19: minor (deferred): wording — missing learned.txt counts as empty; stray period after `Critical.`; "fix or remove a recipe that stops working" vs never pruning Critical
- Task 19: ⚠️ resolved — formats accommodate finding-data.md's multi-block and no-`Use for:` recipes (step 5 only touches `Last used:`); ⚠️ carried to Task 20's review — SKILL.md must have summary.md list the recipes and table entries used
- Task 19: complete (commits 9aa42f6..6b80265, review clean)
- Task 20: Ruling: commit the `git mv` as its own pure-rename commit before rewriting the content (the plan does both in one commit) — the plan's stated purpose is "so history follows", and git links a rename only by content similarity, which a full rewrite destroys — cost if wrong: one extra commit.
- Task 20: dispatched (base 6b80265, haiku)
- Task 20: implementer DONE (d821dc1 rename + 3dc0fa9 rewrite, implementer af7795a173f77f5a5); review dispatched
- Task 20: minor (deferred): SKILL.md "Customer names and IDs stay in runs/" is narrower than "Customer data appears only in runs/" (a customer-tied number without a name passes); updater.md already bars results and numbers
- Task 20: ⚠️ carried to Tasks 23 and 29–30 — Claude Code accepting list-form allowed-tools with ~ paths; check-in and trigger wording. ⚠️ resolved by plan — CLAUDE.md (deleted in Task 25) and README.md (rewritten in Task 26) still link to Snowflake.md
- Task 20: complete (commits 6b80265..3dc0fa9, review clean; history follows via the separate rename commit)
- Task 21: dispatched (base 3dc0fa9, haiku)
- Task 21: implementer DONE (5cc09fc, implementer ac6fdaee7b8385e01; suite 120); review dispatched
- Task 21: review (a006bd17cdab011b7): spec ✅, Needs fixes — 1 Important (plan-mandated): run_eval.py can't tell a dead window from a quiet one (returncode unread, no result-event check, always exits 0; TimeoutExpired loses all output), so a crashed window writes all-zero facts that pass E9/E10 ("skill didn't trigger") and flatter the baseline
- Task 21: Ruling: fix it before the paid, login-gated evals — facts() gains result_seen (existing facts test's expected dict updated), main() records exit_code, prints a WARNING and returns 1 when exit_code != 0 or no result event, and catches TimeoutExpired saving its (bytes) stdout/stderr; plus one test that facts([]) reports result_seen False — spec §10.4/§10.6 grading depends on telling a failed window from a non-trigger — cost if wrong: none; suite offset becomes +7 (plan 114→121).
- Task 21: minor (deferred): repo_changes_outside_runs compares porcelain lines, not content (an already-dirty file edited by an eval goes unseen)
- Task 21: minor (deferred): the mode→flags mapping (P11) is untested; facts() tested on the happy path only
- Task 21: minor (deferred): nits — <2 args gives an unpack error; a malformed `{` line raises before facts.json is written; text=True/read_text() without encoding="utf-8"
- Task 21: minor (deferred): task-21 report's line counts are wrong
- Task 21: ⚠️ carried to Task 29 — the Skill tool_use shape (input.skill == "snowflake") and headless honoring of SKILL.md allowed-tools are live-only; eval windows also start the user's atlassian MCP server (currently timing out at 30 s), same for both arms. ⚠️ resolved by plan — registration and link happen in Task 23, before Tasks 29–30
- Task 21: fix round 1/5 dispatched (resume ac6fdaee7b8385e01; FIX_BASE 5cc09fc)
- Task 21: fix round 1 committed (fb0063f; RED 2 failed, GREEN 4 in file, suite 121); scoped re-review dispatched (a91f4ffee92072d6c, sonnet)
- Task 21: fix round 1/5 (1 addressed, 0 open — result_seen/exit_code/WARNING/return 1, timeout output kept; commits 5cc09fc..fb0063f)
- Task 21: minor (deferred): json.loads on a cut final line (timeout/kill mid-write) raises before answer.md/facts.json are written (loud, transcript kept)
- Task 21: ⚠️ carried to Tasks 29–30 dispatches — a `WARNING:` line, result_seen false or exit_code ≠ 0 means re-run that window and don't grade it (a dead window otherwise still "passes" E9/E10); before any same-day re-run, move the old runs/evals/<date>/<id>-<mode>/ folder aside so stale facts.json/answer.md can't mix in
- Task 21: complete (commits 3dc0fa9..fb0063f, review clean after 1 fix round)
- Task 22: dispatched (no base commit — writes ~/.snowflake/connections.toml outside the repo, R10; haiku)
- Task 22: implementer DONE (ae32cab4a9147e7d5; ~/.snowflake/connections.toml written, mode 600, CONFIG_MANAGER read OK, no repo change); state-check review dispatched (a1e52ae5d0c329596, haiku)
- Task 22: complete (outside repo, no commit; state-check review clean)
- Task 23: dispatched (base fb0063f, haiku)
- Task 23: implementer DONE (5cbd135, implementer ae340e892cd15b5de; 5/5 PASS, symlink works, no fallback); user told open windows need a restart; review dispatched
- Task 23: minor (deferred): check_install.py doesn't diagnose a dead/slow window (TimeoutExpired traceback; no init event → five FAILs that read like an install problem)
- Task 23: minor (deferred): exact-dict match on the mcp_servers entry breaks if Claude Code adds a field
- Task 23: minor (deferred): the log window is shared across windows (another window's login during the ~8 s run would flip "no login")
- Task 23: complete (commits fb0063f..5cbd135, review clean; registration absolute-path, env-free; symlink loads; no fallback)
- Task 24: dispatched (base 5cbd135, haiku)
- Task 24: implementer BLOCKED (a811fc1120032f87f) — plan defect: Account_owner.sql is TRACKED (committed in ddcb2af "Plan Done", which is on origin/snowflake-skill), not untracked as the plan says; after the move git shows ` D Account_owner.sql`; the implementer's `git rm --cached Account_owner.sql` was denied by the harness. All four files are safe in runs/originals/ (sizes match; fingerprints SAME per report). Asking the user: (1) untrack Account_owner.sql in Task 24's commit; (2) what to do about the copy in pushed history.
- Task 24: user decisions (2026-10-01): (1) stop tracking Account_owner.sql — approved; (2) the copy in pushed history (ddcb2af on origin/snowflake-skill) — leave history as is
- Task 24: Ruling: the controller ran the user-approved `git rm --cached Account_owner.sql` and the Task 24 commit itself instead of resuming the implementer — the harness had denied that command to the subagent, and the subagent can't carry the user's approval; a reviewer still checks the result — cost if wrong: none; the commit only records two deletions.
- Task 24: committed 74e08c3 (controller, user-approved; SAME + IGNORED); metadata-only state review dispatched (ad6641d7bc778d02f, haiku) — the full diff would expose customer names
- Task 24: complete (commits 5cbd135..74e08c3, state review clean)
- Task 25: dispatched (base 74e08c3, haiku; carries R3 /runs/)
- Task 25: implementer DONE (c18090e, implementer a615a3bd2ae2ed516; suite 121; /runs/ anchored, fixtures not ignored); review dispatched
- Task 25: ⚠️ resolved — the controller ran pgrep before dispatch (none running)
- Task 25: complete (commits 74e08c3..c18090e, review clean)
- Task 26: dispatched (base c18090e, haiku; copy fallback was not used in Task 23)
- Task 26: implementer DONE (d875045, implementer a764fcac1c70a1d99); review dispatched
- Task 26: minor (deferred): install steps don't say "run from the repo folder" ($PWD paths register wrongly elsewhere)
- Task 26: minor (deferred): fresh-machine prerequisites missing (mkdir -p ~/.snowflake, chmod 600, ~/.claude/skills, creating .venv)
- Task 26: minor (deferred, fix in final wave): README says the live checks "read" runs/evals/values.toml, but live_login_check.py (Task 27) creates it and should be listed first
- Task 26: ⚠️ carried to Task 27 (R6) — re-run the README existence loop with tests/live_login_check.py added
- Task 26: complete (commits c18090e..d875045, review clean)
- Task 31: dispatched (base d875045, haiku; runs before Task 27 per R8)
- Task 31: implementer DONE (0d20007, implementer ab4251d9ccec95514; 15 files committed, suite 121); review dispatched
- Task 31: ⚠️ carried to Task 32's grading — (a) expected.md item 2 also passes if customers.md already states the SFDC_ACCOUNT_NAME column and the updater reports it covered (avoid a needless login-costing fix loop); (b) item 1 also passes with an extra II table entry; (c) add `grep -c CANARY-ROW-DATA-7Q "$T/pass1.jsonl"` = 0 so a CSV open is caught, not just a leak. ⚠️ carried to Task 28's probe window — DESCRIBE TABLE TRANSFORMED.SALES.SFDC_ACCOUNT_D to confirm it has no NAME column (fixture premise)
- Task 31: minor (deferred): whoami/summary.md lacks "How I got this" (harmless one-off)
- Task 31: complete (commits d875045..0d20007, review clean)
- LIVE phase begins: Tasks 27, 28, 29, 30, 32, 33, 34 open Okta logins; stopping before Task 27 for the user's go-ahead (R9)
- Task 27: user go-ahead received (Task 27 only, 1 login); dispatched (base 0d20007, implementer aef43483cb0e8266f, sonnet)
- Task 27: run 1 (commit 635e208 adds the script, verbatim): PASS window A no login, PASS window B logged in exactly once, PASS three queries; FAIL values (missing npm_account_id — the yesterday ELIA query returned 0 rows), so values.toml holds only company_a/b/c and the 8 dependent keys were skipped; README recheck clean; suite 121. 1 login used.
- Task 27: Ruling: take the plan's documented fallback — change `-1` to `-2` in the npm-account query, commit that one-line change, and re-run once (one more login) after the user's OK; don't query MAX(USAGE_DATE) instead, since ELIA has no clustering key and that scan would be slow — cost if wrong: if ELIA also lacks the day before yesterday, one more login.
- User (2026-10-01) asked why so many logins (explained: ALLOW_ID_TOKEN=false → one login per new connection/window; tests open fresh windows); chose "Full tests, stop before each task" — ask for an OK before every live task or re-run
- Task 27: user approved the re-run (1 login); implementer resumed with the -1 → -2 change
- Task 27: re-run (9b1b39e: -1 → -2): all five PASS (A no login; B exactly one login; three queries; values.toml has all 12 P10 keys); 2 logins used in total for Task 27; suite 121
- Task 27: ⚠️ carried to Task 29 — ELIA had no NetworkMonitoring rows for yesterday (load lag?), so E1 ("yesterday") may return zero rows; grade "Must" on the SQL shape, and note whether the skill flagged the empty/partial day
- Task 27: review dispatched (no live re-runs allowed)
- Task 27: review (af2b11d82b99a2bd5): spec ✅, Needs fixes — 1 Important (plan-mandated): live_login_check.py groups events by pid and then flattens them, so counts are per time slice, not per window (another window's login/query inside a slice can flip a check, including a false PASS)
- Task 27: Ruling: defer that fix to the final-review fix wave (offline, no login) instead of fixing now — the recorded results were verified per pid by the reviewer (only the script's own pids appear in both slices), no later task runs this script, and fixing now would hold the user at the browser between live tasks — cost if wrong: a future manual re-run of the check could misreport if another window queries Snowflake meanwhile.
- Task 27: minor (deferred): values.toml is hand-written TOML, never read back (control characters or raw ids could break it; a failed run overwrites a good file)
- Task 27: minor (deferred): window() drops return codes and stderr; TimeoutExpired escapes; one log read lacks an exists() guard
- Task 27: minor (deferred): "newest CSV wins" can mask a step window B skipped (only query_finished == 3 guards it)
- Task 27: minor (deferred): the NPM day uses Snowflake CURRENT_DATE()-2 while start_date uses the local date-2 (two clocks)
- Task 27: minor (deferred): no offline tests for events_by_pid/first_column/write_values/repr_toml
- Task 27: complete (commits 0d20007..9b1b39e; 2 logins used; 1 Important deferred to the final wave by ruling)
- Task 28: Ruling: the probe window uses start_date (two days ago) wherever the plan's template says <end_date>, and adds cheap probes carried from earlier reviews — data-centre column sort order (Task 16), II juniper-mist USAGE_CATEGORY (Task 18), ELIA rows vs devices on one day (Task 18), DESCRIBE SFDC_ACCOUNT_D (Task 31) — yesterday had no NPM rows, and the extra probes ride on the same login — cost if wrong: a few seconds of extra query time.
- Task 28: user go-ahead (up to 3 logins); dispatched (base 9b1b39e, implementer aed68c25b1a2115c5, sonnet)
- Task 28: implementer DONE_WITH_CONCERNS (6c48117; 3 of 3 logins; check 1: 18 PASS + 1 FAIL customers.md:58 text-vs-number; re-check: 19 PASS, 0 failed; suite 121). Probes: CONCAT_WS NULL wins (pitfall stays); RPM join covers 99.93% (stays; new type-mismatch pitfall added); no data-centre column (US-over-EU pitfall deleted); Mist in II is CustomEvents/Metrics (stays); ELIA rows > distinct GUIDs (grain reworded); SFDC_ACCOUNT_D has no NAME (fixture premise holds). Concern: customers.md says NPM SUBSCRIPTION_ACCOUNT_ID carries the RPM ID, npm.md says it is the CC- contract. Review dispatched.
- Task 28: review (a9968ffbf1ca54ab4): Needs fixes — 1 Important (plan-mandated, pre-existing): customers.md:8-9 calls NPM `SUBSCRIPTION_ACCOUNT_ID` an RPM-ID column, contradicting npm.md, customers.md:101 and the Verified Facts (it is the CC- contract); a session joining it to RPM_ACCOUNT_ID would silently get zero rows
- Task 28: Ruling: fix it offline before the evals — rewrite customers.md:8-9 so `ALL_DAILY_USAGE` uses `BILLABLE_RPM_ACCOUNT_ID`, the NPM tables use `ACCOUNT_ID`, and `SUBSCRIPTION_ACCOUNT_ID` is the contract that must never be joined to RPM_ACCOUNT_ID; the edit is prose outside any sql fence, so no login is needed — spec §6.2 requires the RPM join "confirmed in the knowledge checks", and only BILLABLE_RPM_ACCOUNT_ID was — cost if wrong: if ELIA's ACCOUNT_ID were not an RPM ID either, the note would still overstate one join (unprobed; npm.md and the Meraki memory support it).
- Task 28: deviation recorded (reviewer minor 3): the spec's "US over EU" billing rule (spec §6.2, plan Task 16) was dropped live — ALL_DAILY_USAGE has no data-centre column (8 columns), per spec §11 "fixed or dropped"
- Task 28: minor (deferred): customers.md step 1 could say RPM_ACCOUNT_ID is text (the cast caveat lives only in the new pitfall)
- Task 28: minor (deferred): the new pitfall's title says "numbers in usage" but only BILLABLE_RPM_ACCOUNT_ID was probed
- Task 28: ⚠️ unverified — ELIA ACCOUNT_ID / II SUB_ACCOUNT_ID join to RPM_ACCOUNT_ID (no probe); a later live window could bundle a one-day join check
- Task 28: fix round 1/5 dispatched (resume aed68c25b1a2115c5; FIX_BASE 6c48117; offline only)
- Task 28: fix round 1 committed (6b3d55f; prose-only; dry-run 19 PASS; 0 logins); scoped re-review dispatched
- Task 28: fix round 1/5 (1 addressed, 0 open — RPM-ID column prose; commits 6c48117..6b3d55f)
- Task 28: complete (commits 9b1b39e..6b3d55f, review clean after 1 fix round; 3 logins)
- Task 29: user go-ahead (up to 10 windows + 3 re-runs = 13 logins); dispatched (base 6b3d55f, implementer ae35c1f3e3eaf8799, sonnet)
- Task 29: implementer DONE_WITH_CONCERNS (013af73: SKILL.md step 7 — SQL in a code block; 11 windows, 10 of 13 logins, 1 of 3 re-runs). Skill: E1 PASS after fix, E2–E5 PASS. Baseline: E1/E2/E5 FAIL (wrong tables, no cleanup); E3/E4 "Must met" but contaminated — the baseline read the skill's notes from the repo with Read/Grep/Bash after status printed the repo path. Skill tool_use shape matches facts(). No permission denials.
- Task 29: Ruling: fix run_eval.py's baseline mode to deny local file tools (Read, Grep, Glob, Bash) and re-run only the E3 and E4 baselines (2 re-runs, ≤2 logins, inside the user's approval) — P11 says the baseline exists to "measure what the skill adds", and reading the skill's own notes defeats that; touching Task 21's runner is outside Task 29's file list but needed for a valid §10.6 comparison in Tasks 29–30 — cost if wrong: the baseline is weaker than "plain Claude with file tools", which is fair for data questions where the only local files are the skill's notes.
- Task 29: minor (deferred, final wave): the skill suggested /snowflake learn at 3 unlearned folders (rule says 5 or more)
- Task 29: minor (deferred, final wave): in E3 the skill said the login "has expired" when it had never logged in
- Task 29: note for the user — each Okta tab must be completed within 2 minutes (one timed out)
- Task 29: follow-up dispatched (resume ae35c1f3e3eaf8799): baseline denies Read/Grep/Glob/Bash via build_command + test; re-run E3 and E4 baselines (≤2 logins, the last 2 approved re-runs)
- Task 29: follow-up done (dabea77: baseline denies Read/Grep/Glob/Bash via build_command + 1 test; suite 122). Clean re-runs (2 logins): E3 baseline FAIL (no check-in; ran 16 queries, picked its own definition), E4 baseline FAIL (different path; 2 of 4 checks). Task 29 total: 12 of 13 logins, 3 of 3 re-runs. Skill beats baseline on Must for E1–E5; on check counts E3 ties 2–2 (a check-in has no query/result for checks 1 and 3).
- Task 29: Ruling: extend the baseline deny list to every tool that can reach local files or spawn work (Monitor, Task/Agent, Workflow, Write, Edit, NotebookEdit, plus the existing four) before Task 30 — offline, no login; P11's intent again — cost if wrong: none for data-question baselines.
- Task 29: Ruling (for Task 30's §10.6 verdict): on check-in prompts (E3, E7) compare on "Must" plus the applicable checks, since a correct check-in can't satisfy "saves queries/CSVs" or the answer-order check — cost if wrong: the E3 tie on raw check counts would read as a §10.6 failure.
- Task 29: deny-list follow-up — original implementer hit an API timeout before changing anything (tree clean); fresh haiku implementer a39b381876c66f30e dispatched with the exact tool names from a baseline init event (Read, Grep, Glob, Bash, Monitor, Task, Workflow, Write, Edit, NotebookEdit)
- Task 29: deny-list follow-up done (429e078: baseline also denies Monitor, Task, Workflow, Write, Edit, NotebookEdit; suite 122 passing; 0 logins). Recorded in a later session — the implementer committed but the ledger wasn't updated.
- Task 29: review dispatched (a3f413a32a538fe0b, sonnet; package review-6b3d55f..429e078.diff) — stopped when the session closed; resumed
- Task 29: resumed review failed (API 400 on resume); fresh reviewer a7ac4cfd91f5a265f dispatched (sonnet, same prompt)
- Task 30: Ruling: runs land in runs/evals/2026-10-09/ (the runner uses today's date) but grades append to runs/evals/2026-10-01/grades.md with a note naming the 2026-10-09 run folders — the brief says "grade into the same grades.md" and §10.6 compares across all ten — cost if wrong: one grades file sits in an older date folder than half its runs; moving it is trivial.
- Task 30: Ruling: login budget is the plan's 6 for the ten windows plus up to 3 re-runs (9 in all), mirroring Task 29's approved re-run allowance; the user is told the count before the run starts (Step 4's "tell the user first") — cost if wrong: up to 3 extra Okta tabs the user has to complete.
- Task 29: review (a7ac4cfd91f5a265f): spec ✅, Needs fixes — 1 Important (partly plan-mandated: P18's `--model sonnet` alias): the E1/E2 baseline-vs-skill pairs and the step-7 "fix works" claim straddle an unnoticed Sonnet 4.6 → 5.5 and CLI 2.1.153 → 2.1.285 switch (between the E2 baseline and E2 skill windows); facts() records neither model nor CLI version, and grades.md never mentions it
- Task 29: ⚠️ (1) resolved from this ledger — go-ahead for 13 logins recorded, all 3 re-runs inside it (12 of 13 used); ⚠️ (2) the 10-name deny list never ran in a live window — folded into fix round 1's E2 baseline re-run (check its init tool list)
- Task 29: Ruling: keep P18's `--model sonnet` alias and fix the finding by recording `model` and `claude_code_version` from the init event in facts(), noting each grades.md row's conditions (model, CLI, baseline deny list), softening the "fix works" and comparison claims, and re-running the E2 baseline once (the 13th approved login) so every E1–E5 pair has a same-model comparison — the spec is silent on pinning and P18 chose the alias; recording turns future drift into a visible pair mismatch — cost if wrong: if the alias moves again mid-Task 30, one pair needs a re-run login.
- Task 29: minor (deferred): run_eval.py:7-8 docstring still says baseline denies 4 tools; Artifact, CronCreate, ScheduleWakeup, EnterWorktree, SendMessage still offered to baselines (none called)
- Task 29: minor (deferred): build_command fails open — any mode other than "baseline" gets the unrestricted command (main() guards it today)
- Task 29: minor (deferred): test_run_eval.py:52 restates the 10-name list literally; test name claims "cannot read local files", which an argv test can't show
- Task 29: minor (deferred): a deny list drifts with the CLI's tool set; `--tools` (built-in allowlist) may be sturdier; init tool list isn't authoritative (Grep callable in E4 try 1 but absent from its init list)
- Task 29: minor (deferred, carried to Task 30): grades.md legend defines n/a as "folder convention only" but n/a is also used for check-ins
- Task 29: minor (deferred, carried to Task 30): checks 1 and 3 are the skill's own conventions, so a baseline scores at most 2 of 4 by construction; only the Must discriminates, and the E4 Must is path-specific
- Task 29: minor (deferred, carried to Task 30): the /snowflake learn suggestion at 3 unlearned folders and the "login has expired" slip look like model non-compliance, not wording gaps
- Task 29: minor (deferred, carried to Task 30): question folders were moved by hand into <id>/question-folders/, so transcripts' SQL: paths are stale; find a run's folder by diffing runs/<date>/ before and after, not by moving folders
- Task 29: fix round 1/5 dispatched (fresh implementer ab3018931bf3e57f9, sonnet — resuming prior-session agents fails with API 400; FIX_BASE 429e078; findings task-29-fix1-findings.md; 1 live window: E2 baseline re-run)
- Task 29: fix round 1 implementer DONE_WITH_CONCERNS (6722d42: facts() records model + claude_code_version, 2 tests; suite 124). E2 baseline re-run (runs/evals/2026-10-09/E2-baseline/, 1 login, valid): Must no, same model as E2 skill (sonnet-5-5, CLI 2.1.285); deny list held — none of the 10 in init tools, one Grep and one Glob attempt refused by the harness, nothing read, 0 denials. grades.md: 13 rows annotated, claims softened, same-model table: baseline fails Must on all five pairs, skill meets it. Task 29 logins 13 of 13. Scoped re-review next (package review-429e078..6722d42.diff).
- Task 29: fix round 1/5 (1 addressed, 0 open — model/CLI drift; commits 429e078..6722d42; re-review a5952524b650297ad: no new breakage; the two refused Grep/Glob attempts in the E2 re-run ruled as the deny list holding)
- Task 29: minor (deferred, carried to Task 30): a refused call shows as a tool_result error, not a permission_denials entry, so facts() can't show attempted-but-refused calls — graders read the transcript
- Task 29: minor (deferred): result.modelUsage lists claude-haiku-4-5 in every CLI 2.1.285 window and none of the 2.1.153 ones; facts() records only the init model (same within each same-model pair)
- Task 29: complete (commits 6b3d55f..6722d42, review clean after 1 fix round; 13 of 13 logins)
- Task 30: user go-ahead ("Ok lets continue", 2026-10-09, after the warning of up to 6 logins); the 3-re-run allowance (9 in all) was announced to the user by ruling above
- Task 30: dispatched (base 6722d42, implementer ad2667269874d6a6b, sonnet; report task-30-report.md; budget 9 logins incl. 3 re-runs)
- Task 30: implementer DONE_WITH_CONCERNS (no commits — no skill run failed; 10 windows, all valid, every pair claude-sonnet-5-5 / CLI 2.1.285; 5 of 9 logins, 0 of 3 re-runs). Must skill/baseline: E6 yes/no, E7 yes/yes, E8 yes/no, E9 yes/n/a, E10 yes/n/a. Check-ins on E3 and E7 only. Strict §10.6: FAIL on E7 alone — the baseline also checked in, so E7 ties; the skill beats its same-model baseline on the other 7 triggering prompts.
- Task 30: concern — the E8 skill window grepped its own skill folder and saw skills/snowflake/evals/evals.md (which holds the E8 expectation); it had read the answer in npm.md first, so graded met, but the sample isn't clean; evals.md inside the skill folder is readable by skill windows
- Task 30: concern — the E6 eval account has no ALL_DAILY_USAGE rows; the skill ran the required de-duplicated SQL, got none, fell back to Instrumentation Insights flagged as not billed; de-duplication never exercised on real rows (links to Task 28's unverified ELIA ACCOUNT_ID → RPM join)
- Task 30: concern — the E8 baseline took 14 minutes (every window then ran as a background call); the E8 baseline and skill windows shared one question folder
- Task 30: minor (deferred): billing.md says ALL_DAILY_USAGE has hundreds of millions of rows; the E7 baseline's metadata query shows about 1.8 billion
- Task 30: Ruling: E7 counts as a ceiling tie, not a §10.6 failure — both runs met every applicable check, so nothing was left for the skill to exceed; §10.6's "meets more of its checks" is read as strictly more wherever the baseline missed something, and equal when the baseline is already at the ceiling; resampling the baseline until it fails would be fishing — cost if wrong: the eval result overstates the pass on one prompt; the E7 rows show both runs, and a stricter E7 check would need new windows.
- Task 30: review dispatched (a6e06277febc62178, sonnet; state review — no commits, so no diff; reviews grades.md E6–E10 rows, verdict, run folders)
- Task 30: review (a6e06277febc62178): spec ✅ (given the rulings), Approved — every E6–E10 Must re-derives from the saved SQL/answers; all ten windows valid; 5 logins; no cross-credit in the shared E8 folder (baseline files 01–11, skill 12–13 + its own summary.md); reviewer agrees with the E7 ceiling-tie ruling (skill: 0 queries, 0 logins, ~24 s vs baseline 6 queries, 1 login, ~6 min). 1 Important (plan-mandated): the eval answer key ships inside the skill folder — spec §4 (line 355) and §10.4 (line 445) put evals/ under skills/snowflake/, SKILL.md lets the skill read that folder, and the E8 skill window grepped it (no grade changed: npm.md already held the answer and was read first)
- Task 30: ⚠️ resolved — (1) Step 1 go-ahead recorded above; (2) a second E7 baseline sample: not taken, per the E7 ruling (resampling until it fails is fishing); (3) why the E6 account has no ALL_DAILY_USAGE rows: unprobed, same gap as Task 28's unverified ELIA ACCOUNT_ID → RPM join, carried to the final wave; (4) whether evals.md shaped E8's wording: tool order only, the grade stands
- Task 30: Ruling: the answer-key finding is real but deferred to the final fix wave — fix there by moving skills/snowflake/evals/evals.md to tests/evals.md and updating tests/run_eval.py:20, README.md:13 and spec lines 355 and 445 — the spec's literal path yields to its own purpose for §10 (P11: measure what the skill adds), and no later task runs evals, so nothing builds on it before then — cost if wrong: if the final wave drops it, a future eval run can again read its own answer key, and day-to-day greps of the skill folder keep turning up eval prompts.
- Task 30: minor (deferred): E7 baseline check 1 is "no" though the legend makes 1 and 3 n/a on a check-in (it ran 6 metadata queries); the tie is 3 vs 3 either way
- Task 30: minor (deferred, carried to Task 35): grades.md's verdict still reads "FAIL (strict)" and says a tie fails "however the checks are counted"; Task 35 reports the ruled verdict (PASS, E7 a ceiling tie) from this ledger
- Task 30: minor (deferred): E8 skill check 3 is "yes" on order only — its code block was a suggested query with placeholders, not the SQL it ran (SKILL.md:42 says "the SQL you ran"); the weakest yes, not listed under slips
- Task 30: minor (deferred): the E7 skill answer repeated billing.md:89's stale "hundreds of millions of rows" (about 1.8 billion)
- Task 30: minor (deferred): npm_account_id is picked from ELIA (tests/live_login_check.py:35), a telemetry account, so E6 can never show de-duplication on real rows; a directly billed account would
- Task 30: minor (deferred): no same-model baseline exists for the current step-7 wording on E1 (the only same-model E1 pair is old-wording try 1)
- Task 30: complete (no commits — 6722d42 unchanged; review approved; 1 Important plan-mandated, deferred to the final wave by ruling; 5 of 9 logins, 0 re-runs)
- Tasks 32–34: user go-ahead ("ok", 2026-10-09) for up to 6 logins plus up to 3 for repeats
- Task 32: dispatched (base 6722d42, implementer a76ea752222229e80, sonnet; report task-32-report.md; carried: Task 31 ⚠️ (a)(b)(c) grading allowances, Task 19's login-hiccup minor → treat a LOGIN_TIMEOUT/EXPIRED pass as dead)
- Task 32: implementer DONE_WITH_CONCERNS (no commits — updater.md unchanged; T=runs/updater-test-174527; claude-sonnet-5-5 / CLI 2.1.285, permission mode auto, 0 denials). Pass 1: items 1–9 all pass (diff 93 lines, canary 0, no invented data, largest note 128 lines, SKILL.md unchanged, learned.txt = six folders + 2026-10-09/snowflake-learn). Pass 2: no new changes (22 s, 0 queries, says nothing left to learn). Notes reverted (git status skills/ empty). 1 login, 0 repeats.
- Task 32: concern — the window edited the notes through the ~/.claude/skills/snowflake/ symlink path, which SKILL.md's Edit rule doesn't list; it worked with 0 denials only because the permission mode was auto (P7's rules may not hold outside auto mode)
- Task 32: concern — SKILL.md step 3 still names "NPM customers" as a check-in example, while a learned npm.md says to use the confirmed meaning (follows from expected.md items 3 and 8)
- Task 32: concern — the recipe re-runs used the made-up fixture IDs, so 2 of 4 returned no rows (proves the SQL compiles, not that it returns useful data); the pass-1 reply quoted one column value from a re-run result (transcript only, gitignored)
- Task 32: review dispatched (ab249bf629afda055, sonnet; state review of runs/updater-test-174527/ — no commits)
- Task 32: review ab249bf629afda055 failed early — API 418 "Your IP has been blocked! Ensure you are connected to the VPN"; waiting for the user to reconnect the VPN, then re-dispatch a fresh reviewer (same prompt)
- Task 32: fresh reviewer aaf46903551fc1bea dispatched (sonnet, same prompt) after the user reconnected the VPN (2026-10-10)
- Task 32: review (aaf46903551fc1bea): spec ✅, Approved — all nine expected.md items re-derive as PASS from pass1.diff (item 1 also gained an SFDC_ACCOUNT_D entry, accepted: item 1 says "gains", not "only"); canary 0 in both transcripts; both windows valid; 1 login; repo byte-identical to HEAD, no stash, real runs/ untouched. 1 Important (plan-mandated, P7, outside Task 32's files): SKILL.md's Edit rules (lines 10–11) list only ~/Code/Snowflake/... while the harness hands the model the ~/.claude/skills/snowflake/ symlink spelling (Read has that twin at line 8, Edit doesn't); the reviewer read the 2.1.285 permission code — an edit must match an allow rule under every spelling, so a default-mode window would prompt and -p would deny. Latent for this user: ~/.claude/settings.json has defaultMode auto and bare Read/Write/Edit allows. Every eval and updater window ran in auto mode, so 0 denials never exercised P7 (the same masking covers the read-only Bash calls P7 doesn't list).
- Task 32: ⚠️ resolved — Step 1 go-ahead recorded above; the CSVs were not opened (neither window's calls name one); the Step 4 outputs were recomputed from pass1.diff; the P7 conclusion is from reading the binary — carried to the final wave with a no-Snowflake probe (a `claude -p --permission-mode default --setting-sources project` window that edits a scratch note through the symlink path) to confirm before and after the fix; the Task 19 login-hiccup path stayed unexercised (login succeeded)
- Task 32: Ruling: the P7 symlink gap is real and deferred to the final fix wave — add `Edit(~/.claude/skills/snowflake/references/**)` beside the existing Edit rules, confirmed by the probe above — Tasks 33–34 also run in auto mode, so the fix wouldn't change them, and nothing builds on it before then — cost if wrong: if the final wave drops it, anyone running the skill outside auto mode (or without blanket Edit approval) gets a prompt on every note edit during /snowflake learn.
- Task 32: minor (deferred): updater.md step 4 says nothing about the login — pass 1 went from "Not logged in" to its first run_query with no sentence to the user (SKILL.md hands over to updater.md, bypassing the step-4 warning); belongs with Task 19's LOGIN_* minor
- Task 32: minor (deferred): SKILL.md:25-27 still names "NPM customers" as the check-in example after a learned npm.md records the confirmed meaning (costs at most one extra question)
- Task 32: minor (deferred): updater-written text quality — a positional "the next entry" reference, an "(accounts with NPM ingest)" heading over a SUBSCRIPTION_ACCOUNT_ID count, an unsupported "makes the scan slower" claim; the provider-column trap seen in the step-4 re-run was left out (updater.md takes pitfalls only from past runs)
- Task 32: minor (deferred): the pass-1 reply ran ~20 lines (updater.md:33 says "a few") and quoted one re-run value; pass 2 checks the learned.txt bookkeeping, not merge-vs-duplicate on re-learning
- Task 32: complete (no commits — 6722d42 unchanged; review approved; 1 Important plan-mandated, deferred to the final wave by ruling; 1 login, 0 repeats)
- Task 33: dispatched (base 6722d42, implementer ac12b8a6be39a6c57, sonnet; report task-33-report.md; extra checks: other notes < 300, SKILL.md unchanged, canary 0, size.diff saved before revert)
- Task 33: implementer DONE_WITH_CONCERNS (no commits — updater.md unchanged; T=runs/updater-test-003024; claude-sonnet-5-5 / CLI 2.1.285, auto, 0 denials; 4 min 32 s, 7 run_query calls). billing.md padded to 340 → 241 after the run; padding critical 1, real critical 2, "Similar padding" 1 (100 merged into 1; first 89 lines identical to HEAD). Other notes 27–125 lines, SKILL.md unchanged, canary 0, size.diff saved, notes reverted. 1 login (2 of 6 for Tasks 32–34), 0 repeats.
- Task 33: concern — the prune path (drop entries unused for 90 days, oldest first) never ran, because merging alone got under 300; the 150 old padding entries survived
- Task 33: concern — updater.md's size rule says "when an update would push a note past its limit", yet the window shrank billing.md, which its learning hadn't touched (right outcome; the wording doesn't strictly cover a note already over the limit)
- Task 33: review dispatched next (state review of runs/updater-test-003024/)
- Task 33: review dispatched (a9ea5fc2445e5d503, sonnet)
- Task 33: review a9ea5fc2445e5d503 failed early — API 418 (VPN dropped again); waiting for the user to reconnect, then re-dispatch a fresh reviewer (same prompt)
- Task 33: fresh reviewer aa7987476b28ac668 dispatched (sonnet, same prompt) after the user reconnected (2026-10-12)
- Task 33: review (aa7987476b28ac668): spec ✅ (brief + extra checks), Approved — padded and after-states rebuilt byte-identical from HEAD + generator + size.diff; 100 "Similar padding" merged into 1 with nothing lost; all three HEAD Critical. lines survive; window valid; 1 login; tree reverted. 1 Important (plan-mandated): the brief's padding can't reach the prune path — only the 100 similar lines could merge, the note ended 59 lines under the limit, so spec §10.5's "shrinks by merging entries and removing unused ones; no critical entry is removed" has evidence for merging only; the 2026-01-10 padding critical entry survived because nothing was pruned. The gap is the test design, not the updater (updater.md:61-64 reads "merge, then remove oldest first").
- Task 33: ⚠️ resolved — the prune half is the Important above (ruled below); whether the window's habit of size-checking a note its learning never touched is stable is one sample → final-wave wording fix (minor below)
- Task 33: Ruling: run one follow-up window ("Task 33b") with 231 unmergeable padding lines (200 distinct old facts dated 2026-01-01..06-30, 30 recent facts dated 2026-08-01..09-28, the old critical entry) taking billing.md to 320 lines, and check: under 300, critical kept, both real critical entries kept, all 30 recent kept, some old removed oldest-first, HEAD's 89 lines untouched — spec §10.5 names the removal half explicitly, and the run costs 1 login inside the user's 6 for Tasks 32–34 (2 used + 1 + Task 34's 3) — cost if wrong: one Okta tab and ~10 minutes for evidence the final verdict could otherwise only mark "merge verified, prune not exercised". Script dry-run on a scratch copy: 320 lines, 200 distinct tokens, dates as designed.
- Task 33: minor (deferred): updater.md:61-64 — "when an update would push a note past its limit" doesn't cover a note already over that the learning never touched, and "then remove …" doesn't say "if still over, until under"; final-wave one-line fix: check every note's length; if merging leaves one over, remove oldest unused first until under
- Task 33: minor (deferred): the billing.md merge was written with Bash `python3 - <<EOF`, a write path SKILL.md's allowed-tools doesn't list (auto mode hid it, like the P7 symlink gap) — add to the final wave's P7 probe, or have updater.md say to change notes with Edit
- Task 33: minor (deferred): report slip (tables.md +12 -1 vs the diff's +11 -1); the last re-run swapped in a real account although updater.md:20-21 says to fill placeholders from the source run's values (results gitignored; notes hold none)
- Task 33: fix round 1/5 dispatched — resume implementer ac12b8a6be39a6c57 with task-33-fix1-findings.md (follow-up window, 1 login)
- Task 33: fix round 1 implementer DONE_WITH_CONCERNS — follow-up Window A FAILED on the old wording: billing.md stayed at 320 lines ("this update didn't add to it"); fix 3bf0ade "Size-check every note in the updater and prune until under the limit" (updater.md only; suite 124); Window B passed: 320 → 299 lines, padding critical 1, real critical 2, recent 30, old 179 (Padding fact 000–020 removed; newest removed 2026-01-19, oldest kept 2026-01-20), first 89 lines identical to HEAD, other notes 33–127, SKILL.md unchanged, canary 0, notes reverted. Logins 2 (Window A = 3rd of 6 for Tasks 32–34; Window B = repeat 1 of 3).
- Task 33: concern — spec §6.3 (lines 340–343) and plan Task 19 still carry the old "when an update would push a note past its limit" sentence; only updater.md changed
- Task 33: concern — Window B pruned with `sed -i` through Bash (the deferred P7 write-path item); 299 lines leaves no slack (one sample per wording); the window wrote a column-format pitfall learned from its own step-4 re-run (placeholder only; updater.md takes pitfalls from past runs only)
- Task 33: fix round 1 re-review dispatched (acd9224e7d93616c7, sonnet; package review-6722d42..3bf0ade.diff; windows runs/updater-test-145350 and -150127)
- Task 33: fix round 1/5 (1 addressed, 0 open — prune half of §10.5 now evidenced by window B; commits 6722d42..3bf0ade; re-review acd9224e7d93616c7: window A's failure confirmed as the conditional wording, B valid and every step-4 check re-derived, merge path and the Critical rule kept, no new Critical/Important breakage)
- Task 33: minor (deferred): updater.md:64 "until it is under 300 lines" hard-codes the area-note limit (line 61 gives SKILL.md 150 and says "about 300"); "until it is under its limit" fixes it
- Task 33: minor (deferred): spec §6.3 (line 341) and plan Task 19 (line 2759) still carry the old "when an update would push a note past its limit" sentence — doc drift; update the spec line in the final wave
- Task 33: minor (deferred): nothing says what to do when a note is still over after merging and removing every non-Critical entry older than 90 days (pre-existing spec gap) — a "say so in the report" clause closes it
- Task 33: minor (deferred): the follow-up padding lists old entries in date order at the top of the block, so a pass can't tell date-based pruning from deleting the top block (window B did check the block for Critical and cut at a date boundary); one sample per wording; 299 leaves no slack
- Task 33: minor (deferred): the fix report names no pytest command (124 tests collect; suite not re-run by the reviewer)
- Task 33: complete (commits 6722d42..3bf0ade, review clean after 1 fix round; 3 logins — first run, window A, window B as repeat 1 of 3)
- Task 34: Ruling: if N2 ≥ N1, diagnose before reverting; after a fix, re-run only the windows the fix affects (a SKILL.md fix → window 3 alone against the still-learned notes; an updater/entry-wording fix → windows 2 and 3), within the 2 repeat logins left; a full 3-window repeat (the plan's "repeat Steps 2–5") exceeds what the user approved, so stop and report instead — cost if wrong: a fix verified on 1–2 re-run windows instead of a full fresh repeat.
- Task 34: dispatched (base 3bf0ade, implementer ac3ba3ea5cc1dcff4, sonnet; report task-34-report.md; 3 logins + 2 repeats left)
- Task 34: implementer DONE_WITH_CONCERNS (no commits; T=runs/updater-test-152305). **N1 = 21, N2 = 5** (log cross-check 21+0 and 5+0) — N2 < N1 ✅; window 3 read the learned entries and ran the new recipes in order, and its answer matched window 1's. The updater changed finding-data.md (4 recipes, a freshness check, 4 pitfalls) and tables.md (5 table entries); SKILL.md and updater.md untouched; notes reverted (HEAD 3bf0ade). 3 of 3 logins, 0 of 2 repeats.
- Task 34: concern — the learned "What a dbt model reads" recipe hard-codes the dbt production service-account name (internal, not customer data, but a specific value outside {{placeholders}}; a rename returns no rows)
- Task 34: concern — queries issued together ran back to back in the server log (four independent queries took 133 s; overlapping would be about 39 s), so SKILL.md step 5's "run in parallel" saves no wall time today; run_query has no readOnlyHint
- Task 34: concern — the updater's re-run files are double-numbered (01-01-….sql, cosmetic); window 2 ran in plain-text mode (the plan's command), so its model and permission mode aren't recorded; one pair of windows, no variance shown
- Task 34: review dispatched (a3fa66e78ab78f0c7, sonnet; state review of runs/updater-test-152305/)
- Ruling: run the final whole-branch review and its single fix wave before Task 35, so Task 35's offline re-run and §10.6 verdict describe the branch as it will merge; Task 35 Step 4 (report, finishing-a-development-branch) then closes the plan — cost if wrong: none; Task 35 is offline and re-runs everything anyway.
- Task 34: review (a3fa66e78ab78f0c7): spec ✅, Approved, no Critical/Important — N1 = 21 and N2 = 5 exact across transcript tool_use ids, the brief's grep, the per-pid server log and the SQL files; all three windows valid (3 logins, no LOGIN_* events); window 3 found the learned entries and its 5 queries equal learned recipes in order; answers agree in substance; learned notes pass the notes rules (24 dry-run PASS on a rebuilt copy); learn.diff == final.diff; tree back at HEAD
- Task 34: ⚠️ resolved — Step 1 go-ahead recorded above; the learned recipes' live knowledge check is moot (reverted; each matched a successful re-run); the serialized-queries cause needs a live experiment → carried to the final wave (offline: add readOnlyHint to both tools; the 1-login check needs the user's OK); window 2's model unrecorded (plain-text command, plan-mandated)
- Task 34: minor (deferred): "run independent queries in parallel" (SKILL.md:33-34, spec §5) saves no wall time — four independent queries took 133 s back to back, not ~39 s; server code shows no server-side cause (sync tool on a worker thread, no lock held during a query); likely the CLI starts MCP calls one at a time; neither tool sets ToolAnnotations(readOnlyHint=True) (server.py:22, 41)
- Task 34: minor (deferred): the learned "What a dbt model reads" recipe over-reaches — proven for one incremental model, relies on a __dbt_tmp view, hard-codes the dbt service-account literal; updater.md could require that a literal copied from a result is a stable system identifier and that an entry states the scope its one run proved
- Task 34: minor (deferred): the learned Looker recipe states a one-run negative as a standing fact ("Looker queries did not appear in Snowflake at all") although finding-data.md:39 lists REPORTING_LOOKER_PDT
- Task 34: minor (deferred, plan-mandated test design): all three windows had open Bash and Read; window 3 grepped the learned entry before loading the skill (gitignored runs/ stayed unseen, but not by a deny rule); re-run files double-numbered (updater.md:20-21 doesn't say to pass an unnumbered step name); window 2's server started 83 s after launch
- Task 34: complete (no commits — 3bf0ade unchanged; review approved; 3 logins, 0 repeats). All live tasks done: Tasks 32–34 used 6 of 6 logins + 1 of 3 repeats.
- Final review: dispatched (af6edf8eb019bcb56, opus; package review-ddcb2af..3bf0ade.diff — 44 commits, 52 files; note: main is a387cc2, and a387cc2..ddcb2af holds only the spec and plan commits, so ddcb2af is where implementation began; asked to triage every deferred/final-wave item into must fix / fix now / can wait)
- Final review: af6edf8eb019bcb56 stopped on an API stream idle timeout mid-review; resumed via SendMessage
- Final review (af6edf8eb019bcb56, opus): **With fixes** — no Critical; 5 Important + 5 Minor; ran pytest (124) and check_notes --dry-run (19 PASS) read-only; `claude mcp get snowflake` wrote one no-login server_started line to runs/logs/2026-10-12.log. Important: (1) check_install.py:21-22 exact-dict match now FAILs on CLI 2.1.285 (adds "source":"user") — a false FAIL on a correct install; (2) /snowflake learn can silently lose learnings — no login warning (SKILL.md hands over to updater.md), and a missed Okta tab drops every recipe and still marks folders learned; (3) neither tool sets readOnlyHint, and 2.1.285 runs MCP tools concurrently only when it's set, so "run in parallel" can't happen (133 s vs ~39 s); (4) README install fails on a fresh laptop; (5) the P7 symlink Edit rule. Minor: billing.md:89 row count (reached an E7 answer); network errnos 250001/250003/250005 read as SQL_ERROR, so SKILL.md says to fix the query; owner recipe can pair one AE's name with another's email (needs live check); unprobed ELIA ACCOUNT_ID join (needs live probe); same-day follow-ups to a learned folder are never learned.
- Final review triage: must fix — 316, 284+435, 470/475/476, 331–333, 426/432–434, 410/419; fix now — 460, 462, 452/457, 286, 479 (numbering), 292, 415/407, 390, 456/461, 315, 262; can wait — every other deferred line (per-line reasons in the review), including Task 27's Important 351 (re-verifying costs a login) and the live-check items 254/263/269/366/408. Also closed: 176 (no EventLog.write passes event=/self=), 293 (2.1.285 accepts list-form allowed-tools), 451 (fixed in 3bf0ade).
- Final review: Ruling: accept the reviewer's "can wait" triage as given — each line carries a reason, and the items it defers need a live login, test-harness robustness or wording no eval tripped — cost if wrong: a deferred minor surfaces in daily use and needs a later fix.
- Final review: Ruling (declined-to-judge lines): SYSTEM$ functions pass the guard — accepted, §5.3 defines the guard by statement type and the read-only role is the second line of defence; `->>` chains — accepted, fail closed (Task 3); Account_owner.sql in pushed history — the user's choice (ledger 321); approved rulings not re-argued — accepted; very wide SELECT * previews — accepted, the spec fixes the preview shape; connector network retries past timeout_seconds — accepted as a known risk, needs live failure injection; read-only Bash (wc -l) prompting in default mode — accepted, the Edit-only write rule covers the write path — cost if wrong: one of these surfaces as a prompt or a slow failure in daily use.
- Final review: Minor 2 (network errors read as SQL_ERROR) joins the fix wave by ruling — a one-line SKILL.md row in a must-fix file, and this user's VPN drops are frequent (two reviews died on them this week) — cost if wrong: none.
- Final review: Ruling: split the fix wave into 7 small sequential dispatches (A check_install + new test; B updater.md + spec §6.3; C server.py readOnlyHint + test; D SKILL.md + login-free P7 probe; E evals.md move + run_eval docstring + README:13 + spec 355/445; F README fresh-laptop install; G billing.md) instead of the skill's one fix dispatch — the user's global CLAUDE.md (Tier 1) requires the smallest independently executable pieces, one logical change, ideally ≤2 files, and overrides skill instructions; one scoped re-review still covers the whole wave — cost if wrong: more dispatch overhead than one batch.
- Final fix wave: FIX_BASE 3bf0ade; briefs final-fix-A..G.md in the workspace; A dispatched (ab918c0de7f875951, sonnet)
- Final fix A: DONE (a657b14 — check_install matches name+status only and reports a dead window; new tests/test_check_install.py, 8 cases, TDD; suite 132; real check_install.py: 5 PASS on CLI 2.1.285). Minor (deferred): a claude process killed mid-line still gives a JSONDecodeError traceback; a missing claude binary is a traceback, and three window scripts hard-code its path.
- Final fix B: dispatched (ab2a24d126709a428, sonnet; base a657b14)
- Final fix B: DONE_WITH_CONCERNS (ae0db48 — updater.md: login warning before the first re-run; only SQL_ERROR/BLOCKED/TIMEOUT drop a recipe; LOGIN_*/INTERNAL_ERROR retry once then stop with no note changes and no learned.txt mark; size rule "under its limit", report a note still over; Edit-only note changes; missing learned.txt = empty; never remove a Critical recipe; unnumbered step names; spec §6.3 size paragraph synced; updater.md 97 lines; suite 132; dry-run 0 failed)
- Final fix B: concern — spec §6.3 step 4 (lines 307–308) still says "drop any that fail" → Ruling: add tiny fix H (sync that sentence to updater.md) — one spec sentence, keeps the binding spec consistent with the shipped procedure — cost if wrong: none
- Final fix B: minor (deferred): a stopped learn run leaves an unmarked runs/<today>/snowflake-learn/ folder (SQL saved before connecting); the next /snowflake learn marks it learned, so it self-heals; a SQL_ERROR on the retry drops that recipe rather than aborting (the brief's "if it still fails" read as "fails with a login/internal code again"); the stop path is unexercised live
- Final fix C: dispatched (ab93f0c4a486a3992, sonnet; base ae0db48); fix H brief written (final-fix-H.md)
- Final fix C: DONE_WITH_CONCERNS (d7ff3e9 — readOnlyHint=True on status and run_query; new list_tools test RED→GREEN; suite 133; fake-backed stdio check shows the hint on the wire). Minor (deferred): the live overlap check stays open (needs a login); the hint also lets Claude Code's plan mode treat both tools as read-only, so run_query can run in plan mode (read-only on Snowflake, but it writes .sql/.csv under runs/); permission prompts unchanged (checkPermissions ignores the hint)
- Final fix D: dispatched (a3c979bcbe382c6f5, sonnet; base d7ff3e9; includes the login-free P7 probe before and after)
- Final fix D: DONE_WITH_CONCERNS (a3e8310 — SKILL.md 91 lines: Edit(~/.claude/skills/snowflake/references/**) added; step 4 calls status on its own first and waits; SQL_ERROR row: network/connect messages → don't change the query, tell the user (VPN); "Customer data (names, IDs, results) stays in runs/"; suite 133; scratch note deleted; tree clean). Probe before/after INVALID: `--setting-sources project` drops the user's apiKeyHelper, so the nested window can't authenticate (stops at "Not logged in" before any model call); the brief's command also dropped the user-level skill (a temp project-level link fixed that). No window made a tool call; nothing queried Snowflake.
- Final fix D: the implementer began to inspect the user's apiKeyHelper to pass it to the probe; the auto-mode classifier denied it as credential exploration and the implementer stopped without reading or using it — surfaced to the user; the controller won't route around it
- Final fix D: Ruling: ship the P7 symlink Edit rule unverified (brief item 7: an extra allow rule can't break anything) and record it in the final report as unverified, with the probe the user can run themselves if they ever leave auto mode — the gap is latent for this user (auto mode plus blanket Edit allows), and any verifying route needs the user's credential setup — cost if wrong: if Claude Code also protects ~/.claude/ paths, note edits outside auto mode would still prompt.
- Final fix E: haiku dispatch a78e813d008a687b8 failed at start ("The given model doesn't exist in the requested endpoint" — haiku unavailable on this endpoint; nothing changed); re-dispatched on sonnet (ad7e5b605a707de4c; base a3e8310). Ruling: use sonnet for the remaining pieces (F, G, H) — cost if wrong: slightly higher cost per piece.
- Final fix E: DONE_WITH_CONCERNS (a732593 — git mv to tests/evals.md (100% rename), run_eval.py EVALS path + 10-tool docstring, README row, spec lines 355/445; skills/snowflake/evals/ gone; suite 133; EVALS.exists() True; git grep matches only the plan). Minor (deferred): a skill window that reads outside the skill folder can still reach the Musts — SKILL.md:7 allows Read(~/Code/Snowflake/**) and spec §10.4 repeats the Must table; the E8 route (grepping the skill folder) is closed; no eval re-run
- Final fix F: dispatched (a8c3b9659684c6be6, sonnet; base a732593)
- Final fix F: DONE_WITH_CONCERNS (669efd5 — README install steps 1–7: run from the repo folder, create .venv, mkdir ~/.snowflake ~/.claude/skills, chmod 600, live_login_check.py first (it writes runs/evals/values.toml); +17/-8). Minor (deferred): a truly fresh laptop also needs Python 3.14, the repo cloned at ~/Code/Snowflake, and claude at /opt/homebrew/bin (hard-coded in tests/check_install.py:16, live_login_check.py:17, run_eval.py:23)
- Final fix G: dispatched (a8da3dd8d12cf4398, sonnet; base 669efd5)
- Final fix G: DONE_WITH_CONCERNS (5acbad4 — billing.md: "one of the largest tables (billions of rows)"; the cross-reference names "Find tables by name" with `RAW` as {{database}} and `daily_view` as the search term; dry-run 0 failed; suite 133; the filled query passes the guard offline)
- Final fix G: Ruling: keep `RAW` as the database to search — the user's original Snowflake.md (d56a0d1, lines 284–294) documents product_consumption_daily_view's columns directly under "Source: Raw Product Consumption" beside the RAW.PRODUCT_CONSUMPTION tables; unverified live — cost if wrong: one wasted search query before the skill looks elsewhere (the old wording named no database at all).
- Final fix H: dispatched (a8945e17281a84388, sonnet; base 5acbad4)
- Final fix H: DONE (81c2114 — spec §6.3 step 4 now says only SQL_ERROR/BLOCKED/TIMEOUT drop a recipe; a login or internal error retries once, then stops with no note changes and no learned.txt mark). Minor (deferred): spec §5.5's error table doesn't list LOGIN_FAILED or INTERNAL_ERROR (the plan adds them, decision P4); spec step 4 doesn't mention updater.md's pre-re-run login warning
- Final fix wave: all 8 pieces committed (a657b14, ae0db48, d7ff3e9, a3e8310, a732593, 669efd5, 5acbad4, 81c2114); scoped re-review dispatched (af84d938b79b738e6, sonnet; package review-3bf0ade..81c2114.diff; findings final-fix-findings.md)
- Final fix wave re-review (af84d938b79b738e6): **all findings addressed, no new Critical/Important** — must-fix 1–6 and every fix-now item ADDRESSED with file:line evidence; ran pytest (133), check_notes --dry-run (19 PASS, 0 failed), check_install (five PASS, exit 0) at HEAD 81c2114; git diff --check clean; each commit touches only its brief's files.
- Final fix wave: parked — updater.md:29 vs SKILL.md:58: a network-type SQL_ERROR after login (VPN drop mid-learn) still drops a recipe and the folder is still marked learned — Ruling: real, not a regression (the old wording dropped on any failure), nothing downstream builds on it, and the SDD allows no second fix wave; surfaced to the user as the one known residual, with the one-line fix (treat a connect/network SQL_ERROR like a login error) — cost if wrong: a VPN drop during /snowflake learn can still lose that run's learnings.
- Final fix wave: parked — an aborted learn leaves an unmarked snowflake-learn run folder (self-heals on the next successful run); spec gaps exposed by H (§5.5 doesn't define LOGIN_FAILED/INTERNAL_ERROR; spec:218 still says fix-and-retry every SQL_ERROR; spec step 4 omits the pre-re-run warning) — Ruling: doc drift, no behaviour effect — cost if wrong: none.
- Final fix wave: parked — billing.md:32 searches RAW, but finding-data.md:12 calls RAW "rarely", finding-data.md:58's defaults omit it, and billing.md:46 says the daily views come after RAW — Ruling: keep (Task-G ruling stands, unverified live) — cost if wrong: one wasted search query; one word to change after a live check.
- Final fix wave: out-of-scope (deferred): spec:245 lists allowed-tools as only the two MCP tools (SKILL.md has eight entries); SKILL.md:7 Read(~/Code/Snowflake/**) still lets a skill window read tests/evals.md and the spec's Must table by absolute path; check_install.py:44 raises on a truncated JSON line; /opt/homebrew/bin/claude hard-coded in three scripts; README lacks a Python 3.14 prerequisite and a clone step
- Task 35 Step 1 (controller, HEAD 81c2114): pytest 133 passed; check_notes --dry-run 0 failed; check_install five PASS (exit 0); git status shows only this untracked progress file (allowed by R2)
- Task 35 Step 2 — §10.6 criteria:
  1. Unit tests pass — ✅ 133 passed (Step 1)
  2. Every note query runs — ✅ Task 28 live check 19 PASS, 0 failed; all 19 sql blocks are byte-identical between 6b3d55f and HEAD (later note commits changed prose only)
  3. Live login checks: no login without a query, exactly one login for three queries — ✅ Task 27 (its deferred Important on pid grouping triaged "can wait": results were verified per pid)
  4. All ten evals meet "Must" and the checks — ✅ Tasks 29–30 (E1 after the step-7 fix; check-ins on E3 and E7 only)
  5. Updater tests incl. speed check — ✅ Task 32 (items 1–9, pass 2 nothing new), Task 33 (merge 340→241; prune 320→299 after fix 3bf0ade, oldest first, Critical kept), Task 34 (N1 = 21 → N2 = 5)
  6. Skill beats its baseline on every prompt that triggers it — ✅ by ruling: strictly ahead on 7 of 8 (same-model pairs), E7 a ceiling tie (both runs met every applicable check; the skill used 0 queries and 0 logins vs 6 and 1)
  Caveat: the live evidence predates the final fix wave (a657b14..81c2114 — readOnlyHint, status-first wording, updater login-safety, SKILL.md wording); those fixes are verified offline only. Suggested next live window (one login): confirm parallel queries overlap in the server log, probe the ELIA ACCOUNT_ID → RPM join, check the owner recipe on an account with two people in one role, and search RAW for the daily view.
- Task 35 Step 3: the §11 sleep check is not yet done — left with the user (ask a question, leave the window open through ≥4 hours of laptop sleep, ask again; pass = an immediate "session expired" and a new login tab, the log shows query_failed code=LOGIN_EXPIRED then login_started)
- Task 35: complete (no commits; verdict above)
- Finishing: the user said they are the only maintainer, "do as appropriate" → Ruling: merge snowflake-skill into main locally (fast-forward; origin/main = main = a387cc2), push main to the private GitHub repo as the off-laptop backup, then delete the merged branch locally and on origin — a PR adds a review step with no reviewer; private repo confirmed — cost if wrong: none; every commit stays on main.
- Finished: main = origin/main = 81c2114 (fast-forward; tests 133 on the merged result); snowflake-skill deleted locally and on origin; plan workspace .superpowers/sdd/2026-09-30-snowflake-skill deleted (git history and runs/ hold the record). Follow-ups for the user: the §11 sleep check; one approved live window (parallel overlap, ELIA join, two-AE owner recipe, RAW daily view); the one-line VPN-drop fix in updater.md.
