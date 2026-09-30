# Snowflake Skill — Design Spec

- **Date:** 2026-09-30
- **Status:** Draft for review
- **Owner:** Jay Karnik (Networking PM)
- **Repo:** `~/Code/Snowflake` (branch `snowflake-skill`)

## 1. Summary

This repo becomes a personal Claude Code skill that answers New Relic data questions from
Snowflake. The user asks in plain English from any project. Claude finds the right table, runs
read-only queries and answers in plain English. It saves every query, result and summary in the
gitignored `runs/` folder.

The skill has four parts:
- a main document (`SKILL.md`, moved from `Snowflake.md`)
- reference notes: one per question area, plus a table index
- a small MCP server that connects to Snowflake
- a small settings file of non-secret connection values

An updater (`/snowflake learn`) turns past runs into better notes. Repeat questions then need
fewer queries.

The MCP server signs in through Okta on the first Snowflake query in each Claude window. It keeps
that login until the window closes.

The skill replaces today's toolkit (`session_server.py`, `q`, `CLAUDE.md`). That toolkit works only
inside this folder, and it failed twice in testing. One session waited silently 15 minutes for a
login, and one query hung for 21 hours.

## 2. Decisions

The user made these decisions during brainstorming, 2026-09-28 to 2026-09-30.

| # | Decision | Detail |
|---|---|---|
| D1 | Personal install | For Jay only, for now. Connection values live in one settings file, so sharing later needs a setup step, not a rewrite. |
| D2 | Four question areas | NPM adoption and usage; customer and account lookups; billing and consumption; finding what data exists. |
| D3 | Check in only when it matters | Ask in plain English only when a term has more than one reasonable meaning, or when a query would be slow or expensive. Otherwise run straight away. |
| D4 | MCP on first use | Our own small MCP server, registered for all Claude windows. It logs in on the first Snowflake query in each window. We chose it over the Snowflake CLI, Snowflake's own MCP and a shared background session (§2.1). |
| D5 | Every output goes in a gitignored folder | Queries, results, summaries and other outputs go in `runs/`, one folder per question. The original SQL files move there too. |
| D6 | No environment variables or secrets | Okta signs the user in through the browser. `~/.snowflake/connections.toml` holds the account, user, role and warehouse, none of them secret, along with the sign-in method. |
| D7 | One main skill document | `CLAUDE.md` is deprecated. `Snowflake.md` becomes the skill's main file, renamed `SKILL.md` because Claude Code requires that name. Its subparts become reference files. |
| D8 | Account owners | `Account_owner.sql` feeds the customers note. It maps an RPM account to its Salesforce account, then to that account's AE and TSM. |
| D9 | Skill updater | `/snowflake learn` distils past runs into the notes: a table index, recipes, pitfalls and confirmed definitions. A fixed bar decides what's kept (§6.3). It replaces the per-answer offer to save knowledge. We considered progress monitoring and dropped it as overkill. |

### 2.1 Evidence behind D4

The logs from the spikes on 2026-09-29 and 2026-09-30 are in `runs/20260929-153945/spike/` and
`runs/20260930-145700/spike2/`.

- **No saved logins.** The account sets `ALLOW_ID_TOKEN = false`, so every new connection needs
  a fresh Okta login, which takes 15–25 s.
- **Sessions expire.** `CLIENT_SESSION_KEEP_ALIVE` defaults to false, so idle sessions expire
  unless the client turns keep-alive on.
- **No hosted MCP.** The account has no Snowflake-hosted MCP.
- **Snowflake CLI:**
  - It needed a login on every command: two runs, two logins.
  - It printed a 5,000-row result as 261 KB into the terminal.
  - It sent a `DELETE` through to Snowflake.
- **Snowflake's MCP** (`snowflake-labs-mcp` 1.3.3):
  - It logs in as soon as a Claude window starts it, before any question, and its tools stay
    missing until that login finishes.
  - It blocked the `DELETE` before it reached Snowflake, because it denies statement types by
    default.
  - It returned the 5,000-row result as one 314K-character line, which Claude saved to a hidden
    file.
- **Skill-scoped MCP** (skill `context: fork` plus agent `mcpServers`): Claude Code 2.1.153 supports
  it, but Claude shuts the server down when the skill finishes. Every question would need a login.
- **Lazy MCP (chosen):**
  - A window that never queried Snowflake never logged in.
  - A window with three queries logged in once, at the first query (21 s).
  - The next two queries reused that login and took 9.1 s and 0.3 s.
  - The tool was available as soon as the window opened.

## 3. What the user experiences

- **Asking.** The user asks in plain English from any project, or types `/snowflake`. The skill
  triggers on questions about New Relic business data: accounts and Salesforce, account owners,
  NPM adoption, ingest, billing and entitlements. It also triggers on explicit Snowflake or SQL
  requests. It stays out of unrelated work, including questions about a customer's live
  telemetry, which New Relic itself answers.
- **Logging in.** The first Snowflake query in a Claude window opens the Okta login in the browser,
  which takes about 20 s. Claude says so just before the tab opens. The rest of that window reuses
  the login, and windows that never query Snowflake never ask. If a login lapses, Claude says so
  plainly, and the next query opens one new login.
- **Check-ins.** As D3 describes.
- **Answers.** Each answer has four parts, in this order:
  1. the result in plain English
  2. a small table, if useful
  3. a short "How I got this": definitions, tables, date range and caveats
  4. the SQL

  Every answer links the question's folder in `runs/`. Large results never go into the chat;
  only a preview does.
- **Safety.** The skill only reads, and refuses anything else before it reaches Snowflake. It
  queries production databases only, unless the user asks otherwise.
- **Gets smarter.** `/snowflake learn` reads past runs and writes what's worth keeping into the
  reference notes (§6.3), so similar questions need fewer queries next time. The skill suggests it
  once five or more new runs are waiting. Notes hold definitions and example queries with
  placeholders, and never hold customer data or results.

## 4. Architecture

```
Claude window ──MCP (stdio)──▶ snowflake MCP server ──Okta SSO, one session per window──▶ Snowflake
     │                              │
     │ reads                        └── writes queries + CSVs ──▶ runs/<date>/<question>/
     ▼
skills/snowflake/SKILL.md ──▶ references/*.md (read on demand)
```

| Unit | Purpose | Depends on |
|---|---|---|
| `skills/snowflake/SKILL.md` | When to use the skill, the workflow, the rules and an index of the reference notes | The MCP tools |
| `skills/snowflake/references/*.md` | Domain knowledge per question area, with verified example queries | — |
| `skills/snowflake/mcp_server/` | The MCP server: lazy login, read-only guard, query execution and result files | `mcp`, `snowflake-connector-python`, `sqlglot`, the settings file |
| `~/.snowflake/connections.toml` | Non-secret connection settings | — |
| `runs/` (gitignored) | Every output, one folder per question, plus the updater's list of learned runs | — |

Setup links the skill folder into Claude (`~/.claude/skills/snowflake` → `skills/snowflake`). It
also registers the MCP server at user scope, so both are available in every Claude window. Edits
in the repo take effect without reinstalling.

## 5. The MCP server

### 5.1 Lifecycle

- Claude Code starts the server with each window and stops it when the window closes.
- The server starts logged out. It imports the Snowflake connector only when first needed, so
  idle windows pay almost nothing.
- The first `run_query` call connects with these settings:
  - `connection_name="newrelic"`, read from `~/.snowflake/connections.toml`
  - `client_session_keep_alive=True`
  - a 2-minute browser-login timeout
  - session parameter `QUERY_TAG = 'snowflake-skill'`
- Each window has one connection. A lock makes sure that concurrent first calls trigger only one
  login.
- The connector prints login messages to stdout, which carries the MCP protocol. So the server
  redirects stdout to stderr while it connects.
- The server appends one line per event to `runs/logs/<YYYY-MM-DD>.log`, with timings. The events
  are server start, login started, logged in, and each query finished or failed. The log never
  holds query results.

### 5.2 Tools

**`status()`** has no side effects. It returns whether this window is logged in and, if so, the
user, role and warehouse. Claude calls it before the first query, to decide whether to warn the
user about a login tab.

**`run_query(sql, question, step="query", timeout_seconds=300, max_rows=100000)`**

Parameters:
- `sql`: exactly one statement.
- `question`: a short slug that names the question's folder, for example `npm-devices-by-type`.
  The server lowercases it and keeps only letters, digits and hyphens.
- `step`: a short name for this query within the question.
- `timeout_seconds`: the statement time limit, at most 3600. Claude sets it above 300 only after
  the user agrees (D3).
- `max_rows`: the maximum number of rows written to the CSV.

The tool runs these steps in order:
1. Save the SQL to the question folder. Every call saves its SQL, including refused and failed
   ones (D5).
2. Check the statement with the guard (§5.3).
3. Connect, if this window isn't connected yet.
4. Execute the statement with the time limit.
5. Stream the rows to a CSV next to the SQL. Only successful queries produce a CSV.

It returns a plain-text result containing:
- a header line with the row count, column count, elapsed seconds and Snowflake query ID
- the paths of the `.sql` and `.csv` files
- a preview of up to 50 rows, with cells over 200 characters shortened and tabs and line breaks
  shown escaped
- a note if the CSV reached `max_rows`

### 5.3 Read-only guard

- `sqlglot` parses the statement with its Snowflake dialect.
- The guard allows only three statement types:
  - `Select`, which includes `WITH … SELECT` and `UNION`
  - `Show`
  - `Describe`
- It refuses everything else, including:
  - `USE`, `CALL`, `COPY`, `PUT`, `GET` and `EXPLAIN`
  - input containing more than one statement
  - any statement that `sqlglot` cannot classify
- A refused statement never reaches Snowflake. The error names the refused statement type.
- The `FR_PRODUCT_ANALYST` role's own permissions stay as a second line of defence.

### 5.4 Result files

- Each question gets a folder at `runs/<YYYY-MM-DD>/<question>/`, using the local date.
  - A follow-up that refines the same question reuses its folder.
  - A new question gets a new folder.
- Each query writes two files, `NN-<step>.sql` and `NN-<step>.csv`. `NN` is a two-digit number
  that counts up within the folder.
- CSV format: UTF-8, standard quoting, a header row, and NULL written as empty. Values that contain
  commas, quotes, tabs or line breaks survive intact.
- The server finds `runs/` relative to its own location, at the repo root. A `--runs-dir` argument
  can override that.
- Claude writes `summary.md` into the same folder. It holds four things:
  - the answer and "How I got this"
  - any check-in answer the user gave
  - the recipes that Claude used
  - the table-index entries that Claude used

  Any other output for the question goes there too.

### 5.5 Errors and how Claude responds

| Code | When | Claude's response |
|---|---|---|
| `BLOCKED` | The guard refused the statement | Explain why. Never retry it as a write. |
| `LOGIN_TIMEOUT` | The browser login didn't finish within 2 minutes | Tell the user. The next call reopens the login. |
| `LOGIN_EXPIRED` | The session lapsed, for example while the laptop slept | Tell the user a login tab will open, then call again. |
| `TIMEOUT` | The statement ran past its time limit | Suggest a narrower query, or ask the user to allow up to 60 minutes. |
| `SQL_ERROR` | Snowflake rejected the SQL | Read the message, fix the query and retry up to two times. After that, tell the user. |

On `LOGIN_EXPIRED`, the server must not wait for a browser login inside the failing call. In
testing, the connector's own re-login waited 15+ minutes with no timeout. So the server discards
the dead connection and returns the error. The next call opens a fresh login, with the 2-minute
timeout.

If the server crashes or hangs, `/mcp` reconnect or a new window resets it. Between windows,
nothing persists except the files in `runs/`.

## 6. Skill document and reference notes

### 6.1 `SKILL.md`

Frontmatter:
- `name: snowflake`
- `description`: says when to use the skill, with the trigger words first, and never lists the
  workflow steps. The skill applies to questions that New Relic's internal Snowflake warehouse can
  answer:
  - customer accounts and Salesforce details
  - account owners
  - NPM and network monitoring adoption and ingest
  - billing and consumption
  - entitlements
  - finding tables

  It also applies to explicit Snowflake or SQL requests.
- `allowed-tools`: `mcp__snowflake__run_query`, `mcp__snowflake__status`.

The body stays under 150 lines, in four parts.

1. **Workflow.**
   1. Understand the question.
   2. Check `references/tables.md` and the recipes in the matching area note. Search Snowflake's
      catalog only if nothing there fits.
   3. Check in if D3 applies.
   4. Call `status`, and warn the user before a first login.
   5. Run the queries, with independent ones in parallel.
   6. Write `summary.md`.
   7. Answer in the §3 format.
2. **Rules.**
   - Only read.
   - Query production databases only. Never query `*_DEV`, `*_STAGING` or `DEV_*` unless the user
     asks.
   - `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` is append-only, the financial system of record.
   - Use `LIMIT` while exploring. Use date filters or `SAMPLE` on tables over 100M rows.
   - Keep the 5-minute default time limit.
   - Write outputs only to the question's `runs/` folder. Never write them to the current project
     unless the user asks.
3. **Learning.** `/snowflake learn` follows `references/updater.md` (§6.3). After an answer, Claude
   mentions the updater once five or more unlearned runs are waiting. Notes never hold customer
   data. Note edits stay uncommitted until the user asks to commit.
4. **Reference index.** One line per note, saying when to read it.

### 6.2 Reference notes (`skills/snowflake/references/`)

| Note | Content | Sources |
|---|---|---|
| `npm.md` | NPM definitions from ELIA: `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F` with `METRIC = 'NetworkMonitoring'`, where `DOMAIN_TYPE` is the device type. NPM definitions from Instrumentation Insights: `TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F` with `USAGE_CATEGORY = 'NetworkMonitoring'`, plus the mapping from event name to subgroup. Example queries: devices by type, reporting accounts, ingest by subgroup, trends. | `company_query.sql` |
| `customers.md` | Salesforce accounts and billing addresses, with line-break cleanup. Account owners: RPM account → Salesforce account → AE and TSM. Organisations and entitlements. The RPM account ID as the join from usage tables to Salesforce, confirmed in the knowledge checks. | `Account_owner.sql`, `addr.sql`, `Snowflake.md` |
| `billing.md` | Product consumption tables and their columns. The `ALL_DAILY_USAGE` rules: append-only, de-duplication, the `INSERTED_AT` tie-break and US over EU. Product lines and metrics. The pipeline and its 2 am PST SLA. The Slack help channels. | `Snowflake.md` |
| `finding-data.md` | Data layers and environments. The database and schema inventory. Naming standards and data classification. Discovery queries using `INFORMATION_SCHEMA`, `DESCRIBE` and the dbt artifacts. The Confluence reference pages. | `Snowflake.md` |
| `tables.md` | The table index, built by the updater. For each table used: what it holds, its key columns and their meaning, gotchas, and a last-used date. | Runs, via the updater |
| `updater.md` | The updater's steps and the bar for what's kept (§6.3). | — |

Each area note has a Recipes section and a Pitfalls section. Every learned entry carries a
last-used date.

Every example query meets three conditions:
- It sits in a fenced `sql` block.
- It uses a `{{placeholder}}` for any specific value, such as a company name or account ID.
- It ran successfully in the knowledge checks (§10.2). Facts that fail the checks get fixed or
  dropped.

One fact is dropped outright. The data dictionary in the developer sandbox
`DEV_KNAGENDRA_TRANSFORMED` breaks the production-only rule, and `INFORMATION_SCHEMA` covers its
purpose.

### 6.3 The skill updater (`references/updater.md`)

The updater runs when the user types `/snowflake learn` or asks the skill to learn from its runs.
Nothing runs on a schedule. It uses Claude's normal file tools and `run_query`, so it adds no new
code.

Steps:
1. List the question folders in `runs/` that `runs/learned.txt` doesn't name yet.
2. Read each folder's `.sql` files, including failed ones, and its `summary.md`. Never open the
   CSVs.
3. Pick the items that clear the bar below.
4. Rewrite each item with `{{placeholders}}`. Re-run every new or changed recipe through
   `run_query`, and drop any that fail.
5. Write the new entries:
   - table entries go in `tables.md`
   - recipes, pitfalls and confirmed definitions go in the matching area note

   Update an existing entry instead of adding a near-copy. Set the last-used date on every entry
   that a run used.
6. Apply the size limits.
7. Add the processed folders to `runs/learned.txt`.
8. Report in a few lines what it added, updated, merged and removed. Leave the edits uncommitted.

**The bar.** The updater keeps an item only if it passes all three of these tests:
- **It worked,** and still works when re-run.
- **It's reusable.** It can be written with placeholders, and isn't tied to one customer or one
  day.
- **It's new.** If the notes already cover it, the updater updates that entry instead.

It must also pass at least one of these:
- **Changes the answer.** This covers a definition the user confirmed at a check-in, a filter or
  rule needed for correct numbers, or a trap that produced a wrong result. These entries are
  critical: always kept and never pruned.
- **Saved effort.** Finding it took searching or a failed attempt.
- **Came up again.** The same table or query shape appears in two or more questions.

**Never stored:**
- results or numbers
- customer names or IDs
- full column lists. `DESCRIBE` returns those in a second, so store only key columns and their
  meaning
- facts that go stale, such as row counts or the latest loaded date
- near-copies of an existing recipe

**Size limits.** Each reference note stays under about 300 lines, and `SKILL.md` stays under 150.
When an update would push a note past its limit, the updater first merges similar entries. Then it
removes entries that no question has used for 90 days, oldest first. It never removes a critical
entry. A recipe that stops working gets fixed or removed.

## 7. Outputs and file layout

Tracked in git:

```
README.md                      what the skill is; install, update, uninstall; running tests
requirements.txt               pinned Python dependencies
skills/snowflake/SKILL.md      main skill document (moved from Snowflake.md)
skills/snowflake/references/   npm.md, customers.md, billing.md, finding-data.md, tables.md, updater.md
skills/snowflake/mcp_server/   guard.py, results.py, server.py
skills/snowflake/evals/        end-to-end prompts and expected behaviour (placeholders only)
tests/                         unit tests, check scripts, made-up runs for the updater tests
docs/superpowers/              this spec and the implementation plan
```

Gitignored:

```
.venv/                         Python environment
runs/<YYYY-MM-DD>/<question>/  NN-<step>.sql, NN-<step>.csv, summary.md, other outputs
runs/logs/<YYYY-MM-DD>.log     MCP server event log (no query results)
runs/originals/                company_query.sql, Account_owner.sql, addr.sql, addr.tsv
runs/evals/values.toml         real values for placeholders: company names, account IDs
runs/learned.txt               question folders the updater has already learned from
```

Customer names and IDs appear only in gitignored files.

## 8. Repo migration

1. Run `git mv Snowflake.md skills/snowflake/SKILL.md`, keeping the pending title change. Rewrite
   the file per §6.1, and move its catalog content into the reference notes.
2. Once their knowledge is in the notes, move `company_query.sql`, `Account_owner.sql`,
   `.sfrun/addr.sql` and `.sfrun/addr.tsv` into `runs/originals/`. `Account_owner.sql` is not in
   git, so it is moved, never deleted.
3. Delete `CLAUDE.md`, `session_server.py` and `q`, whose history git keeps. Then delete `.sfrun/`,
   which holds only runtime pipes once step 2 has moved the addr files out.
4. Rewrite `README.md`.
5. Update `.gitignore`: drop `.sfrun/`, `.sf_server.log` and `*.out`, and add `__pycache__/` and
   `.pytest_cache/`.

## 9. Setup

Claude does this once.

1. Install `requirements.txt` into the existing `.venv` (Python 3.14). The requirements are
   `snowflake-connector-python`, `mcp` 2.x, `sqlglot` and `pytest`.
2. Write `~/.snowflake/connections.toml`, with permissions `600` and a `[newrelic]` section:
   - account `pda47359.us-east-1`
   - user `JKARNIK`
   - authenticator `externalbrowser`
   - role `FR_PRODUCT_ANALYST`
   - warehouse `TEAM_PRODUCT_ANALYST_XSMALL`
3. Register the server:
   `claude mcp add --scope user snowflake -- <repo>/.venv/bin/python <repo>/skills/snowflake/mcp_server/server.py`.
4. Link the skill: `~/.claude/skills/snowflake` → `<repo>/skills/snowflake`.
5. Restart any open Claude windows, then verify two things:
   - The skill appears in the skill list.
   - `/mcp` shows `snowflake` connected, without a login.

## 10. Testing

### 10.1 Connection unit tests (no Snowflake)

These use pytest with a fake connector.

- **Guard.**
  - It allows `SELECT`, `WITH … SELECT`, `UNION`, `SHOW` and `DESCRIBE`.
  - It refuses `DELETE`, `INSERT`, `UPDATE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`,
    `GRANT`, `USE`, `CALL`, `COPY`, `PUT` and `EXPLAIN`.
  - It refuses multiple statements, a write hidden after a comment, and text it can't parse.
- **Semicolons.** A semicolon inside a string literal doesn't split or break a query.
- **CSV round-trip.** It keeps commas, quotes, tabs, line breaks, NULLs and non-ASCII text, such as
  Turkish company names.
- **Large results.** A 5,000-row result writes every row to the CSV and returns a 50-row preview.
  `max_rows` truncates the CSV and adds a note.
- **File names.** Files are named and numbered correctly inside the question folder.
- **Lazy login.**
  - Server start and `status` never connect.
  - The first `run_query` connects once.
  - Two concurrent first calls still connect only once.
- **Clean output.** Nothing reaches stdout while the server connects.
- **Error codes.** Fake failures map to the right codes: login timeout, expired session, statement
  timeout and SQL error.

### 10.2 Knowledge checks (live)

A script runs every `sql` block in the reference notes. It fills placeholders from
`runs/evals/values.toml` and gives each query a 2-minute limit. Each example must be cheap as
written, with a `LIMIT`, a tight filter or an aggregate. The check passes when every block
succeeds.

### 10.3 Live login checks

These use headless Claude windows, as in the spike, and check the server log:
- A window that never queries Snowflake shows no login.
- A window with three queries shows exactly one login.

### 10.4 End-to-end evals

The prompts live in `skills/snowflake/evals/` with placeholders. Their real values live in
`runs/evals/values.toml`. Each prompt runs in a fresh Claude window, first without the skill as a
baseline, then with it.

| # | Prompt | Must |
|---|---|---|
| E1 | How many accounts had network devices reporting yesterday, by device type? | Use ELIA with `METRIC = 'NetworkMonitoring'`, grouped by `DOMAIN_TYPE` |
| E2 | What was last month's NPM ingest in GB, split into SNMP, syslog, flow and traps? | Use Instrumentation Insights with the event-name mapping |
| E3 | How many NPM customers do we have? | Check in, asking which definition |
| E4 | Who are the AE and TSM for {{company_a}}? | Use the account-owner path |
| E5 | What are the billing addresses for {{company_b}} and {{company_c}}? | Use Salesforce accounts, with line-break cleanup |
| E6 | How much data did account {{npm_account_id}} ingest per day last week? | Use the billing tables, with the de-duplication rules |
| E7 | Show me every usage row for 2025. | Check in, offering a summary instead |
| E8 | Is there a table with SNMP trap counts per account? | Name the Instrumentation Insights table (`KSnmpTrap` events), and say whether it holds counts or GB |
| E9 | Draft an intro paragraph for my PRD. | The skill doesn't trigger |
| E10 | Explain what SNMP traps are. | The skill doesn't trigger |

Every prompt that triggers the skill must also meet these checks:
- It saves its queries, CSVs and `summary.md` in its `runs/` folder.
- It writes nothing outside `runs/`.
- Its answer follows the §3 format.

Across the whole set, check-ins happen on E3 and E7, and on no other prompt.

### 10.5 Updater tests

- **Made-up runs.** `tests/fixtures/runs/` holds runs with invented company names. They include:
  - a table used in two questions
  - a query that failed, then was fixed
  - a confirmed definition
  - a trivial one-off query
  - a near-copy of an existing recipe

  After one updater pass:
  - the notes gain the table entry, the pitfall and the definition
  - the one-off query is skipped, and the near-copy is merged
  - no invented company name or ID appears in the notes
  - a second pass finds nothing new
- **Size limit.** A note pushed past its limit shrinks by merging entries and removing unused ones.
  No critical entry is removed.
- **Speed check.** Ask a new kind of question, run the updater, then ask again in a fresh window.
  The second answer uses fewer queries.

### 10.6 Pass criteria

- Every unit test passes.
- Every reference-note query runs.
- The live login checks show no login and exactly one login.
- All ten evals meet their "Must" column and the checks above.
- The updater tests pass, including the speed check.
- With the skill, each prompt that triggers it meets more of its checks than it did in the
  baseline run without the skill.

## 11. Risks

| Risk | Mitigation |
|---|---|
| On an expired session, the connector's automatic re-login blocks with no timeout. | Detect the expiry, discard the connection and return `LOGIN_EXPIRED` (§5.5). A fake-connector test covers this, and a live check after a long laptop sleep confirms it. |
| Facts in `Snowflake.md` may be stale: tables, columns, the sandbox dictionary. | The knowledge checks (§10.2) find them, and each one is fixed or dropped. |
| `Account_owner.sql` has a trailing comma before `FROM` in `PivotedRoles`. | The knowledge checks run it. If Snowflake rejects it, remove the comma. |
| The `mcp` SDK 2.x renamed its APIs (FastMCP became MCPServer). | Pin versions in `requirements.txt`. |
| Claude Code may not load a symlinked skill folder. | Verify during setup. If it fails, copy the folder instead and add an update step. |
| Claude Code's MCP tool timeout may be shorter than a 5-minute query. | Check the default during implementation. If it's shorter, lower the query limit instead of adding a setting (D6). |
| Every Claude window runs an idle server process. | Lazy imports keep that process light. |
| The notes fill with noise over time. | The bar and the size limits in §6.3. Edits stay uncommitted, so the user can undo any change. |
| The updater learns a mistake. | It re-runs every recipe before saving it. It takes business definitions only from the user's own check-in answers. |

## 12. Out of scope

- Sharing with the NPM team, or publishing in `npm-claude-plugins`.
- Any write access to Snowflake.
- Using the skill outside Claude, such as from a terminal.
- Other authentication methods, such as key pairs or access tokens.
- Getting saved logins (`ALLOW_ID_TOKEN`) enabled. That needs a request to the data platform team,
  and isn't part of this build.
- Snowflake Cortex features, dashboards or scheduled reports.
- Progress monitoring, such as live status, run history or a learning log. The user judged it
  overkill.
- Scheduled or automatic learning. The updater runs only when the user asks.
