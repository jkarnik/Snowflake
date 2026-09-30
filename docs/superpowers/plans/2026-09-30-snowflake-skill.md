# Snowflake Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `~/Code/Snowflake` into a personal Claude Code skill that answers New Relic data questions from Snowflake, through a small MCP server that logs in on the first query in each Claude window.

**Architecture:** A stdio MCP server (`skills/snowflake/mcp_server/`), registered at user scope, stays logged out until its first `run_query`. It refuses anything but reads and writes each query's SQL and CSV to `runs/<YYYY-MM-DD>/<question>/`. `SKILL.md` holds the workflow and rules. `references/*.md` hold per-area notes, which `/snowflake learn` improves from past runs.

**Tech Stack:** Python 3.14 (the repo's `.venv`), `mcp` 2.2.0 (`MCPServer`), `snowflake-connector-python` 4.6.0, `sqlglot` 30.20.0, `pytest` 9.1.1, Claude Code 2.1.153 (`/opt/homebrew/bin/claude`).

**Spec:** `docs/superpowers/specs/2026-09-30-snowflake-skill-design.md`. Its §2 lists decisions D1–D9. Read the spec before starting any task.

## How to run this plan

- Work in `/Users/jkarnik/Code/Snowflake` on branch `snowflake-skill`. Run Python as `.venv/bin/python`.
- Keep the progress file `docs/superpowers/plans/2026-09-30-snowflake-skill.progress.md` current. After every task, record the task number, its commit SHA and the next task. On resume, read it first.
- Commit at the end of every task. Never push.
- Tasks marked **LIVE** open Okta browser logins (about 20 s each). Before a LIVE task, tell the user how many logins it will open and wait for their go-ahead. Every other task runs without Snowflake.
- The user is a product manager. Don't ask them technical questions. Decide, then state what you decided.

## Global Constraints

- **No secrets, no environment variables (D6).** Connection values live only in `~/.snowflake/connections.toml`, section `[newrelic]`: account `pda47359.us-east-1`, user `JKARNIK`, authenticator `externalbrowser`, role `FR_PRODUCT_ANALYST`, warehouse `TEAM_PRODUCT_ANALYST_XSMALL`. File mode `600`.
- **Connect settings (§5.1):** `connection_name="newrelic"`, `client_session_keep_alive=True`, a 2-minute browser-login timeout, session parameter `QUERY_TAG = 'snowflake-skill'`.
- **Tools (§5.2):** `status()` and `run_query(sql, question, step="query", timeout_seconds=300, max_rows=100000)`. `timeout_seconds` is at most 3600.
- **Read-only (§5.3):** only `Select` (including `WITH … SELECT` and `UNION`), `Show` and `Describe` reach Snowflake. A refused statement never reaches Snowflake.
- **Result files (§5.4):** `runs/<YYYY-MM-DD>/<question>/NN-<step>.sql` and `.csv`, local date, `NN` two digits counting up per folder. CSV: UTF-8, standard quoting, header row, NULL written as empty.
- **Preview (§5.2):** at most 50 rows; cells over 200 characters shortened; tabs and line breaks shown escaped.
- **Event log (§5.1):** one line per event in `runs/logs/<YYYY-MM-DD>.log` — server start, login started, logged in, query finished or failed — with timings. Never query results.
- **Error codes (§5.5):** `BLOCKED`, `LOGIN_TIMEOUT`, `LOGIN_EXPIRED`, `TIMEOUT`, `SQL_ERROR`, plus this plan's `LOGIN_FAILED` and `INTERNAL_ERROR` (decision P4).
- **Sizes (§6.3):** `SKILL.md` under 150 lines. Each reference note under about 300 lines.
- **Notes (§6.2):** every example query sits in a fenced `sql` block, uses `{{placeholder}}` for specific values, and must pass the knowledge checks. Notes never hold results, numbers, customer names or IDs.
- **Production only:** never query `*_DEV`, `*_STAGING` or `DEV_*` unless the user asks. `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` is append-only, the financial system of record.
- **Customer data** appears only in gitignored files (`runs/`).
- **Protect the user's files:** keep the uncommitted title edit in `Snowflake.md` (it becomes `SKILL.md`). Never delete the untracked `Account_owner.sql`; Task 24 moves it.
- **Old toolkit:** ignore the project `CLAUDE.md`, `session_server.py` and `q`. Never start that server. Never write to `runs/latest` — a parallel session may still use it.
- **mcp 2.x:** `from mcp.server.mcpserver import MCPServer`. Only a `ToolError` message reaches Claude; any other exception shows as a bare `Error executing tool …`.

## Verified Facts

Checked on 2026-09-30 without Snowflake: a throwaway venv plus reads of the installed source.

**mcp 2.2.0**
- `MCPServer("snowflake")` registers tools with `@server.tool(structured_output=False)`, which returns plain text only.
- Sync tools run in worker threads (`anyio.to_thread`), so two calls really run at once.
- `raise ToolError(msg)` (from `mcp.server.mcpserver.exceptions`) gives `is_error=True` with the text `Error executing tool run_query: <msg>`. Any other exception gives only `Error executing tool run_query`.
- Test client: `from mcp import Client, StdioServerParameters`. `async with Client(server) as c` connects in-process; `Client(StdioServerParameters(command=..., args=[...]))` launches a subprocess. Then `r = await c.call_tool(name, args)`, and read `r.is_error` and `r.content[0].text`. Async pytest tests use `@pytest.mark.anyio` plus an `anyio_backend` fixture that returns `"asyncio"`.
- While serving, the stdio transport points fd 1 at stderr and writes the protocol through a private duplicate. A stray `print()` inside a tool did not break the protocol.

**snowflake-connector-python 4.6.0**
- The `externalbrowser` login waits in `select.select([sock], [], [])` with no timeout. `external_browser_timeout` applies only to OAuth. The server must enforce the 2-minute limit itself.
- On an expired session, the network layer calls `connection._reauthenticate()`, which opens a new browser login and waits with no timeout (`network.py`, `_get_request` and `_post_request`). Replacing `_reauthenticate` on the connection object intercepts it.
- `cursor.execute(sql, timeout=N)` starts a client-side cancel timer. When it fires, the error message contains `SQL execution was cancelled by the client due to a timeout` (errno 604). Server-side statement timeouts use errno 630.
- `errno 250002` means the connection is closed. `390112` means the session expired and `390114` means the master token expired.
- `connect(connection_name="newrelic", **kw)` merges `kw` over the TOML section. The connector reads `~/.snowflake/connections.toml` only if `~/.snowflake/` exists. It warns when the file is readable by others.

**sqlglot 30.20.0, `dialect="snowflake"`** (`sqlglot.parse` returns a list)
- Allowed shapes: `exp.Select` (including `WITH`), `exp.Union`, `exp.Intersect`, `exp.Except` (all subclasses of `exp.SetOperation`), `exp.Show` and `exp.Describe` (`DESC`/`DESCRIBE` of a table, view, warehouse or function). Uncommon `SHOW` commands (`SHOW PARAMETERS`, `SHOW GRANTS`, `SHOW MCP SERVERS`) parse as `exp.Command` with `this == "SHOW"`.
- Refused shapes: `Use`, `Copy`, `Put`, `Delete`, `Insert`, `Update`, `Merge`, `Create`, `Drop`, `Alter`, `TruncateTable`, `Grant`, `Set`, `Transaction`, `Undrop`, `Values`, `Subquery`, `Alias` (what garbage like `SELEC * FRM t` parses to), and `Command` with `this` of `CALL`, `GET`, `EXPLAIN`, `EXECUTE` or `REMOVE`. `SELECT * INTO t2 FROM t` parses as `Select` with an `into` argument.
- Multiple statements: `SELECT 1; DELETE FROM t` gives `[Select, Delete]`. `SELECT 1; -- note` gives `[Select, Semicolon]`, `SELECT 1;;` gives `[Select, None]`, and empty or comment-only input gives `[None]`.
- Semicolons inside `'…'` or `$$…$$` strings don't split. `LIST @~` and `BEGIN … END` raise `ParseError`. All errors subclass `sqlglot.errors.SqlglotError`.
- These all parse as `Select`: `QUALIFY`, `LATERAL FLATTEN`, `::` casts, `IFF`, `ILIKE`, `PIVOT`, `SAMPLE`, `CHR()`, `INFORMATION_SCHEMA` queries, and a trailing comma before `FROM`.
- Fallbacks log a warning through the `sqlglot` logger, which goes to stderr.

**Claude Code 2.1.153**
- The default MCP tool-call timeout is 1e8 ms (about 27.8 hours). A per-server `timeout` field overrides `MCP_TOOL_TIMEOUT`. The 5- and 60-minute limits fit, so the §11 timeout risk needs no setting.
- `claude -p … --output-format stream-json --verbose` prints an `init` event first, with `tools`, `mcp_servers` (`name`, `status`) and `slash_commands`. Skills appear in `slash_commands`. The final `result` event carries `permission_denials`.
- Useful flags: `--mcp-config <file>`, `--strict-mcp-config`, `--disable-slash-commands` (turns all skills off), `--model`, `--permission-mode`, `--no-session-persistence`.
- One skill-folder scan accepts `isDirectory() || isSymbolicLink()`, so a symlinked skill folder should load. Task 23 checks.

**This machine**
- `.venv` runs Python 3.14.7 and holds only `snowflake-connector-python` 4.6.0 and `keyring`. A dry run of the pinned install adds packages and changes none.
- `~/.snowflake/` doesn't exist. `~/.claude/skills/` exists and is empty. The only user-scope MCP server is `atlassian`.
- The old `session_server.py` was running on 2026-09-30 (PID 42651) for a parallel session writing to `runs/20260930-173831-juniper-mist` (`runs/latest`).
- `.sfrun/` holds the FIFOs, `addr.sql`, `addr.tsv` (22 lines, with customer names) and leftovers `q.hhRQp5*`: two empty files and a `SELECT CURRENT_USER()` query.
- `runs/` also holds legacy folders named `YYYYMMDD-HHMMSS…`. They are not question folders.
- A parallel session measured NPM facts live on 2026-09-30 and saved them as project memories (`npm-juniper-mist-data`, `npm-meraki-data`):
  - Juniper Mist is booked outside `METRIC = 'NetworkMonitoring'`.
  - ELIA has no clustering key. One day scans in tens of seconds on XSMALL, and a month takes about 8 minutes.
  - II is small and fast.
  - `STG_ENTITIES` sits on an 84 TB raw table.
  - `IS_REPORTING` is text.
  - `SUBSCRIPTION_ACCOUNT_ID` is the `CC-…` customer contract.
  - Internal accounts sit in the "New Relic Production US/EU" orgs.

  Tasks 15, 17 and 18 use these facts.

## Plan Decisions Beyond the Spec

The spec leaves these open, or the verified facts forced them.

| # | Decision | Why |
|---|---|---|
| P1 | The server has five files: `guard.py`, `results.py`, `eventlog.py`, `connection.py` and `server.py`. | Spec §7 names three. Splitting logging and login out of `server.py` gives each file one job and its own tests. |
| P2 | The guard also allows `INTERSECT` and `MINUS`/`EXCEPT`, and `SHOW` commands that sqlglot parses as `Command('SHOW')`. It refuses `SELECT … INTO`. The server sends the user's SQL text unchanged, never sqlglot's rewrite. | Those are read-only relatives of `UNION` and `SHOW`, and the spike used `SHOW PARAMETERS`. `INTO` writes a table. |
| P3 | `connect()` runs in a daemon thread, and the tool waits at most 120 s for it. A timed-out attempt keeps listening. If the user finishes that tab later and no connection exists yet, the server keeps that connection. The next call after a timeout opens a new login. | The connector's browser wait has no timeout. Keeping a late login means it isn't wasted. §5.5 requires the reopen. |
| P4 | Two extra error codes: `LOGIN_FAILED` (the login ended with an error) and `INTERNAL_ERROR` (a bug or disk error in the server). | Otherwise Claude sees only `Error executing tool`. |
| P5 | After connecting, the server replaces `conn._reauthenticate` with a function that raises `LoginExpired`. errno 250002, 390112 and 390114 also map to `LOGIN_EXPIRED`. The server drops the dead connection. | The connector can never open a browser inside a failing query (§5.5). |
| P6 | `status()` also reports the runs folder path and how many question folders are unlearned. | From any project, Claude needs the path for `summary.md` and the updater, and the count for the five-run nudge, with no extra tool calls. |
| P7 | `allowed-tools` in `SKILL.md` adds `Read(~/Code/Snowflake/**)`, `Read(~/.claude/skills/snowflake/**)`, `Write(~/Code/Snowflake/runs/**)`, `Edit(~/Code/Snowflake/runs/**)` and `Edit(~/Code/Snowflake/skills/snowflake/references/**)`. | Answers asked from other projects write `summary.md` without a permission prompt. The live evals check that `permission_denials` is empty. |
| P8 | Pins: `snowflake-connector-python[secure-local-storage]==4.6.0`, `mcp==2.2.0`, `sqlglot==30.20.0`, `pytest==9.1.1`. | The connector is already installed, so nothing changes under the running old toolkit. The spike tested mcp 2.2.0. |
| P9 | `pytest.ini` sets `pythonpath = skills/snowflake/mcp_server tests`, and modules import each other as top-level names (`from guard import check_sql`). | `server.py` runs as a script, so sibling imports behave the same in tests and in Claude. |
| P10 | One placeholder vocabulary serves notes and evals: `company_name`, `account_id`, `start_date`, `end_date`, `search_term`, `database`, `schema`, `table`, plus the eval-only `company_a`, `company_b`, `company_c` and `npm_account_id`. | `runs/evals/values.toml` must define every name, and the check fails on any missing one. |
| P11 | The eval baseline loads the `snowflake` MCP server but turns all skills off (`--disable-slash-commands`). | That measures what the skill adds. Without the server, the baseline couldn't query at all. |
| P12 | The task that deletes the old toolkit first checks for a running `session_server.py`. If one runs, it asks the user to finish that session and never kills it. | A parallel session was using it on 2026-09-30. |
| P13 | Question folders are exactly `runs/<YYYY-MM-DD>/<question>/`. `runs/learned.txt` lists them as `YYYY-MM-DD/<question>`, one per line. `logs/`, `originals/`, `evals/` and legacy timestamp folders are never question folders. | The updater and the unlearned count need one unambiguous rule. |
| P14 | The updater tests run on the real notes in a clean git tree, with fixture runs passed through the server's `--runs-dir`. Afterwards they revert with `git checkout -- skills/snowflake/references/`. | Realistic, and nothing leaks into the committed notes. |
| P15 | The account-owner recipe drops the trailing comma before `FROM` up front. | It's harmless either way, and it removes the §11 risk. |
| P16 | Slugs for `question` and `step`: lowercase; spaces and underscores become hyphens; keep only `a-z`, `0-9` and `-`; collapse repeated hyphens and trim them from the ends; at most 60 characters. Empty becomes `question` or `query`. | `NPM devices by type` becomes `npm-devices-by-type`, not `npmdevicesbytype`. |
| P17 | Each log line starts with local ISO time and `pid=<n>`. | Every window's server writes to the same daily log. The pid tells windows apart for the one-login check. |
| P18 | Headless test windows use `--model haiku` for mechanical checks (setup, logins) and `--model sonnet` for evals and updater tests. | Mechanical checks stay cheap, and the realistic tests run on a strong model. |

## Review Focus

These are inputs the spec implies but its tests don't exercise, most likely first. Each has a test in the task named.

1. **Parallel queries in one question folder.** `SKILL.md` tells Claude to run independent queries in parallel, so two `run_query` calls can number files in the same folder at the same moment. Each must get its own `NN` and never overwrite the other's files. Task 4 tests 20 threads.
2. **Real Snowflake read syntax passes the guard.** `QUALIFY`, `LATERAL FLATTEN`, `::` casts, `ILIKE`, `PIVOT`, `SAMPLE`, `$$…$$` strings, a trailing `;` and a trailing `-- comment` must be allowed. A false `BLOCKED` stops real questions. Task 3.
3. **`status()` during a pending login.** It must answer at once with "login in progress" instead of waiting up to 2 minutes behind the login. Tasks 9 and 11.
4. **Odd question names.** `../../etc`, `Ünïcode Şirket`, an emoji, an empty string and a 300-character string must each give a safe folder name inside `runs/`. Task 4.
5. **Empty results.** A zero-row result writes a header-only CSV and reports `0 rows`. A statement with no result columns writes an empty CSV without crashing. Tasks 5 and 6.

## File Map

| Path | Job | Tasks |
|---|---|---|
| `requirements.txt` | Pinned dependencies (P8) | 1 |
| `pytest.ini` | Test paths (P9) | 2 |
| `.gitignore` | Add Python caches; later drop the old toolkit's entries | 2, 25 |
| `skills/snowflake/mcp_server/guard.py` | Read-only guard | 3 |
| `skills/snowflake/mcp_server/results.py` | Question folders, file numbering, CSV, preview, unlearned count | 4–7 |
| `skills/snowflake/mcp_server/eventlog.py` | Daily event log | 8 |
| `skills/snowflake/mcp_server/connection.py` | Lazy login, login timeout, expired sessions, error codes | 9–10 |
| `skills/snowflake/mcp_server/server.py` | MCP tools and entry point | 11–12 |
| `tests/test_*.py` | Unit tests, one file per module or script | 3–14, 21 |
| `tests/fakes.py` | Fake Snowflake connector | 9 |
| `tests/fake_server_main.py`, `tests/test_stdio.py` | Real-stdio test with the fake connector | 13 |
| `tests/check_notes.py` | Knowledge checks (§10.2) | 14 |
| `skills/snowflake/references/*.md` | `finding-data`, `billing`, `customers`, `npm`, `tables`, `updater` | 15–19 |
| `skills/snowflake/SKILL.md` | Main skill document, moved from `Snowflake.md` | 20 |
| `skills/snowflake/evals/evals.md`, `tests/run_eval.py` | End-to-end eval prompts and their headless runner (§10.4) | 21 |
| `tests/check_install.py` | Checks the skill and server load, without a login | 23 |
| `README.md` | Rewritten | 26 |
| `tests/live_login_check.py` | Live login checks (§10.3) | 27 |
| `tests/fixtures/runs/` | Made-up runs for the updater tests | 31 |

Outside git: `~/.snowflake/connections.toml` (Task 22); the `~/.claude/skills/snowflake` link and the user-scope MCP registration (Task 23); `runs/originals/` (Task 24); `runs/evals/` (Tasks 21 and 27–30). Deleted in Task 25: `CLAUDE.md`, `session_server.py`, `q`, `.sfrun/`.

### Shared interfaces

Later tasks rely on these exact names.

```python
# guard.py
class Blocked(Exception): ...                      # str(exc) says why
def check_sql(sql: str) -> str: ...                 # "SELECT" | "SHOW" | "DESCRIBE", else raises Blocked

# results.py
def slugify(text: str, fallback: str) -> str: ...
def question_dir(runs_dir: Path, question: str, today: date | None = None) -> Path: ...   # creates it
def save_query(folder: Path, step: str, sql: str) -> tuple[Path, Path]: ...               # (sql_path, csv_path)
@dataclass
class CsvResult:
    row_count: int
    truncated: bool
    preview: list[tuple]
def write_csv(csv_path: Path, columns: list[str], rows: Iterable[Sequence], max_rows: int,
              preview_rows: int = 50) -> CsvResult: ...
def format_preview(columns: list[str], rows: list[tuple], max_cell: int = 200) -> str: ...
def format_result(*, columns: list[str], result: CsvResult, elapsed: float, query_id: str | None,
                  sql_path: Path, csv_path: Path, max_rows: int) -> str: ...
def unlearned_folders(runs_dir: Path) -> list[str]: ...    # ["2026-10-01/npm-devices-by-type", ...]

# eventlog.py
class EventLog:
    def __init__(self, logs_dir: Path) -> None: ...
    def write(self, event: str, **fields: object) -> None: ...   # never raises

# connection.py
class LoginTimeout(Exception): ...
class LoginFailed(Exception): ...
class LoginExpired(Exception): ...
class LazyConnection:
    def __init__(self, connect: Callable[[], Any], login_timeout: float = 120.0,
                 log: EventLog | None = None) -> None: ...
    def get(self) -> Any: ...            # the live connection; logs in on first use
    def state(self) -> dict: ...         # never blocks: {"state": "logged_out"|"logging_in"|"logged_in", ...}
    def discard(self, conn: Any) -> None: ...
def default_connect() -> Any: ...        # imports snowflake.connector lazily
def classify_error(exc: BaseException) -> tuple[str, str]: ...    # (code, message)

# server.py
def build_server(runs_dir: Path, connection: LazyConnection, log: EventLog) -> MCPServer: ...
def main(argv: list[str] | None = None) -> None: ...     # --runs-dir overrides <repo>/runs
```

### Task index

| Phase | Tasks |
|---|---|
| A. Foundation | 1 Dependencies · 2 Test config |
| B. MCP server | 3 Guard · 4 Question folders · 5 CSV writer · 6 Preview · 7 Unlearned count · 8 Event log · 9 Lazy login · 10 Expired sessions and error codes · 11 `status` tool · 12 `run_query` tool · 13 Real-stdio test |
| C. Knowledge | 14 Knowledge-check script · 15 `finding-data.md` · 16 `billing.md` · 17 `customers.md` · 18 `npm.md` · 19 `tables.md` and `updater.md` · 20 `SKILL.md` · 21 Evals |
| D. Install | 22 Settings file · 23 Register and link |
| E. Migration | 24 Move originals · 25 Retire the old toolkit · 26 README |
| F. Live checks (**LIVE**) | 27 Login checks and eval values · 28 Knowledge checks · 29 Evals E1–E5 · 30 Evals E6–E10 · 31 Updater fixtures (not live) · 32 Updater pass · 33 Size limit · 34 Speed check · 35 Pass criteria |

---

## Tasks

### Task 1: Pinned dependencies

**Files:**
- Create: `requirements.txt`

**Interfaces:**
- Produces: `.venv` with `mcp` 2.2.0, `sqlglot` 30.20.0 and `pytest` 9.1.1 next to the installed connector 4.6.0.

- [ ] **Step 1: Write `requirements.txt`**

```text
# Pinned for the repo's .venv (Python 3.14). See plan decision P8.
snowflake-connector-python[secure-local-storage]==4.6.0
mcp==2.2.0
sqlglot==30.20.0
pytest==9.1.1
```

- [ ] **Step 2: Dry-run the install**

Run: `.venv/bin/pip install --dry-run --disable-pip-version-check -r requirements.txt | grep "Would install"`
Expected: a list of new packages that doesn't include `snowflake-connector-python` or `keyring`, since the running old toolkit uses those. If either appears, stop and report it.

- [ ] **Step 3: Install**

Run: `.venv/bin/pip install --disable-pip-version-check -r requirements.txt`
Expected: ends with `Successfully installed …`.

- [ ] **Step 4: Verify versions and the mcp 2.x import**

Run: `.venv/bin/python -c "import importlib.metadata as m; from mcp.server.mcpserver import MCPServer; print(*(m.version(p) for p in ['snowflake-connector-python', 'mcp', 'sqlglot', 'pytest']))"`
Expected: `4.6.0 2.2.0 30.20.0 9.1.1`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "Pin the Snowflake skill's Python dependencies"
```

### Task 2: Test configuration

**Files:**
- Create: `pytest.ini`
- Modify: `.gitignore` (append two entries)

**Interfaces:**
- Produces: `pytest` collects `tests/`, and test files import server modules as top-level names (`from guard import check_sql`) and test helpers as `from fakes import …`.

- [ ] **Step 1: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = skills/snowflake/mcp_server tests
```

- [ ] **Step 2: Append Python caches to `.gitignore`**

Add these lines at the end of `.gitignore`. Don't remove existing lines yet; Task 25 does that.

```gitignore

# Python caches
__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Check pytest reads the config**

Run: `mkdir -p tests && .venv/bin/python -m pytest`
Expected: `no tests ran`, exit code 5. That's correct, since there are no tests yet. The header line shows `configfile: pytest.ini`.

- [ ] **Step 4: Commit**

```bash
git add pytest.ini .gitignore
git commit -m "Add pytest config and ignore Python caches"
```

### Task 3: Read-only guard

**Files:**
- Create: `skills/snowflake/mcp_server/guard.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `sqlglot` 30.20.0.
- Produces: `class Blocked(Exception)`, whose `str()` says why, and `check_sql(sql: str) -> str`, which returns `"SELECT"`, `"SHOW"` or `"DESCRIBE"` or raises `Blocked`.

- [ ] **Step 1: Write the failing test** — `tests/test_guard.py`. It covers spec §10.1 (Guard, Semicolons) and Review Focus 2.

```python
import pytest

from guard import Blocked, check_sql

ALLOWED = {
    "select": ("SELECT 1", "SELECT"),
    "with": ("WITH a AS (SELECT 1 AS x) SELECT * FROM a", "SELECT"),
    "union": ("SELECT 1 UNION ALL SELECT 2", "SELECT"),
    "intersect": ("SELECT 1 INTERSECT SELECT 1", "SELECT"),
    "minus": ("SELECT 1 MINUS SELECT 2", "SELECT"),
    "show": ("SHOW TABLES IN SCHEMA TRANSFORMED.SALES", "SHOW"),
    "show_parsed_as_command": ("SHOW PARAMETERS LIKE 'ALLOW_ID_TOKEN' IN ACCOUNT", "SHOW"),
    "describe": ("DESCRIBE TABLE CONFORMED.SFDC.STG_SFDC_ACCOUNT", "DESCRIBE"),
    "desc_view": ("DESC VIEW CONFORMED.ENTITIES.STG_ENTITIES", "DESCRIBE"),
    # Review Focus 2: real Snowflake read syntax must pass.
    "qualify": ("SELECT a, ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) rn FROM t QUALIFY rn = 1", "SELECT"),
    "flatten": ("SELECT f.value FROM t, LATERAL FLATTEN(input => t.v) f", "SELECT"),
    "cast_iff_ilike": ("SELECT x::DATE, IFF(a ILIKE '%y%', 1, 0) FROM t", "SELECT"),
    "pivot": ("SELECT * FROM t PIVOT(SUM(amount) FOR month IN ('JAN', 'FEB')) AS p", "SELECT"),
    "sample": ("SELECT * FROM t SAMPLE (1) LIMIT 10", "SELECT"),
    "dollar_string": ("SELECT $$a;b$$", "SELECT"),
    "trailing_semicolon": ("SELECT 1;", "SELECT"),
    "trailing_comment": ("SELECT 1; -- note", "SELECT"),
    "semicolon_in_string": ("SELECT 'x; DROP TABLE t' AS y", "SELECT"),
}


@pytest.mark.parametrize("sql,kind", ALLOWED.values(), ids=ALLOWED.keys())
def test_allows_single_reads(sql, kind):
    assert check_sql(sql) == kind


REFUSED = {
    "delete": ("DELETE FROM t WHERE 1=1", "Delete"),
    "insert": ("INSERT INTO t SELECT 1", "Insert"),
    "update": ("UPDATE t SET a = 1", "Update"),
    "merge": ("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.a = s.a", "Merge"),
    "create": ("CREATE TABLE t AS SELECT 1", "Create"),
    "drop": ("DROP TABLE t", "Drop"),
    "alter": ("ALTER TABLE t ADD COLUMN c INT", "Alter"),
    "truncate": ("TRUNCATE TABLE t", "TruncateTable"),
    "grant": ("GRANT SELECT ON TABLE t TO ROLE r", "Grant"),
    "use": ("USE WAREHOUSE X", "Use"),
    "call": ("CALL my_proc(1)", "CALL"),
    "copy": ("COPY INTO t FROM @stage", "Copy"),
    "put": ("PUT file:///tmp/x.csv @~/stage", "Put"),
    "get": ("GET @~/stage file:///tmp/", "GET"),
    "explain": ("EXPLAIN SELECT 1", "EXPLAIN"),
    "select_into": ("SELECT * INTO t2 FROM t", "INTO"),
    "two_statements": ("SELECT 1; DELETE FROM t", "2 statements"),
    "write_after_comment": ("SELECT 1; -- hi\nDELETE FROM t", "2 statements"),
    "write_behind_comment": ("/* SELECT */ DELETE FROM t", "Delete"),
    "unparseable": ("BEGIN DELETE FROM t; END", "could not parse"),
    "garbage": ("SELEC * FRM t", "Alias"),
    "empty": ("", "no statement"),
    "only_comment": ("-- nothing", "no statement"),
}


@pytest.mark.parametrize("sql,reason", REFUSED.values(), ids=REFUSED.keys())
def test_refuses_everything_else(sql, reason):
    with pytest.raises(Blocked) as exc:
        check_sql(sql)
    assert reason in str(exc.value)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_guard.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'guard'`.

- [ ] **Step 3: Write the implementation** — `skills/snowflake/mcp_server/guard.py`

```python
"""Read-only guard: only single SELECT, SHOW and DESCRIBE statements may reach Snowflake."""
import logging

import sqlglot
from sqlglot import exp

# sqlglot warns on stderr whenever it falls back to a generic Command; the guard handles those.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

ALLOWED_HINT = "Only single SELECT, SHOW and DESCRIBE statements are allowed."


class Blocked(Exception):
    """The statement must not reach Snowflake. str(exc) says why."""


def check_sql(sql: str) -> str:
    """Return "SELECT", "SHOW" or "DESCRIBE" for an allowed statement; raise Blocked otherwise."""
    try:
        parsed = sqlglot.parse(sql, dialect="snowflake")
    except sqlglot.errors.SqlglotError as exc:
        first_line = str(exc).splitlines()[0]
        raise Blocked(f"could not parse the statement ({first_line}). {ALLOWED_HINT}") from None
    statements = [s for s in parsed if s is not None and not isinstance(s, exp.Semicolon)]
    if not statements:
        raise Blocked(f"no statement found. {ALLOWED_HINT}")
    if len(statements) > 1:
        raise Blocked(f"{len(statements)} statements found; send exactly one. {ALLOWED_HINT}")
    stmt = statements[0]
    if isinstance(stmt, exp.Select) and stmt.args.get("into"):
        raise Blocked(f"SELECT ... INTO writes a table. {ALLOWED_HINT}")
    if isinstance(stmt, (exp.Select, exp.SetOperation)):
        return "SELECT"
    if isinstance(stmt, exp.Show):
        return "SHOW"
    if isinstance(stmt, exp.Describe):
        return "DESCRIBE"
    kind = str(stmt.this).upper() if isinstance(stmt, exp.Command) else type(stmt).__name__
    if kind == "SHOW":
        return "SHOW"
    raise Blocked(f"{kind} statements are not allowed. {ALLOWED_HINT}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_guard.py -q`
Expected: `41 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/guard.py tests/test_guard.py
git commit -m "Add the read-only SQL guard"
```

### Task 4: Question folders and SQL files

**Files:**
- Create: `skills/snowflake/mcp_server/results.py`
- Test: `tests/test_results.py`

**Interfaces:**
- Produces: `slugify(text: str, fallback: str) -> str`, `question_dir(runs_dir: Path, question: str, today: date | None = None) -> Path` (creates the folder) and `save_query(folder: Path, step: str, sql: str) -> tuple[Path, Path]`, which returns `(sql_path, csv_path)` and writes only the SQL. Tasks 5–7 add to this same file.

- [ ] **Step 1: Write the failing test** — `tests/test_results.py`. It covers spec §10.1 (File names), P16 and Review Focus 1 and 4.

```python
import threading
from datetime import date

from results import question_dir, save_query, slugify


def test_slugify_keeps_letters_digits_and_single_hyphens():
    assert slugify("NPM devices by type", "question") == "npm-devices-by-type"
    assert slugify("  Devices__by--Type!! ", "question") == "devices-by-type"


def test_slugify_makes_odd_names_safe():  # Review Focus 4
    assert slugify("../../etc", "question") == "etc"
    assert slugify("Ünïcode Şirket", "question") == "unicode-sirket"
    assert slugify("🚀", "question") == "question"
    assert slugify("", "query") == "query"
    assert slugify("a" * 300, "question") == "a" * 60


def test_question_dir_uses_local_date_and_slug(tmp_path):
    folder = question_dir(tmp_path, "NPM devices by type", today=date(2026, 10, 1))
    assert folder == tmp_path / "2026-10-01" / "npm-devices-by-type"
    assert folder.is_dir()


def test_question_dir_stays_inside_runs(tmp_path):  # Review Focus 4
    folder = question_dir(tmp_path, "../../etc", today=date(2026, 10, 1))
    assert folder.resolve().is_relative_to(tmp_path.resolve())


def test_save_query_numbers_files_and_saves_sql(tmp_path):
    first = save_query(tmp_path, "devices", "SELECT 1")
    second = save_query(tmp_path, "By Type", "SELECT 2;\n\n")
    assert [p.name for p in first] == ["01-devices.sql", "01-devices.csv"]
    assert [p.name for p in second] == ["02-by-type.sql", "02-by-type.csv"]
    assert first[0].read_text() == "SELECT 1\n"
    assert second[0].read_text() == "SELECT 2;\n"
    assert not first[1].exists()  # only a successful query writes its CSV


def test_save_query_continues_past_99(tmp_path):
    (tmp_path / "99-old.sql").write_text("SELECT 1\n")
    assert save_query(tmp_path, "next", "SELECT 2")[0].name == "100-next.sql"


def test_parallel_saves_get_distinct_numbers(tmp_path):  # Review Focus 1
    barrier = threading.Barrier(20)
    names = []

    def work(i):
        barrier.wait()
        names.append(save_query(tmp_path, f"step{i}", f"SELECT {i}")[0].name)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(int(n.split("-")[0]) for n in names) == list(range(1, 21))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'results'`.

- [ ] **Step 3: Write the implementation** — `skills/snowflake/mcp_server/results.py`

```python
"""Result files: one folder per question under runs/, numbered SQL and CSV files, previews."""
import fcntl
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

MAX_SLUG = 60
_NUMBERED = re.compile(r"^(\d+)-")


def slugify(text: str, fallback: str) -> str:
    """Lowercase ASCII slug: spaces and underscores become hyphens; only a-z, 0-9 and single hyphens stay."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[\s_]+", "-", ascii_text.lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:MAX_SLUG].rstrip("-") or fallback


def question_dir(runs_dir: Path, question: str, today: date | None = None) -> Path:
    """Create and return runs/<YYYY-MM-DD>/<question-slug>/, using the local date."""
    day = (today or date.today()).isoformat()
    folder = Path(runs_dir) / day / slugify(question, "question")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_query(folder: Path, step: str, sql: str) -> tuple[Path, Path]:
    """Save the SQL as NN-<step>.sql with the next free number; return (sql_path, csv_path).

    A lock on the folder keeps numbers unique when queries run in parallel, even across windows.
    """
    name = slugify(step, "query")
    lock_fd = os.open(folder, os.O_RDONLY)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        used = [int(m.group(1)) for p in folder.iterdir() if (m := _NUMBERED.match(p.name))]
        sql_path = folder / f"{max(used, default=0) + 1:02d}-{name}.sql"
        sql_path.write_text(sql.rstrip() + "\n", encoding="utf-8")
    finally:
        os.close(lock_fd)  # closing the descriptor releases the lock
    return sql_path, sql_path.with_suffix(".csv")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `7 passed`. Run the parallel test three more times with `-k parallel`. It must pass every time.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/results.py tests/test_results.py
git commit -m "Add question folders and numbered SQL files"
```

### Task 5: CSV writer

**Files:**
- Modify: `skills/snowflake/mcp_server/results.py`
- Test: `tests/test_results.py`

**Interfaces:**
- Consumes: `results.py` from Task 4.
- Produces: `CsvResult(row_count: int, truncated: bool, preview: list[tuple])` and `write_csv(csv_path: Path, columns: list[str], rows: Iterable[Sequence], max_rows: int, preview_rows: int = 50) -> CsvResult`. `preview` holds the first `preview_rows` raw rows.

- [ ] **Step 1: Write the failing tests**

Replace the import lines at the top of `tests/test_results.py` with:

```python
import csv
import threading
from datetime import date, datetime
from decimal import Decimal

from results import question_dir, save_query, slugify, write_csv
```

Append to `tests/test_results.py`. This covers spec §10.1 (CSV round-trip, Large results) and Review Focus 5.

```python

TRICKY = [
    ("a,b", 'say "hi"', "tab\there", "line\nbreak", None, "Demirören Teknoloji Şirketi"),
    (Decimal("1.50"), datetime(2026, 9, 30, 14, 5), True, b"\x00\xff", 42, ""),
]


def read_back(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_csv_round_trip_keeps_tricky_values(tmp_path):
    path = tmp_path / "01-q.csv"
    result = write_csv(path, ["c1", "c2", "c3", "c4", "c5", "c6"], iter(TRICKY), max_rows=100)
    rows = read_back(path)
    assert rows[0] == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert rows[1] == ["a,b", 'say "hi"', "tab\there", "line\nbreak", "", "Demirören Teknoloji Şirketi"]
    assert rows[2] == ["1.50", "2026-09-30 14:05:00", "True", "00ff", "42", ""]
    assert (result.row_count, result.truncated) == (2, False)
    assert result.preview == TRICKY


def test_large_result_writes_every_row_and_keeps_a_50_row_preview(tmp_path):
    path = tmp_path / "01-big.csv"
    result = write_csv(path, ["n"], ((i,) for i in range(5000)), max_rows=100000)
    assert len(read_back(path)) == 5001
    assert (result.row_count, result.truncated, len(result.preview)) == (5000, False, 50)


def test_max_rows_truncates_the_csv(tmp_path):
    path = tmp_path / "01-big.csv"
    result = write_csv(path, ["n"], ((i,) for i in range(150)), max_rows=100)
    assert len(read_back(path)) == 101
    assert (result.row_count, result.truncated) == (100, True)


def test_exactly_max_rows_is_not_truncated(tmp_path):
    result = write_csv(tmp_path / "01-x.csv", ["n"], ((i,) for i in range(100)), max_rows=100)
    assert (result.row_count, result.truncated) == (100, False)


def test_zero_rows_writes_a_header_only_csv(tmp_path):  # Review Focus 5
    path = tmp_path / "01-none.csv"
    result = write_csv(path, ["a", "b"], iter([]), max_rows=10)
    assert read_back(path) == [["a", "b"]]
    assert (result.row_count, result.truncated, result.preview) == (0, False, [])


def test_no_result_columns_writes_an_empty_csv(tmp_path):  # Review Focus 5
    path = tmp_path / "01-nothing.csv"
    result = write_csv(path, [], iter([]), max_rows=10)
    assert path.read_text() == ""
    assert result.row_count == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `ImportError: cannot import name 'write_csv' from 'results'`.

- [ ] **Step 3: Write the implementation**

At the top of `results.py`, add `import csv` before `import fcntl`, and add these two lines before `from datetime import date`:

```python
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
```

Append to `results.py`:

```python

@dataclass
class CsvResult:
    row_count: int
    truncated: bool
    preview: list[tuple]


def _cell(value):
    """NULL becomes empty and bytes become hex; csv writes everything else with str()."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def write_csv(csv_path: Path, columns: list[str], rows: Iterable[Sequence], max_rows: int,
              preview_rows: int = 50) -> CsvResult:
    """Stream rows into a UTF-8 CSV with a header row, stopping after max_rows."""
    count, truncated, preview = 0, False, []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if not columns:  # the statement returned no result columns
            return CsvResult(0, False, [])
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            if count == max_rows:
                truncated = True
                break
            writer.writerow([_cell(v) for v in row])
            if count < preview_rows:
                preview.append(tuple(row))
            count += 1
    return CsvResult(count, truncated, preview)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `13 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/results.py tests/test_results.py
git commit -m "Stream query results into CSV files"
```

### Task 6: Preview and result text

**Files:**
- Modify: `skills/snowflake/mcp_server/results.py`
- Test: `tests/test_results.py`

**Interfaces:**
- Consumes: `CsvResult` from Task 5.
- Produces: `format_preview(columns: list[str], rows: list[tuple], max_cell: int = 200) -> str` and `format_result(*, columns, result, elapsed, query_id, sql_path, csv_path, max_rows) -> str`. The first line of the result text is `Rows: N | Columns: N | Seconds: N.NN | Query ID: <id or unknown>`.

- [ ] **Step 1: Write the failing tests**

Change the `from results import …` line in `tests/test_results.py` to:

```python
from results import CsvResult, format_preview, format_result, question_dir, save_query, slugify, write_csv
```

Append to `tests/test_results.py`. This covers spec §5.2 (the returned text) and Review Focus 5.

```python

def test_preview_escapes_tabs_and_line_breaks_and_shows_nulls():
    text = format_preview(["a", "b"], [("x\ty", "line1\nline2\r"), (None, "back\\slash")])
    assert text.splitlines() == ["a\tb", "x\\ty\tline1\\nline2\\r", "NULL\tback\\\\slash"]


def test_preview_shortens_long_cells_to_200_characters():
    cell = format_preview(["a"], [("z" * 500,)]).splitlines()[1]
    assert len(cell) == 200
    assert cell.endswith("…")


def test_result_text_has_header_paths_and_preview(tmp_path):
    result = CsvResult(row_count=2, truncated=False, preview=[(1, "a"), (2, "b")])
    text = format_result(columns=["n", "s"], result=result, elapsed=1.234, query_id="01abc",
                         sql_path=tmp_path / "01-q.sql", csv_path=tmp_path / "01-q.csv", max_rows=100000)
    lines = text.splitlines()
    assert lines[0] == "Rows: 2 | Columns: 2 | Seconds: 1.23 | Query ID: 01abc"
    assert lines[1] == f"SQL: {tmp_path / '01-q.sql'}"
    assert lines[2] == f"CSV: {tmp_path / '01-q.csv'}"
    assert lines[3] == "Preview (2 of 2 rows):"
    assert lines[4:] == ["n\ts", "1\ta", "2\tb"]


def test_result_text_notes_truncation(tmp_path):
    result = CsvResult(row_count=100, truncated=True, preview=[(i,) for i in range(50)])
    text = format_result(columns=["n"], result=result, elapsed=0.5, query_id="q1",
                         sql_path=tmp_path / "a.sql", csv_path=tmp_path / "a.csv", max_rows=100)
    assert "Preview (50 of 100 rows):" in text
    assert text.splitlines()[-1] == ("Note: the CSV stopped at max_rows=100. More rows exist; "
                                     "narrow the query or raise max_rows.")


def test_result_text_for_zero_rows(tmp_path):  # Review Focus 5
    result = CsvResult(row_count=0, truncated=False, preview=[])
    text = format_result(columns=["a"], result=result, elapsed=0.1, query_id=None,
                         sql_path=tmp_path / "a.sql", csv_path=tmp_path / "a.csv", max_rows=10)
    assert text.splitlines()[0] == "Rows: 0 | Columns: 1 | Seconds: 0.10 | Query ID: unknown"
    assert text.splitlines()[-1] == "Preview: no rows."
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `ImportError: cannot import name 'format_preview' from 'results'`.

- [ ] **Step 3: Write the implementation** — append to `results.py`:

```python

def _preview_cell(value, max_cell: int) -> str:
    if value is None:
        return "NULL"
    text = value.hex() if isinstance(value, (bytes, bytearray)) else str(value)
    text = text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
    return text if len(text) <= max_cell else text[: max_cell - 1] + "…"


def format_preview(columns: list[str], rows: list[tuple], max_cell: int = 200) -> str:
    """Tab-separated header and rows. NULL shows as NULL; tabs and line breaks are escaped."""
    lines = ["\t".join(_preview_cell(c, max_cell) for c in columns)]
    lines += ["\t".join(_preview_cell(v, max_cell) for v in row) for row in rows]
    return "\n".join(lines)


def format_result(*, columns: list[str], result: CsvResult, elapsed: float, query_id: str | None,
                  sql_path: Path, csv_path: Path, max_rows: int) -> str:
    """The text that run_query returns to Claude."""
    lines = [
        f"Rows: {result.row_count} | Columns: {len(columns)} | Seconds: {elapsed:.2f}"
        f" | Query ID: {query_id or 'unknown'}",
        f"SQL: {sql_path}",
        f"CSV: {csv_path}",
    ]
    if result.preview:
        lines.append(f"Preview ({len(result.preview)} of {result.row_count} rows):")
        lines.append(format_preview(columns, result.preview))
    else:
        lines.append("Preview: no rows.")
    if result.truncated:
        lines.append(f"Note: the CSV stopped at max_rows={max_rows}. More rows exist; "
                     "narrow the query or raise max_rows.")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `18 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/results.py tests/test_results.py
git commit -m "Format the query preview and result text"
```

### Task 7: Unlearned-run count

**Files:**
- Modify: `skills/snowflake/mcp_server/results.py`
- Test: `tests/test_results.py`

**Interfaces:**
- Produces: `unlearned_folders(runs_dir: Path) -> list[str]`, sorted, as `YYYY-MM-DD/<question>` (P13). Task 11 reports its length in `status()` (P6).

- [ ] **Step 1: Write the failing tests**

Change the `from results import …` line in `tests/test_results.py` to:

```python
from results import (CsvResult, format_preview, format_result, question_dir, save_query, slugify,
                     unlearned_folders, write_csv)
```

Append to `tests/test_results.py`:

```python

def test_unlearned_folders_lists_question_folders_not_yet_learned(tmp_path):
    for rel in ["2026-10-01/npm-devices", "2026-10-01/ae-lookup", "2026-10-02/billing-addresses"]:
        (tmp_path / rel).mkdir(parents=True)
    for other in ["logs", "originals", "evals", "20260930-173831-juniper-mist"]:  # never question folders
        (tmp_path / other).mkdir()
    (tmp_path / "2026-10-01" / "stray.txt").write_text("x")
    (tmp_path / "learned.txt").write_text("2026-10-01/ae-lookup\n\n")
    assert unlearned_folders(tmp_path) == ["2026-10-01/npm-devices", "2026-10-02/billing-addresses"]


def test_unlearned_folders_without_a_runs_folder(tmp_path):
    assert unlearned_folders(tmp_path / "missing") == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `ImportError: cannot import name 'unlearned_folders' from 'results'`.

- [ ] **Step 3: Write the implementation** — append to `results.py`:

```python

_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def unlearned_folders(runs_dir: Path) -> list[str]:
    """Question folders (runs/<YYYY-MM-DD>/<question>/) that runs/learned.txt doesn't list yet."""
    runs_dir = Path(runs_dir)
    learned_file = runs_dir / "learned.txt"
    learned = set(learned_file.read_text(encoding="utf-8").split()) if learned_file.exists() else set()
    found = {
        f"{day.name}/{question.name}"
        for day in runs_dir.glob("*") if day.is_dir() and _DAY.match(day.name)
        for question in day.iterdir() if question.is_dir()
    }
    return sorted(found - learned)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_results.py -q`
Expected: `20 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/results.py tests/test_results.py
git commit -m "Count question folders the updater has not learned from"
```

### Task 8: Event log

**Files:**
- Create: `skills/snowflake/mcp_server/eventlog.py`
- Test: `tests/test_eventlog.py`

**Interfaces:**
- Produces: `EventLog(logs_dir: Path)` with `write(event: str, **fields) -> None`, which never raises. Lines look like `2026-10-01T14:59:52 pid=4242 logged_in seconds=21.39` (P17). Later tasks use these event names: `server_started`, `login_started`, `logged_in`, `login_timeout`, `login_failed`, `query_finished` and `query_failed` (with `code=`, so an expiry is `query_failed code=LOGIN_EXPIRED`).

- [ ] **Step 1: Write the failing test** — `tests/test_eventlog.py`

```python
import os
import re
from datetime import date

from eventlog import EventLog


def test_write_appends_one_line_per_event_with_time_and_pid(tmp_path):
    log = EventLog(tmp_path / "logs")
    log.write("server_started")
    log.write("logged_in", seconds=21.391, note="two\nlines")
    lines = (tmp_path / "logs" / f"{date.today().isoformat()}.log").read_text().splitlines()
    assert len(lines) == 2
    assert re.fullmatch(rf"\d{{4}}-\d\d-\d\dT\d\d:\d\d:\d\d pid={os.getpid()} server_started", lines[0])
    assert lines[1].endswith(f"pid={os.getpid()} logged_in seconds=21.39 note=two lines")


def test_write_never_raises(tmp_path):
    blocker = tmp_path / "logs"
    blocker.write_text("a file where the folder should be")
    EventLog(blocker).write("server_started")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eventlog.py -q`
Expected: `ModuleNotFoundError: No module named 'eventlog'`.

- [ ] **Step 3: Write the implementation** — `skills/snowflake/mcp_server/eventlog.py`

```python
"""Append-only event log: runs/logs/<YYYY-MM-DD>.log, one line per event. Never query results."""
import os
import threading
from datetime import datetime
from pathlib import Path


class EventLog:
    def __init__(self, logs_dir: Path) -> None:
        self._dir = Path(logs_dir)
        self._lock = threading.Lock()

    def write(self, event: str, **fields: object) -> None:
        """Append `<local time> pid=<n> <event> key=value …`. Logging must never break a query."""
        now = datetime.now()
        parts = [now.strftime("%Y-%m-%dT%H:%M:%S"), f"pid={os.getpid()}", event]
        for key, value in fields.items():
            text = f"{value:.2f}" if isinstance(value, float) else str(value)
            parts.append(f"{key}={text.replace(chr(10), ' ')}")
        try:
            with self._lock:
                self._dir.mkdir(parents=True, exist_ok=True)
                with open(self._dir / f"{now:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
                    f.write(" ".join(parts) + "\n")
        except OSError:
            pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eventlog.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/eventlog.py tests/test_eventlog.py
git commit -m "Add the daily MCP server event log"
```

### Task 9: Lazy login

**Files:**
- Create: `skills/snowflake/mcp_server/connection.py`
- Create: `tests/fakes.py` (the fake connector; Tasks 10–13 reuse it)
- Test: `tests/test_connection.py`

**Interfaces:**
- Consumes: `EventLog` from Task 8.
- Produces: `LoginTimeout`, `LoginFailed` and `LoginExpired` (all `Exception`), and `LazyConnection(connect, login_timeout=120.0, log=None)` with `get()` and `state()`. `state()` never blocks and returns `{"state": "logged_out"}`, `{"state": "logging_in", "seconds_left": n}` or `{"state": "logged_in", "user", "role", "warehouse"}`. In `tests/fakes.py`: `FakeConnector(delay=0.0, error=None, prints=None)`, a callable that counts `calls` and keeps `connections`; and `FakeConnection`, whose `result = (columns, rows)` and `fail_with = exception` drive the next query, with `executed` recording `(sql, timeout)`.
- Design: P3. The connector's browser wait has no timeout, so `connect()` runs in a daemon thread while `get()` waits at most `login_timeout`. The lock is never held while waiting, which is why `state()` stays instant (Review Focus 3).

- [ ] **Step 1: Write the fake connector** — `tests/fakes.py`

```python
"""A fake Snowflake connector for tests: no network, no browser."""
import time


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.sfqid = None
        self._rows = iter(())

    def execute(self, sql, timeout=None):
        self.conn.executed.append((sql, timeout))
        if self.conn.fail_with is not None:
            raise self.conn.fail_with
        columns, rows = self.conn.result
        self.description = [(name,) for name in columns] or None
        self.sfqid = f"fake-query-{len(self.conn.executed)}"
        self._rows = iter(rows)
        return self

    def __iter__(self):
        return self._rows

    def close(self):
        pass


class FakeConnection:
    user, role, warehouse = "JKARNIK", "FR_PRODUCT_ANALYST", "TEAM_PRODUCT_ANALYST_XSMALL"

    def __init__(self):
        self.executed = []                  # (sql, timeout) per execute()
        self.result = (["N"], [(1,)])       # (column names, rows) the next query returns
        self.fail_with = None               # an exception the next query raises
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class FakeConnector:
    """Stands in for snowflake.connector.connect: counts logins, and can be slow, fail or print."""

    def __init__(self, delay=0.0, error=None, prints=None):
        self.delay, self.error, self.prints = delay, error, prints
        self.calls = 0
        self.connections = []

    def __call__(self):
        self.calls += 1
        delay, error = self.delay, self.error
        if self.prints:
            print(self.prints)              # the real connector prints its login URL
        time.sleep(delay)
        if error is not None:
            raise error
        conn = FakeConnection()
        self.connections.append(conn)
        return conn
```

- [ ] **Step 2: Write the failing test** — `tests/test_connection.py`. It covers spec §10.1 (Lazy login, Clean output) and Review Focus 3.

```python
import threading
import time

import pytest

from connection import LazyConnection, LoginFailed, LoginTimeout
from eventlog import EventLog
from fakes import FakeConnector


def test_nothing_connects_before_the_first_get():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    assert lazy.state() == {"state": "logged_out"}
    assert connector.calls == 0


def test_first_get_logs_in_once_and_reuses_the_connection():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    first = lazy.get()
    assert lazy.get() is first
    assert connector.calls == 1
    assert lazy.state() == {"state": "logged_in", "user": "JKARNIK", "role": "FR_PRODUCT_ANALYST",
                            "warehouse": "TEAM_PRODUCT_ANALYST_XSMALL"}


def test_concurrent_first_calls_log_in_once():
    connector = FakeConnector(delay=0.2)
    lazy = LazyConnection(connector)
    barrier = threading.Barrier(5)
    got = []

    def work():
        barrier.wait()
        got.append(lazy.get())

    threads = [threading.Thread(target=work) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert connector.calls == 1
    assert len({id(conn) for conn in got}) == 1


def test_login_output_never_reaches_stdout(capsys):
    LazyConnection(FakeConnector(prints="Going to open: https://okta.example/login")).get()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Going to open" in captured.err


def test_state_answers_at_once_during_a_pending_login():  # Review Focus 3
    lazy = LazyConnection(FakeConnector(delay=0.5))
    threading.Thread(target=lazy.get, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    assert lazy.state()["state"] == "logging_in"
    assert time.monotonic() - started < 0.05


def test_login_timeout_then_the_next_call_opens_a_new_login():
    connector = FakeConnector(delay=5)          # the user never finishes the first tab
    lazy = LazyConnection(connector, login_timeout=0.2)
    with pytest.raises(LoginTimeout):
        lazy.get()
    connector.delay = 0                         # the user finishes the second tab
    assert lazy.get() is connector.connections[-1]
    assert connector.calls == 2


def test_a_login_finished_after_the_timeout_is_kept():
    connector = FakeConnector(delay=0.4)
    lazy = LazyConnection(connector, login_timeout=0.1)
    with pytest.raises(LoginTimeout):
        lazy.get()
    time.sleep(0.5)
    assert lazy.state()["state"] == "logged_in"
    lazy.get()
    assert connector.calls == 1


def test_a_login_error_raises_login_failed_and_the_next_call_retries():
    connector = FakeConnector(error=RuntimeError("IdP said no"))
    lazy = LazyConnection(connector)
    with pytest.raises(LoginFailed, match="IdP said no"):
        lazy.get()
    connector.error = None
    lazy.get()
    assert connector.calls == 2


def test_login_events_are_logged(tmp_path):
    LazyConnection(FakeConnector(), log=EventLog(tmp_path)).get()
    text = next(tmp_path.glob("*.log")).read_text()
    assert " login_started" in text
    assert " logged_in seconds=" in text
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_connection.py -q`
Expected: `ModuleNotFoundError: No module named 'connection'`.

- [ ] **Step 4: Write the implementation** — `skills/snowflake/mcp_server/connection.py`

```python
"""One Snowflake connection per Claude window: log in on first use, never block past the timeout."""
import contextlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from eventlog import EventLog


class LoginTimeout(Exception):
    """The browser login didn't finish in time."""


class LoginFailed(Exception):
    """The login ended with an error."""


class LoginExpired(Exception):
    """The session lapsed; the next call opens a fresh login."""


class _Attempt:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.done = threading.Event()
        self.error: BaseException | None = None

    def remaining(self, timeout: float) -> float:
        return max(0.0, self.started + timeout - time.monotonic())


class LazyConnection:
    def __init__(self, connect: Callable[[], Any], login_timeout: float = 120.0,
                 log: EventLog | None = None) -> None:
        self._connect = connect
        self._timeout = login_timeout
        self._log = log
        self._lock = threading.Lock()       # never held while a login waits
        self._conn: Any = None
        self._attempt: _Attempt | None = None

    def _event(self, event: str, **fields: object) -> None:
        if self._log is not None:
            self._log.write(event, **fields)

    def get(self) -> Any:
        """Return the live connection, logging in first if needed (at most one login at a time)."""
        with self._lock:
            if self._conn is not None:
                return self._conn
            attempt = self._attempt
            if attempt is None or attempt.done.is_set() or attempt.remaining(self._timeout) == 0:
                attempt = self._attempt = _Attempt()
                self._event("login_started")
                threading.Thread(target=self._login, args=(attempt,), daemon=True).start()
        if not attempt.done.wait(attempt.remaining(self._timeout)):
            self._event("login_timeout", seconds=float(self._timeout))
            raise LoginTimeout(f"The Okta login didn't finish within {self._timeout:.0f} seconds.")
        with self._lock:
            if self._conn is not None:
                return self._conn
        raise LoginFailed(f"The Okta login failed: {attempt.error}")

    def _login(self, attempt: _Attempt) -> None:
        # The connector's browser wait has no timeout, so it runs here while get() waits with one.
        started = time.monotonic()
        try:
            with contextlib.redirect_stdout(sys.stderr):    # stdout carries the MCP protocol
                conn = self._connect()
        except Exception as exc:
            attempt.error = exc
            self._event("login_failed", seconds=time.monotonic() - started, error=type(exc).__name__)
            attempt.done.set()
            return
        with self._lock:
            keep = self._conn is None
            if keep:
                self._conn = conn
            current = self._attempt
        if keep:
            self._event("logged_in", seconds=time.monotonic() - started)
        else:
            with contextlib.suppress(Exception):
                conn.close()                # a newer login already won
        attempt.done.set()
        if current is not None:
            current.done.set()              # wake callers waiting on a newer attempt

    def state(self) -> dict:
        """Never blocks: logged_out, logging_in (with seconds_left) or logged_in (with names)."""
        with self._lock:
            conn, attempt = self._conn, self._attempt
        if conn is not None:
            return {"state": "logged_in", "user": conn.user, "role": conn.role, "warehouse": conn.warehouse}
        if attempt is not None and not attempt.done.is_set() and attempt.remaining(self._timeout) > 0:
            return {"state": "logging_in", "seconds_left": round(attempt.remaining(self._timeout))}
        return {"state": "logged_out"}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_connection.py -q` three times.
Expected: `9 passed` every time. These tests use real threads and short sleeps, so a flaky pass is a bug to fix, not to retry.

- [ ] **Step 6: Commit**

```bash
git add skills/snowflake/mcp_server/connection.py tests/fakes.py tests/test_connection.py
git commit -m "Log in lazily with a 2-minute limit and one login per window"
```

### Task 10: Expired sessions and error codes

**Files:**
- Modify: `skills/snowflake/mcp_server/connection.py`
- Test: `tests/test_connection.py`

**Interfaces:**
- Consumes: `LazyConnection` and the three exceptions from Task 9.
- Produces: `LazyConnection.discard(conn) -> None`; `default_connect() -> connection`, which imports the connector only when called (§5.1); `classify_error(exc) -> tuple[str, str]`, which returns `(code, message)` with code one of `LOGIN_TIMEOUT`, `LOGIN_FAILED`, `LOGIN_EXPIRED`, `TIMEOUT`, `SQL_ERROR` or `INTERNAL_ERROR`.
- Design: P5. Every new connection gets `_reauthenticate` replaced, so the connector raises `LoginExpired` instead of waiting on a browser (Verified Facts).

- [ ] **Step 1: Write the failing tests**

Replace the import lines at the top of `tests/test_connection.py` (from `import pytest` down to the `from connection …` line) with:

```python
import pytest
from snowflake.connector.errors import OperationalError, ProgrammingError

from connection import (LazyConnection, LoginExpired, LoginFailed, LoginTimeout, classify_error,
                        default_connect)
```

Keep the other imports (`threading`, `time`, `EventLog`, `FakeConnector`). Append to `tests/test_connection.py`. This covers spec §10.1 (Error codes) and §11 (the expired-session risk).

```python

def test_an_expired_session_never_opens_a_browser_inside_a_query():
    conn = LazyConnection(FakeConnector()).get()
    with pytest.raises(LoginExpired):
        conn._reauthenticate()          # what the connector calls when the session has expired


def test_discard_forgets_the_connection_and_the_next_get_logs_in_again():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    conn = lazy.get()
    lazy.discard(conn)
    assert lazy.state() == {"state": "logged_out"}
    assert lazy.get() is not conn
    assert connector.calls == 2


def test_default_connect_uses_the_newrelic_settings(monkeypatch):
    import snowflake.connector

    seen = {}
    monkeypatch.setattr(snowflake.connector, "connect", lambda **kw: seen.update(kw) or "conn")
    assert default_connect() == "conn"
    assert seen == {"connection_name": "newrelic", "client_session_keep_alive": True,
                    "session_parameters": {"QUERY_TAG": "snowflake-skill"}}


@pytest.mark.parametrize("exc,code", [
    (LoginTimeout("slow"), "LOGIN_TIMEOUT"),
    (LoginFailed("no"), "LOGIN_FAILED"),
    (LoginExpired("gone"), "LOGIN_EXPIRED"),
    (OperationalError(msg="Connection is closed", errno=250002), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="Session no longer exists.", errno=390112), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="Authentication token has expired.", errno=390114), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="SQL execution was cancelled by the client due to a timeout.", errno=604), "TIMEOUT"),
    (ProgrammingError(msg="Statement reached its statement or warehouse timeout.", errno=630), "TIMEOUT"),
    (ProgrammingError(msg="SQL compilation error: Object 'X' does not exist.", errno=2003), "SQL_ERROR"),
    (OSError(28, "No space left on device"), "INTERNAL_ERROR"),
    (RuntimeError("bug"), "INTERNAL_ERROR"),
])
def test_classify_error_maps_failures_to_codes(exc, code):
    assert classify_error(exc)[0] == code


def test_a_sql_error_keeps_snowflakes_message():
    code, message = classify_error(ProgrammingError(msg="SQL compilation error: invalid identifier 'FOO'", errno=904))
    assert code == "SQL_ERROR"
    assert "invalid identifier 'FOO'" in message
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_connection.py -q`
Expected: `ImportError: cannot import name 'classify_error' from 'connection'`.

- [ ] **Step 3: Write the implementation**

In `connection.py`, add this function right after the `LoginExpired` class:

```python
def _refuse_reauthentication(*args, **kwargs):
    # The connector calls this on an expired session and would wait on a browser forever (§5.5).
    raise LoginExpired("The Snowflake session expired.")
```

In `LazyConnection._login`, add one line between the `except` block and `with self._lock:`:

```python
            attempt.done.set()
            return
        conn._reauthenticate = _refuse_reauthentication
        with self._lock:
```

Append to the end of `connection.py`. The first block is indented, so it becomes a `LazyConnection` method after `state()`.

```python
    def discard(self, conn: Any) -> None:
        """Forget a dead connection so the next get() logs in again."""
        with self._lock:
            if self._conn is conn:
                self._conn = None


def default_connect() -> Any:
    """Open the real connection from ~/.snowflake/connections.toml, importing the connector only now."""
    import snowflake.connector

    return snowflake.connector.connect(
        connection_name="newrelic",
        client_session_keep_alive=True,
        session_parameters={"QUERY_TAG": "snowflake-skill"},
    )


_EXPIRED_ERRNOS = {250002, 390112, 390114}   # connection closed, session expired, master token expired
_TIMEOUT_ERRNOS = {604, 630}                 # cancelled by the client timer, statement timeout


def classify_error(exc: BaseException) -> tuple[str, str]:
    """Map a login or query failure to a §5.5 code (plus P4's LOGIN_FAILED and INTERNAL_ERROR)."""
    if isinstance(exc, LoginTimeout):
        return "LOGIN_TIMEOUT", str(exc)
    if isinstance(exc, LoginFailed):
        return "LOGIN_FAILED", str(exc)
    if isinstance(exc, LoginExpired):
        return "LOGIN_EXPIRED", str(exc)
    if type(exc).__module__.startswith("snowflake.connector"):
        errno = getattr(exc, "errno", None)
        if errno in _EXPIRED_ERRNOS:
            return "LOGIN_EXPIRED", str(exc)
        if errno in _TIMEOUT_ERRNOS or "due to a timeout" in str(exc):
            return "TIMEOUT", str(exc)
        return "SQL_ERROR", str(exc)
    return "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_connection.py -q`
Expected: `24 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/connection.py tests/test_connection.py
git commit -m "Map login and query failures to error codes; never re-login inside a query"
```

### Task 11: `status` tool and server entry point

**Files:**
- Create: `skills/snowflake/mcp_server/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `LazyConnection` and `default_connect` (Tasks 9–10), `EventLog` (Task 8) and `unlearned_folders` (Task 7).
- Produces: `build_server(runs_dir, connection, log) -> MCPServer` with a `status` tool; `main(argv=None)` with `--runs-dir`, whose default is `<repo>/runs`; `REPO`, the repo root. `status()` returns three lines: the login state; `Runs folder: <path>`; `Unlearned question folders: <n>` (P6). Task 12 adds `run_query` inside `build_server`.

- [ ] **Step 1: Write the failing test** — `tests/test_server.py`

```python
import threading
import time

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

import server as server_module
from connection import LazyConnection
from eventlog import EventLog
from fakes import FakeConnector
from server import build_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def make(tmp_path):
    def _make(connector=None, login_timeout=120.0):
        connector = connector or FakeConnector()
        log = EventLog(tmp_path / "runs" / "logs")
        lazy = LazyConnection(connector, login_timeout=login_timeout, log=log)
        return build_server(tmp_path / "runs", lazy, log), connector, lazy
    return _make


async def call(server, tool, **args):
    async with Client(server) as client:
        result = await client.call_tool(tool, args)
    return result.is_error, result.content[0].text


@pytest.mark.anyio
async def test_status_never_logs_in(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "status")
    assert not is_error
    assert text.splitlines() == [
        "Not logged in. The next run_query opens an Okta login tab in the browser.",
        f"Runs folder: {tmp_path / 'runs'}",
        "Unlearned question folders: 0",
    ]
    assert connector.calls == 0


@pytest.mark.anyio
async def test_status_after_login_names_user_role_and_warehouse(make):
    server, _, lazy = make()
    lazy.get()
    _, text = await call(server, "status")
    assert text.splitlines()[0] == ("Logged in as JKARNIK (role FR_PRODUCT_ANALYST, "
                                    "warehouse TEAM_PRODUCT_ANALYST_XSMALL).")


@pytest.mark.anyio
async def test_status_during_a_pending_login_answers_at_once(make):  # Review Focus 3
    server, _, lazy = make(FakeConnector(delay=1.0))
    threading.Thread(target=lazy.get, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    _, text = await call(server, "status")
    assert text.startswith("Login in progress")
    assert time.monotonic() - started < 0.5


@pytest.mark.anyio
async def test_status_counts_unlearned_question_folders(make, tmp_path):
    for rel in ["2026-10-01/a", "2026-10-01/b"]:
        (tmp_path / "runs" / rel).mkdir(parents=True)
    (tmp_path / "runs" / "learned.txt").write_text("2026-10-01/a\n")
    server, _, _ = make()
    _, text = await call(server, "status")
    assert text.splitlines()[-1] == "Unlearned question folders: 1"


def test_main_logs_server_start_without_logging_in(tmp_path, monkeypatch):
    monkeypatch.setattr(MCPServer, "run", lambda self, *args, **kwargs: None)
    server_module.main(["--runs-dir", str(tmp_path / "runs")])
    log_text = next((tmp_path / "runs" / "logs").glob("*.log")).read_text()
    assert " server_started" in log_text
    assert "login" not in log_text


def test_default_runs_dir_is_at_the_repo_root():
    assert (server_module.REPO / "skills" / "snowflake" / "mcp_server" / "server.py").is_file()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server.py -q`
Expected: `ModuleNotFoundError: No module named 'server'`.

- [ ] **Step 3: Write the implementation** — `skills/snowflake/mcp_server/server.py`

```python
"""Snowflake MCP server: read-only, and logs in on the first query in each Claude window."""
import argparse
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from connection import LazyConnection, default_connect
from eventlog import EventLog
from results import unlearned_folders

REPO = Path(__file__).resolve().parents[3]


def build_server(runs_dir: Path, connection: LazyConnection, log: EventLog) -> MCPServer:
    server = MCPServer("snowflake")

    @server.tool(structured_output=False)
    def status() -> str:
        """Say whether this Claude window is logged in to Snowflake. Never logs in; no side effects.

        Call it before the first query. If it says "Not logged in", tell the user an Okta login tab
        is about to open in their browser (about 20 seconds). It also gives the runs folder and how
        many question folders /snowflake learn hasn't read yet.
        """
        state = connection.state()
        if state["state"] == "logged_in":
            line = (f"Logged in as {state['user']} (role {state['role']}, "
                    f"warehouse {state['warehouse']}).")
        elif state["state"] == "logging_in":
            line = f"Login in progress: waiting for the Okta tab ({state['seconds_left']} s left)."
        else:
            line = "Not logged in. The next run_query opens an Okta login tab in the browser."
        return (f"{line}\nRuns folder: {runs_dir}\n"
                f"Unlearned question folders: {len(unlearned_folders(runs_dir))}")

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=REPO / "runs",
                        help="where question folders and logs go (default: <repo>/runs)")
    runs_dir = parser.parse_args(argv).runs_dir.resolve()
    log = EventLog(runs_dir / "logs")
    log.write("server_started")
    connection = LazyConnection(default_connect, log=log)
    build_server(runs_dir, connection, log).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_server.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/server.py tests/test_server.py
git commit -m "Add the MCP server entry point and the status tool"
```

### Task 12: `run_query` tool

**Files:**
- Modify: `skills/snowflake/mcp_server/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `check_sql`/`Blocked` (Task 3); `question_dir`, `save_query`, `write_csv` and `format_result` (Tasks 4–6); `LazyConnection.get`/`discard` and `classify_error` (Tasks 9–10); `EventLog.write` (Task 8).
- Produces: the `run_query(sql, question, step="query", timeout_seconds=300, max_rows=100000)` tool (§5.2). Pydantic bounds reject `timeout_seconds` outside 1–3600 and `max_rows` below 1 before the tool runs. Errors come back as `ToolError("<CODE>: <message>\nSQL: <path>")`.
- Order of steps (§5.2): save the SQL, guard, connect, execute with the time limit, stream the CSV. A failed query deletes its partial CSV.

- [ ] **Step 1: Write the failing tests**

In `tests/test_server.py`, add `from datetime import date` after `import time`, add `from snowflake.connector.errors import ProgrammingError` after the `mcp` imports, and change `from connection import LazyConnection` to `from connection import LazyConnection, LoginExpired`. Then append:

```python

TODAY = date.today().isoformat()


@pytest.mark.anyio
async def test_run_query_saves_sql_and_csv_and_returns_a_preview(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="SELECT 1 AS n", question="NPM devices", step="count")
    folder = tmp_path / "runs" / TODAY / "npm-devices"
    assert not is_error
    assert text.splitlines()[0].startswith("Rows: 1 | Columns: 1 | Seconds: ")
    assert f"SQL: {folder / '01-count.sql'}" in text
    assert (folder / "01-count.sql").read_text() == "SELECT 1 AS n\n"
    assert (folder / "01-count.csv").read_bytes() == b"N\r\n1\r\n"
    assert connector.calls == 1
    assert connector.connections[0].executed == [("SELECT 1 AS n", 300)]


@pytest.mark.anyio
async def test_blocked_sql_is_saved_but_never_reaches_snowflake(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="DELETE FROM t", question="oops")
    folder = tmp_path / "runs" / TODAY / "oops"
    assert is_error
    assert "BLOCKED: Delete statements are not allowed" in text
    assert (folder / "01-query.sql").read_text() == "DELETE FROM t\n"
    assert not (folder / "01-query.csv").exists()
    assert connector.calls == 0


@pytest.mark.anyio
async def test_follow_ups_share_the_folder_and_count_up(make, tmp_path):
    server, _, _ = make()
    await call(server, "run_query", sql="SELECT 1", question="q", step="first")
    await call(server, "run_query", sql="SELECT 2", question="q", step="second")
    names = sorted(p.name for p in (tmp_path / "runs" / TODAY / "q").iterdir())
    assert names == ["01-first.csv", "01-first.sql", "02-second.csv", "02-second.sql"]


@pytest.mark.anyio
async def test_a_sql_error_returns_its_code_and_leaves_no_csv(make, tmp_path):
    server, _, lazy = make()
    lazy.get().fail_with = ProgrammingError(msg="SQL compilation error: invalid identifier 'FOO'", errno=904)
    is_error, text = await call(server, "run_query", sql="SELECT foo FROM t", question="q")
    assert is_error
    assert "SQL_ERROR: " in text and "invalid identifier 'FOO'" in text
    assert (tmp_path / "runs" / TODAY / "q" / "01-query.sql").exists()
    assert not (tmp_path / "runs" / TODAY / "q" / "01-query.csv").exists()


@pytest.mark.anyio
async def test_an_expired_session_is_dropped_and_the_next_call_logs_in(make):
    server, connector, lazy = make()
    lazy.get().fail_with = LoginExpired("The Snowflake session expired.")
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "LOGIN_EXPIRED: " in text
    is_error, _ = await call(server, "run_query", sql="SELECT 1", question="q")
    assert not is_error
    assert connector.calls == 2


@pytest.mark.anyio
async def test_a_login_timeout_returns_its_code(make):
    server, _, _ = make(FakeConnector(delay=2), login_timeout=0.2)
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "LOGIN_TIMEOUT: " in text


@pytest.mark.anyio
async def test_a_statement_timeout_returns_its_code(make):
    server, _, lazy = make()
    conn = lazy.get()
    conn.fail_with = ProgrammingError(msg="SQL execution was cancelled by the client due to a timeout.",
                                      errno=604)
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q", timeout_seconds=5)
    assert is_error and "TIMEOUT: " in text
    assert conn.executed[-1] == ("SELECT 1", 5)


@pytest.mark.anyio
async def test_unexpected_errors_still_reach_claude(make):
    server, _, lazy = make()
    lazy.get().fail_with = RuntimeError("disk on fire")
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "INTERNAL_ERROR: RuntimeError: disk on fire" in text


@pytest.mark.anyio
async def test_max_rows_caps_the_csv(make, tmp_path):
    server, _, lazy = make()
    lazy.get().result = (["N"], [(i,) for i in range(10)])
    _, text = await call(server, "run_query", sql="SELECT n FROM t", question="q", max_rows=3)
    assert "Note: the CSV stopped at max_rows=3." in text
    assert len((tmp_path / "runs" / TODAY / "q" / "01-query.csv").read_text().splitlines()) == 4


@pytest.mark.anyio
@pytest.mark.parametrize("args", [{"timeout_seconds": 7200}, {"timeout_seconds": 0}, {"max_rows": 0}])
async def test_out_of_range_arguments_are_refused(make, args):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q", **args)
    assert is_error
    assert next(iter(args)) in text
    assert connector.calls == 0


@pytest.mark.anyio
async def test_queries_are_logged_without_results(make, tmp_path):
    server, _, lazy = make()
    lazy.get().result = (["SECRET_COLUMN"], [("secret value",)])
    await call(server, "run_query", sql="SELECT 1", question="q")
    log_text = next((tmp_path / "runs" / "logs").glob("*.log")).read_text()
    assert " query_finished seconds=" in log_text and " rows=1 " in log_text
    assert "secret value" not in log_text and "SECRET_COLUMN" not in log_text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_server.py -q`
Expected: `13 failed, 6 passed`. The failures show `Unknown tool: run_query`.

- [ ] **Step 3: Write the implementation**

Replace the import block at the top of `server.py` (everything between the docstring and `REPO = …`) with:

```python
import argparse
import time
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from connection import LazyConnection, classify_error, default_connect
from eventlog import EventLog
from guard import Blocked, check_sql
from results import format_result, question_dir, save_query, unlearned_folders, write_csv
```

In `build_server`, replace the final `    return server` line with:

```python
    @server.tool(structured_output=False)
    def run_query(
        sql: Annotated[str, Field(description="Exactly one SELECT, SHOW or DESCRIBE statement.")],
        question: Annotated[str, Field(description=(
            "Short slug naming this question's folder, e.g. npm-devices-by-type. "
            "Reuse it for follow-ups that refine the same question."))],
        step: Annotated[str, Field(description="Short name for this query within the question.")] = "query",
        timeout_seconds: Annotated[int, Field(ge=1, le=3600, description=(
            "Statement time limit. Keep 300 unless the user agreed to a longer run."))] = 300,
        max_rows: Annotated[int, Field(ge=1, description="Most rows written to the CSV.")] = 100000,
    ) -> str:
        """Run one read-only statement on New Relic's Snowflake; save its SQL and CSV under runs/.

        The first call in a window opens an Okta login in the browser. Returns a header line, the
        file paths and a preview of up to 50 rows. Errors start with a code: BLOCKED, LOGIN_TIMEOUT,
        LOGIN_FAILED, LOGIN_EXPIRED, TIMEOUT, SQL_ERROR or INTERNAL_ERROR.
        """
        started = time.monotonic()
        try:
            folder = question_dir(runs_dir, question)
            sql_path, csv_path = save_query(folder, step, sql)
        except OSError as exc:
            raise ToolError(f"INTERNAL_ERROR: could not save the SQL under {runs_dir}: {exc}") from None
        where = f"{folder.parent.name}/{folder.name}/{sql_path.name}"

        def fail(code: str, message: str) -> ToolError:
            log.write("query_failed", code=code, seconds=time.monotonic() - started, file=where)
            return ToolError(f"{code}: {message}\nSQL: {sql_path}")

        try:
            check_sql(sql)
        except Blocked as exc:
            raise fail("BLOCKED", str(exc)) from None
        conn = None
        try:
            conn = connection.get()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, timeout=timeout_seconds)
                columns = [d[0] for d in cursor.description or []]
                result = write_csv(csv_path, columns, cursor, max_rows)
                query_id = cursor.sfqid
            finally:
                cursor.close()
        except Exception as exc:
            code, message = classify_error(exc)
            if code == "LOGIN_EXPIRED" and conn is not None:
                connection.discard(conn)
            csv_path.unlink(missing_ok=True)        # only a successful query leaves a CSV
            raise fail(code, message) from None
        elapsed = time.monotonic() - started
        log.write("query_finished", seconds=elapsed, rows=result.row_count, file=where)
        return format_result(columns=columns, result=result, elapsed=elapsed, query_id=query_id,
                             sql_path=sql_path, csv_path=csv_path, max_rows=max_rows)

    return server
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: `106 passed`, the whole suite so far.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/mcp_server/server.py tests/test_server.py
git commit -m "Add the run_query tool: guard, lazy login, CSV and error codes"
```

### Task 13: Real-stdio test

**Files:**
- Create: `tests/fake_server_main.py`
- Test: `tests/test_stdio.py`

**Interfaces:**
- Consumes: `server.main` and `server.default_connect` (Tasks 11–12) and `FakeConnector` (Task 9).
- Produces: an offline stand-in for §10.3. A real stdio server subprocess starts logged out, and three queries give exactly one login, while the fake login writes junk to both `print()` and raw fd 1.

- [ ] **Step 1: Write the failing test** — `tests/test_stdio.py`

```python
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

SCRIPT = Path(__file__).with_name("fake_server_main.py")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_the_stdio_server_survives_login_noise_and_logs_in_once(tmp_path):
    runs = tmp_path / "runs"
    params = StdioServerParameters(command=sys.executable, args=[str(SCRIPT), "--runs-dir", str(runs)])
    async with Client(params) as client:
        assert sorted(t.name for t in (await client.list_tools()).tools) == ["run_query", "status"]
        first = await client.call_tool("status", {})
        assert first.content[0].text.startswith("Not logged in")
        for i in range(3):
            result = await client.call_tool("run_query", {"sql": f"SELECT {i}", "question": "stdio-check"})
            assert not result.is_error, result.content[0].text
        last = await client.call_tool("status", {})
        assert last.content[0].text.startswith("Logged in as JKARNIK")
    log_text = next((runs / "logs").glob("*.log")).read_text()
    assert log_text.count(" server_started") == 1
    assert log_text.count(" login_started") == 1
    assert log_text.count(" query_finished") == 3
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_stdio.py -q`
Expected: `1 failed` with `mcp.shared.exceptions.MCPError: Connection closed`, because the launcher script doesn't exist yet.

- [ ] **Step 3: Write the launcher** — `tests/fake_server_main.py`

```python
"""Run the real MCP server over stdio with a noisy fake connector. Used only by test_stdio.py."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "snowflake" / "mcp_server"))

import server  # noqa: E402
from fakes import FakeConnector  # noqa: E402


class NoisyConnector(FakeConnector):
    def __call__(self):
        os.write(1, b"raw bytes on fd 1 during login\n")    # as a child process or C library might
        return super().__call__()


if __name__ == "__main__":
    server.default_connect = NoisyConnector(prints="Going to open: https://okta.example/login")
    server.main(sys.argv[1:])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: `107 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fake_server_main.py tests/test_stdio.py
git commit -m "Test the real stdio server with a noisy fake login"
```

### Task 14: Knowledge-check script

**Files:**
- Create: `tests/check_notes.py`
- Test: `tests/test_check_notes.py`

**Interfaces:**
- Consumes: `check_sql`/`Blocked` (Task 3) and `LazyConnection`, `default_connect` and `classify_error` (Tasks 9–10).
- Produces: `extract_sql_blocks(text) -> list[tuple[int, str]]`, `fill_placeholders(sql, values) -> str` and the CLI `.venv/bin/python tests/check_notes.py [--dry-run] [--notes DIR] [--values FILE]`. It exits 0 when every block passes. `--dry-run` only parses and guards, so Tasks 15–19 use it offline. Task 28 runs it live, with one login.

- [ ] **Step 1: Write the failing test** — `tests/test_check_notes.py`

```python
import pytest

from check_notes import extract_sql_blocks, fill_placeholders, main

NOTE = """# Note

```sql
SELECT 1
```

Text.

```sql
SELECT * FROM t WHERE name = '{{company_name}}' AND id = {{account_id}}
```

```text
not sql
```
"""


def test_extract_sql_blocks_finds_each_sql_fence_and_its_line():
    assert extract_sql_blocks(NOTE) == [
        (3, "SELECT 1"),
        (9, "SELECT * FROM t WHERE name = '{{company_name}}' AND id = {{account_id}}"),
    ]


def test_fill_placeholders_doubles_single_quotes():
    sql = fill_placeholders("SELECT '{{company_name}}', {{account_id}}",
                            {"company_name": "Macy's", "account_id": 42})
    assert sql == "SELECT 'Macy''s', 42"


def test_fill_placeholders_lists_missing_names():
    with pytest.raises(KeyError, match="account_id, company_name"):
        fill_placeholders("SELECT {{company_name}}, {{account_id}}", {})


def test_dry_run_passes_good_notes_and_fails_writes(tmp_path, capsys):
    notes = tmp_path / "references"
    notes.mkdir()
    (notes / "good.md").write_text(NOTE)
    args = ["--notes", str(notes), "--values", str(tmp_path / "none.toml"), "--dry-run"]
    assert main(args) == 0
    (notes / "bad.md").write_text("```sql\nDELETE FROM t\n```\n")
    assert main(args) == 1
    assert "FAIL bad.md:1 BLOCKED" in capsys.readouterr().out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_check_notes.py -q`
Expected: `ModuleNotFoundError: No module named 'check_notes'`.

- [ ] **Step 3: Write the script** — `tests/check_notes.py`

```python
"""Knowledge checks (spec §10.2): run every ```sql block in the reference notes.

Placeholders like {{company_name}} are filled from runs/evals/values.toml. Each block must pass the
read-only guard and finish within 2 minutes. Prints PASS/FAIL per block, never result rows.
Use --dry-run to parse and guard only, without Snowflake.
"""
import argparse
import re
import sys
import time
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "snowflake" / "mcp_server"))

from connection import LazyConnection, classify_error, default_connect  # noqa: E402
from guard import Blocked, check_sql  # noqa: E402

PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
FENCE = re.compile(r"^```sql[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)


def extract_sql_blocks(text: str) -> list[tuple[int, str]]:
    """(line of the opening fence, SQL) for every ```sql block."""
    return [(text.count("\n", 0, m.start()) + 1, m.group(1).strip()) for m in FENCE.finditer(text)]


def fill_placeholders(sql: str, values: dict) -> str:
    """Replace {{name}} with its value, doubling single quotes; KeyError lists missing names."""
    missing = sorted({name for name in PLACEHOLDER.findall(sql) if name not in values})
    if missing:
        raise KeyError(", ".join(missing))
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]).replace("'", "''"), sql)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=Path, default=REPO / "skills" / "snowflake" / "references")
    parser.add_argument("--values", type=Path, default=REPO / "runs" / "evals" / "values.toml")
    parser.add_argument("--dry-run", action="store_true", help="parse and guard only; no Snowflake")
    args = parser.parse_args(argv)
    values = tomllib.loads(args.values.read_text(encoding="utf-8")) if args.values.exists() else {}
    lazy = None if args.dry_run else LazyConnection(default_connect)
    failures = 0
    for note in sorted(args.notes.glob("*.md")):
        for line, raw in extract_sql_blocks(note.read_text(encoding="utf-8")):
            where = f"{note.name}:{line}"
            try:
                if lazy is None:
                    check_sql(PLACEHOLDER.sub(lambda m: f"PLACEHOLDER_{m.group(1).upper()}", raw))
                    print(f"PASS {where} (parsed)")
                    continue
                sql = fill_placeholders(raw, values)
                check_sql(sql)
                started = time.monotonic()
                cursor = lazy.get().cursor()
                try:
                    cursor.execute(sql, timeout=120)
                    cursor.fetchmany(5)
                finally:
                    cursor.close()
                print(f"PASS {where} ({time.monotonic() - started:.1f} s)")
            except KeyError as exc:
                failures += 1
                print(f"FAIL {where} missing values in {args.values.name}: {exc.args[0]}")
            except Blocked as exc:
                failures += 1
                print(f"FAIL {where} BLOCKED: {exc}")
            except Exception as exc:
                code, message = classify_error(exc)
                failures += 1
                print(f"FAIL {where} {code}: {message.splitlines()[0]}")
                if code.startswith("LOGIN_"):
                    print("Stopping: no Snowflake session, so every later block would fail too.")
                    return 1
    print(f"{failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: `111 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/check_notes.py tests/test_check_notes.py
git commit -m "Add the knowledge-check script for reference-note queries"
```

### Task 15: `finding-data.md`

**Files:**
- Create: `skills/snowflake/references/finding-data.md`

**Interfaces:**
- Consumes: the catalog sections of `Snowflake.md` (architecture, inventory, naming, dictionary, Confluence pages) and `tests/check_notes.py --dry-run` (Task 14).
- Produces: the discovery note. The entry formats used here are the ones `updater.md` (Task 19) defines. A recipe is a `### name` heading, a `Use for: … Last used: YYYY-MM-DD.` line, then a `sql` block. A pitfall is a bullet with a bold name, the fix and `Last used:`. `Critical.` marks entries that change the answer.
- Deliberate cuts: row and object counts (they go stale; §6.3), and the `DEV_KNAGENDRA_TRANSFORMED` dictionary with its Confluence page (production-only; §6.2). The old advice to `USE DATABASE` for cross-database joins becomes a pitfall, since the guard refuses `USE`.

- [ ] **Step 1: Write the note** — `skills/snowflake/references/finding-data.md`, exactly:

````markdown
# Finding data

Read this when no recipe in another note fits, or the user asks what data exists. It covers the
warehouse layout, naming rules and discovery queries.

## Layers and environments

dbt builds four zones. Each zone is fed by the one before it.

| Zone | Database | Holds | Use when |
|---|---|---|---|
| 1 | `RAW` | Untouched feeds: Kafka JSON, Fivetran, Segment, S3 | Rarely; only for raw JSON |
| 2 | `CONFORMED` | Staged views over raw data: entities, accounts, orgs, billing, usage, Salesforce, Zuora, users | You need clean, joined source data |
| 3 | `TRANSFORMED` | Marts with business logic: finance, sales, product consumption | `REPORTING` lacks what you need |
| 4 | `REPORTING` | Views behind Looker dashboards; pre-aggregated metrics | You need ready-made business metrics |

Other production databases:
- `USAGE_AND_RATING`: usage and consumption per account per day. It is the billing system of record (see `billing.md`).
- `NR_SILVER_DATALAKE_PROD`: the silver ingest layer, with Kafka streams, NRDB exports and raw Salesforce and Zuora feeds.
- `DATA_ANALYTICS`: GTM analytics and Tableau. `EA_REPORTING`: Enterprise Account reporting.

Each zone has `_STAGING` and `_DEV` copies (for example `CONFORMED_STAGING`), and developer sandboxes
start with `DEV_`. Query production only, unless the user asks otherwise.

Tooling: Airflow orchestrates, dbt transforms (`source.datanerd.us/dataos/dbt_core_models`) and Looker
visualises (`newrelic.cloud.looker.com`).

## Schemas worth knowing

- **`CONFORMED`:** `ENTITIES` (monitored entities, US/EU/staging), `SFDC` and `SALESFORCE` (CRM),
  `ZUORA` (subscriptions), `ORGANIZATION_DB` (org hierarchy and contracts), `USERS_DB`,
  `PRODUCT_CONSUMPTION_V2` (current product usage; `PRODUCT_CONSUMPTION` is v1),
  `NRDB_INGEST_V2` (ingest volumes), `ENTITY_INGEST`, `COMPACT_ENTITLEMENTS_V2` and
  `COMPACT_ORG_GROUP_ENTITLEMENTS_V2` (what accounts and org groups may use), `CUSTOMER360`,
  `GROWTH_ANALYTICS`, `PRODUCT_RATING`, `RUN_RATE`, `NETSUITE_V2`, `WORKDAY`, `DBT_ARTIFACTS` (dbt
  metadata) and `ELEMENTARY` (dbt tests).
- **`TRANSFORMED`:** `FINANCE`, `COMMON`, `SALES`, `PRODUCT_CONSUMPTION`, `PRODUCT_ENGINEERING`,
  `PRODUCT_MARKETING`, `PRODUCT_OBSERVABILITY`, `GROSS_MARGIN`, `EDP_OPERATIONS`.
- **`REPORTING`:** `REPORTING_LOOKER_PDT` (Looker persistent tables), `COMMON`, `NREM` (enterprise
  metrics), `CONSUMPTION_METRICS`, `PRODUCT_CONSUMPTION`, `REVENUE`, `PRODUCT_ENGINEERING`.

## Naming and classification

| Pattern | Meaning | Example |
|---|---|---|
| `STG_` | Staged (conformed) view | `STG_SFDC_ACCOUNT` |
| `_D` / `_F` suffix | Dimension / fact table (seen in table names) | `SFDC_ACCOUNT_D`, `ENTITY_INGEST_DAILY_F` |
| `DEV_<USER>_` | Developer sandbox database; never query | `DEV_SNAWAZ_CONFORMED` |
| `SVC_` | Service account | `SVC_AF_ETHEL_FINANCE_DEV` |
| `TEAM_<TEAM>_<SIZE>` | Team warehouse | `TEAM_PRODUCT_ANALYST_XSMALL` |

Governance tags: `data_classification` (Public, Internal, Confidential, Restricted), `is_pii`
(Snowflake should hold no PII), `department` and `owning_team`.

## Recipes

### Find tables by name
Use for: "is there a table with …". Search `CONFORMED`, `TRANSFORMED` and `REPORTING` one at a
time. Last used: 2026-09-30.

```sql
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, ROW_COUNT
FROM {{database}}.INFORMATION_SCHEMA.TABLES
WHERE LOWER(TABLE_NAME) LIKE '%{{search_term}}%'
ORDER BY TABLE_SCHEMA, TABLE_NAME
LIMIT 200
```

### Find columns by name
Use for: "which table has a column for …". Last used: 2026-09-30.

```sql
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM {{database}}.INFORMATION_SCHEMA.COLUMNS
WHERE LOWER(COLUMN_NAME) LIKE '%{{search_term}}%'
ORDER BY TABLE_SCHEMA, TABLE_NAME
LIMIT 200
```

### List a database's schemas
Last used: 2026-09-30.

```sql
SHOW SCHEMAS IN DATABASE {{database}}
```

### Look at one table
Use `DESCRIBE` for columns and types, then a 5-row sample. Last used: 2026-09-30.

```sql
DESCRIBE TABLE {{database}}.{{schema}}.{{table}}
```

```sql
SELECT * FROM {{database}}.{{schema}}.{{table}} LIMIT 5
```

### dbt model, source and exposure metadata
Use for: what a dbt model means, where it comes from and which dashboards use it. Last used: 2026-09-30.

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__CURRENT_MODELS LIMIT 20
```

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__SOURCES LIMIT 20
```

```sql
SELECT * FROM CONFORMED.DBT_ARTIFACTS.DIM_DBT__EXPOSURES LIMIT 20
```

## Pitfalls

- **One database at a time.** `INFORMATION_SCHEMA` covers only its own database, so search each one. Last used: 2026-09-30.
- **Views have no row count.** `ROW_COUNT` is empty for views, which are most of `CONFORMED` and `REPORTING`. Last used: 2026-09-30.
- **Never `USE`.** The guard refuses `USE`. Write fully qualified `DATABASE.SCHEMA.TABLE` names, which also work across databases. Critical. Last used: 2026-09-30.
- **Never count entities from `STG_ENTITIES`.** Those views sit on a raw entity table of tens of terabytes, with the type parsed from JSON, so even one day is very expensive. Count entities by type from ELIA (`npm.md`) instead, and use `STG_ENTITIES` only for a filtered lookup with `LIMIT`. Last used: 2026-09-30.

## Confluence pages

- [Databases, Schemas, VWs, Roles, Tags](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2416705705): naming standards, RBAC, warehouse sizing.
- [Onboarding for New Data Engineers](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/3497230586): tech stack, dbt zones, environments.
- [Product Consumption & Billing](https://newrelic.atlassian.net/wiki/spaces/DATA/pages/2419851420): pipeline, table schemas, business rules.
- [Architecture: Product Rating Data Service](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4357130070) and [Onboarding New Products for Usage Rating](https://newrelic.atlassian.net/wiki/spaces/GROW/pages/4340155340): how products get metered and rated.
````

- [ ] **Step 2: Check its SQL offline**

Run: `.venv/bin/python tests/check_notes.py --dry-run`
Expected: 8 `PASS finding-data.md:<line> (parsed)` lines, then `0 failed`.

- [ ] **Step 3: Check its size**

Run: `wc -l skills/snowflake/references/finding-data.md`
Expected: under 300 (125).

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/references/finding-data.md
git commit -m "Add the finding-data reference note"
```

### Task 16: `billing.md`

**Files:**
- Create: `skills/snowflake/references/billing.md`

**Interfaces:**
- Consumes: the consumption, `ALL_DAILY_USAGE`, product-line and pipeline sections of `Snowflake.md`, and `tests/check_notes.py --dry-run`.
- Produces: the billing note that eval E6 relies on (daily ingest with de-duplication). Placeholders: `{{account_id}}`, `{{start_date}}`, `{{end_date}}`.
- Deliberate choices: recipes use only documented columns. The US-over-EU rule is a critical pitfall that tells Claude to `DESCRIBE` for the data-centre column, because its name isn't documented. The daily view's exact name isn't documented either, so the note says how to find it. Task 28 fixes or drops anything that fails live.

- [ ] **Step 1: Write the note** — `skills/snowflake/references/billing.md`, exactly:

````markdown
# Billing and consumption

Read this for questions about usage, ingest billed per account, consumption, product lines or
metrics. `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` is the financial system of record. It is
append-only, so only read it.

## Tables

`USAGE_AND_RATING.USAGE`:

| Table | Holds |
|---|---|
| `ALL_DAILY_USAGE` | Daily usage for every meter and account; the table Business Applications invoices from. Very large: always filter by account and date. |
| `ALL_DAILY_USAGE_CUSTOMER` | Usage rolled up per customer |
| `ALL_DAILY_USAGE_DAILY` | Daily summary |
| `DAILY_AGGREGATION_USER_CONSUMPTION_PROD`, `…_EU_PROD` | Per-user consumption, US and EU |
| `CUSTOMER_CONTRACT_CUSTOMER_ID_PROD`, `…_EU_PROD` | Customer-to-contract mapping, US and EU |

`ALL_DAILY_USAGE` key columns:
- `START_TIME`: start of the usage day.
- `BILLABLE_RPM_ACCOUNT_ID`: the billed RPM account, the same ID as `consuming_account_id` upstream.
- `PRODUCT_LINE`, `METRIC` and `USAGE_METRIC` (the upstream stamper's name).
- `METRIC_TYPE`: `count` or `gauge`.
- `QUANTITY`: already in GB for `GigabytesIngested`, since upstream divides bytes by 10^9.
- `INSERTED_AT`: when the row landed. It breaks ties between repeated inserts.

Upstream, the product-consumption daily view has `consuming_account_id`, `master_account_id`,
`poa_account_id` (partnership owner), `usage_start_time`, `usage_end_time` (really "reported at"),
`usage_type`, `dp_gigabytes_ingested`, `consumption`, `billable_consumption`, `estimated_cost`,
`free_limit` and `processed_time` (use it to spot restreams). It is built from
`RAW.PRODUCT_CONSUMPTION.PRODUCT_CONSUMPTION_PRODUCTION_JSON` (`…_EU_PRODUCTION_JSON` for EU). Find
the view's exact name with the "Find tables" recipe in `finding-data.md`, searching `daily_view`.

## Product lines and metrics

| Product line | Metric | Type |
|---|---|---|
| `DataPlatform` | `GigabytesIngested` | count |
| `FullStackObservability` | `OnDemandFullPlatformSessions` | count |
| `FullStackObservability` | `FullPlatformUsers`, `FullUsers`, `CoreUsers` | gauge |

## Pipeline

The Usage Stamper (AAA team) measures usage, and the Usage Rating Service rates it. Kafka carries
it (`product_consumption` topic) to S3, then to Snowflake `RAW`, then daily views. Airflow (Ethel)
joins the usage with Zuora subscriptions into `ALL_DAILY_USAGE`. Business Applications syncs at
2 am PST, and the transform must finish before then. So today's rows may be missing until after
2 am PST. Help: #help-usage-pipeline (stamper) and #help-product-consumption (rating).

## Recipes

### Daily GB ingested by one account
Use for: "how much data did account X ingest per day". Applies the de-duplication rule. Critical.
Last used: 2026-09-30.

```sql
SELECT DATE(START_TIME) AS USAGE_DATE, SUM(QUANTITY) AS GB_INGESTED
FROM (
    SELECT START_TIME, QUANTITY
    FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
    WHERE BILLABLE_RPM_ACCOUNT_ID = {{account_id}}
      AND PRODUCT_LINE = 'DataPlatform'
      AND METRIC = 'GigabytesIngested'
      AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY BILLABLE_RPM_ACCOUNT_ID, START_TIME, METRIC, PRODUCT_LINE
        ORDER BY INSERTED_AT DESC) = 1
)
GROUP BY USAGE_DATE
ORDER BY USAGE_DATE
```

### What an account is metered on
Use for: "which products or metrics does account X use". Last used: 2026-09-30.

```sql
SELECT PRODUCT_LINE, METRIC, METRIC_TYPE, COUNT(*) AS DAY_ROWS
FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE
WHERE BILLABLE_RPM_ACCOUNT_ID = {{account_id}}
  AND START_TIME >= '{{start_date}}' AND START_TIME < '{{end_date}}'
GROUP BY PRODUCT_LINE, METRIC, METRIC_TYPE
ORDER BY PRODUCT_LINE, METRIC
```

## Pitfalls

- **Repeated inserts double-count.** Keep one row per account, `START_TIME`, `METRIC` and `PRODUCT_LINE`: `ROW_NUMBER()` over that partition, latest `INSERTED_AT` first. Critical. Last used: 2026-09-30.
- **US wins over EU.** When an account reports from both data centres, billing keeps the US row, ordering by data centre ascending. Run `DESCRIBE TABLE USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` to find the data-centre column, and put it first in the `ORDER BY` of the de-duplication. Critical. Last used: 2026-09-30.
- **Gauges aren't additive.** `FullPlatformUsers`, `FullUsers` and `CoreUsers` are levels. Never `SUM` them across days. Critical. Last used: 2026-09-30.
- **Scan size.** `ALL_DAILY_USAGE` has hundreds of millions of rows on an XSMALL warehouse. Always filter by account and a date range, or use `SAMPLE` while exploring. Last used: 2026-09-30.
````

- [ ] **Step 2: Check its SQL offline**

Run: `.venv/bin/python tests/check_notes.py --dry-run`
Expected: every line is `PASS`, including `billing.md:56` and `billing.md:76`, then `0 failed`.

- [ ] **Step 3: Check its size**

Run: `wc -l skills/snowflake/references/billing.md`
Expected: under 300 (90).

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/references/billing.md
git commit -m "Add the billing and consumption reference note"
```

### Task 17: `customers.md`

**Files:**
- Create: `skills/snowflake/references/customers.md`

**Interfaces:**
- Consumes: `Account_owner.sql` (untracked; read it, never delete it), `.sfrun/addr.sql` and the Salesforce, organisation and entitlement lines of `Snowflake.md`.
- Produces: the customers note that evals E4 (account owners) and E5 (billing addresses) rely on. Placeholders: `{{company_name}}` and `{{account_id}}`.
- Deliberate changes from the originals: the owner query filters one company and keeps accounts with no owner, and its trailing comma before `FROM` is gone (P15). The address query joins parts with `ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(…))`, because `CONCAT_WS` returns NULL when any part is NULL. One of the 21 saved addresses in `addr.tsv` is blank, which fits that. Task 28 confirms it live.

- [ ] **Step 1: Write the note** — `skills/snowflake/references/customers.md`, exactly:

````markdown
# Customers and accounts

Read this for questions about a company or account: Salesforce details, billing addresses, account
owners (AE and TSM), organisations and entitlements, or turning an account ID into a company name.

## How accounts join

The RPM account ID links usage to Salesforce. Usage tables call it `BILLABLE_RPM_ACCOUNT_ID`
(`billing.md`) or `ACCOUNT_ID`/`SUBSCRIPTION_ACCOUNT_ID` (`npm.md`). The steps:

1. `TRANSFORMED.SALES.SFDC_RPM_RECORD_D` maps `RPM_ACCOUNT_ID` (and `RPM_ACCOUNT_NAME`) to `SFDC_ACCOUNT_ID`. Filter `IS_DELETED = FALSE`.
2. `TRANSFORMED.SALES.SFDC_ACCOUNT_D` gives `SFDC_ACCOUNT_NAME` for an `SFDC_ACCOUNT_ID`.
3. `TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D` lists the account team. Its `ACCOUNT_ID` is the Salesforce account ID, with `USER_ID`, `TEAM_MEMBER_ROLE` and `IS_DELETED`. The roles used here are `'AE'` and `'Technical Success Manager'`.
4. `TRANSFORMED.SALES.SFDC_USER_D` gives each `USER_ID`'s `NAME` and `EMAIL`.

`CONFORMED.SFDC.STG_SFDC_ACCOUNT` is the conformed Salesforce account view, with `NAME` and the
`BILLING_STREET`, `BILLING_CITY`, `BILLING_STATE`, `BILLING_POSTAL_CODE` and `BILLING_COUNTRY`
columns.

## Recipes

### Account owners (AE and TSM) for a company
Use for: "who are the AE and TSM for X". An empty owner column means Salesforce has none assigned.
For an account ID, replace the last `WHERE` with `WHERE B.RPM_ACCOUNT_ID = {{account_id}}`.
Last used: 2026-09-30.

```sql
WITH base AS (
    SELECT R.RPM_ACCOUNT_ID, R.RPM_ACCOUNT_NAME, R.SFDC_ACCOUNT_ID
    FROM TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
    WHERE R.IS_DELETED = FALSE
),
roles AS (
    SELECT ATM.ACCOUNT_ID AS SFDC_ACCOUNT_ID,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.NAME END) AS AE_NAME,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.EMAIL END) AS AE_EMAIL,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.NAME END) AS TSM_NAME,
           MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.EMAIL END) AS TSM_EMAIL
    FROM TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D ATM
    JOIN TRANSFORMED.SALES.SFDC_USER_D U ON ATM.USER_ID = U.USER_ID
    WHERE ATM.IS_DELETED = FALSE
      AND ATM.TEAM_MEMBER_ROLE IN ('AE', 'Technical Success Manager')
    GROUP BY ATM.ACCOUNT_ID
)
SELECT ACC.SFDC_ACCOUNT_NAME, B.RPM_ACCOUNT_ID, B.RPM_ACCOUNT_NAME,
       R.AE_NAME, R.AE_EMAIL, R.TSM_NAME, R.TSM_EMAIL
FROM base B
JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID
LEFT JOIN roles R ON R.SFDC_ACCOUNT_ID = B.SFDC_ACCOUNT_ID
WHERE ACC.SFDC_ACCOUNT_NAME ILIKE '%{{company_name}}%'
ORDER BY ACC.SFDC_ACCOUNT_NAME, B.RPM_ACCOUNT_ID
LIMIT 100
```

### Company name for an account ID
Use for: naming the accounts in a usage result. Last used: 2026-09-30.

```sql
SELECT R.RPM_ACCOUNT_ID, R.RPM_ACCOUNT_NAME, ACC.SFDC_ACCOUNT_NAME
FROM TRANSFORMED.SALES.SFDC_RPM_RECORD_D R
JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = R.SFDC_ACCOUNT_ID
WHERE R.IS_DELETED = FALSE
  AND R.RPM_ACCOUNT_ID = {{account_id}}
```

### Billing address, one line per company
Use for: "what is the billing address of X". Line breaks in the street become spaces, and empty
parts are skipped. Last used: 2026-09-30.

```sql
SELECT NAME,
       ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(
           NULLIF(TRIM(REPLACE(REPLACE(BILLING_STREET, CHR(10), ' '), CHR(13), ' ')), ''),
           NULLIF(TRIM(BILLING_CITY), ''),
           NULLIF(TRIM(COALESCE(BILLING_STATE, '') || ' ' || COALESCE(BILLING_POSTAL_CODE, '')), ''),
           NULLIF(TRIM(BILLING_COUNTRY), '')), ', ') AS ADDRESS
FROM CONFORMED.SFDC.STG_SFDC_ACCOUNT
WHERE NAME ILIKE '%{{company_name}}%'
ORDER BY NAME
LIMIT 50
```

### Organisations and entitlements
Use for: org hierarchy, or what an account may use. Look at the columns first, then filter.
Last used: 2026-09-30.

```sql
SELECT * FROM CONFORMED.ORGANIZATION_DB.STG_ORGANIZATION_DB_ORGANIZATIONS LIMIT 5
```

```sql
SHOW TABLES IN SCHEMA CONFORMED.COMPACT_ENTITLEMENTS_V2
```

## Pitfalls

- **Match names loosely.** Legal names carry suffixes and non-ASCII letters (`A.Ş.`, `Pty Ltd`), and pasted copies can be garbled. Use `ILIKE '%…%'` on a distinctive word, then confirm with the user if several companies match. Last used: 2026-09-30.
- **Deleted records linger.** Filter `IS_DELETED = FALSE` on `SFDC_RPM_RECORD_D` and `ACCOUNT_TEAM_MEMBER_D`, or former owners appear. Critical. Last used: 2026-09-30.
- **One company, many accounts.** A Salesforce account can have several RPM accounts. Show them all, not just the first. Last used: 2026-09-30.
- **Rolling accounts up to clients.** Group by `SUBSCRIPTION_ACCOUNT_ID`, the customer contract (`CC-…`). Label each client with its Salesforce name through `SFDC_RPM_RECORD_D` → `SFDC_ACCOUNT_D`, and fall back to the `ORGANIZATION_DB` org name, since many orgs are just named "Organization …". Last used: 2026-09-30.
- **New Relic's own accounts.** Internal and test accounts sit in the orgs named "New Relic Production US" and "New Relic Production EU". Exclude them from customer counts. Critical. Last used: 2026-09-30.
- **`CONCAT_WS` drops the whole address.** In Snowflake it returns NULL when any part is NULL. Join address parts with `ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(…), ', ')`. Critical. Last used: 2026-09-30.
- **Street line breaks.** `BILLING_STREET` holds `CHR(10)` and `CHR(13)`. Replace both before showing an address. Last used: 2026-09-30.
````

- [ ] **Step 2: Check its SQL offline**

Run: `.venv/bin/python tests/check_notes.py --dry-run`
Expected: every line is `PASS` (the customers note has 5 blocks), then `0 failed`.

- [ ] **Step 3: Check its size**

Run: `wc -l skills/snowflake/references/customers.md`
Expected: under 300 (103).

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/references/customers.md
git commit -m "Add the customers and account-owners reference note"
```

### Task 18: `npm.md`

**Files:**
- Create: `skills/snowflake/references/npm.md`

**Interfaces:**
- Consumes: `company_query.sql` (the ELIA and II definitions, column lists and the event-name mapping), plus the NPM facts a parallel session measured live on 2026-09-30 (project memories `npm-juniper-mist-data` and `npm-meraki-data`). Those facts are: Mist isn't under `NetworkMonitoring`, how slow ELIA scans are, the text flags, and `SUBSCRIPTION_ACCOUNT_ID` as the customer contract. Their customer names and counts stay out.
- Produces: the NPM note that evals E1 (devices by type), E2 (ingest by subgroup), E3 (the "NPM customers" check-in) and E8 (SNMP trap data holds GB, not counts) rely on. Placeholders: `{{start_date}}` and `{{end_date}}`.

- [ ] **Step 1: Write the note** — `skills/snowflake/references/npm.md`, exactly:

````markdown
# NPM adoption and usage

Read this for Network Performance Monitoring questions: devices, device types, accounts reporting
network data, NPM ingest (SNMP, syslog, flow, traps) and trends.

## Two sources, two definitions

| Source | Table | NPM filter | Grain | Use for |
|---|---|---|---|---|
| ELIA (entity-level ingest) | `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F` | `METRIC = 'NetworkMonitoring'` | One row per entity per day | Devices, device types, accounts with devices |
| Instrumentation Insights (II) | `TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F` | `USAGE_CATEGORY = 'NetworkMonitoring'` | Ingest per account, event and day | GB ingested, split by data type |

ELIA key columns: `USAGE_DATE`, `ACCOUNT_ID` (the account the data lands in),
`SUBSCRIPTION_ACCOUNT_ID` (the customer contract, `CC-…`, which groups a client's accounts),
`ENTITY_GUID` (one device), `METRIC`, `DOMAIN_TYPE` (the device type, for example
`EXT-MERAKI_DEVICE` or `INFRA-JUNIPER_MIST_SWITCH`), `ENTITY_TYPE`, `DAILY_USAGE` (bytes, additive
across rows), `IS_REPORTING`, `HAS_DAILY_CONSUMPTION`, `DATA_CENTER`, `INSTRUMENTATION_PROVIDER`
and `COLLECTOR_NAME`.

II key columns: `DATE`, `SUB_ACCOUNT_ID`, `SUBSCRIPTION_ACCOUNT_ID`, `EVENT_NAME`, `TOTAL_GB`,
`USAGE_CATEGORY`, `DATA_TYPE`, `INSTRUMENTATION_NAME`, `INSTRUMENTATION_PROVIDER`,
`INSTRUMENTATION_SOURCE`, `COLLECTOR_NAME`, `INGEST_POINT` and the `PRODUCT_FAMILY…` columns. II is
a stream from NR1 with fewer fields than NR1 itself. Adding fields is expensive, so if a field is
missing here, it isn't in Snowflake.

II subgroup from `EVENT_NAME`: `Metric` → SNMP metrics, `Log` → syslog, `KFlow` → flow,
`KSnmpTrap` → SNMP traps, and anything else → other. II holds GB (`TOTAL_GB`), not event counts, so
`KSnmpTrap` rows give trap GB per account per day, not trap counts.

## Recipes

### Devices and accounts by device type, one day
Use for: "how many accounts had network devices reporting on day X, by device type". Last used: 2026-09-30.

```sql
SELECT DOMAIN_TYPE AS DEVICE_TYPE,
       COUNT(DISTINCT ACCOUNT_ID) AS ACCOUNTS,
       COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND USAGE_DATE = '{{start_date}}'
GROUP BY DOMAIN_TYPE
ORDER BY DEVICES DESC
```

### Accounts and devices reporting, per day
Use for: adoption trends. Last used: 2026-09-30.

```sql
SELECT USAGE_DATE,
       COUNT(DISTINCT ACCOUNT_ID) AS ACCOUNTS,
       COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND USAGE_DATE >= '{{start_date}}' AND USAGE_DATE < '{{end_date}}'
GROUP BY USAGE_DATE
ORDER BY USAGE_DATE
```

### NPM ingest GB by subgroup
Use for: "NPM ingest split into SNMP, syslog, flow and traps". Last used: 2026-09-30.

```sql
SELECT CASE EVENT_NAME
           WHEN 'Metric' THEN 'SnmpMetric'
           WHEN 'Log' THEN 'Syslog'
           WHEN 'KFlow' THEN 'KFlow'
           WHEN 'KSnmpTrap' THEN 'SnmpTrap'
           ELSE 'other'
       END AS SUBGROUP,
       SUM(TOTAL_GB) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE USAGE_CATEGORY = 'NetworkMonitoring'
  AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
GROUP BY SUBGROUP
ORDER BY GB DESC
```

### Top accounts by NPM ingest
Use for: the biggest NPM users in a period. Last used: 2026-09-30.

```sql
SELECT SUBSCRIPTION_ACCOUNT_ID, SUM(TOTAL_GB) AS GB
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE USAGE_CATEGORY = 'NetworkMonitoring'
  AND "DATE" >= '{{start_date}}' AND "DATE" < '{{end_date}}'
GROUP BY SUBSCRIPTION_ACCOUNT_ID
ORDER BY GB DESC
LIMIT 20
```

## Pitfalls

- **"NPM customers" has three meanings.** It could be accounts with NPM devices reporting (ELIA), accounts with NPM ingest (II), or the companies behind them (join through `customers.md`). Ask which one before counting, and record the answer in `summary.md`. Critical. Last used: 2026-09-30.
- **`NetworkMonitoring` misses Juniper Mist.** Mist is booked under ELIA `METRIC` `'Metrics'` or `'CustomEvents'`, not `'NetworkMonitoring'`. In ELIA it is `DOMAIN_TYPE LIKE 'INFRA-JUNIPER_MIST_%'`, excluding `NGEP-JUNIPER_MIST_CONNECTION`. In II it is `INSTRUMENTATION_NAME = 'juniper-mist'`. Say in "How I got this" that NPM counts exclude Mist, and include Mist only if the user asks. Critical. Last used: 2026-09-30.
- **ELIA scans are slow.** The table is huge and has no clustering key; only a date filter prunes, and `DOMAIN_TYPE` doesn't. On the XSMALL warehouse one day takes tens of seconds, and a month takes several minutes, past the 5-minute limit. For ranges over a week, check in first or use II, which is small and fast. Last used: 2026-09-30.
- **Which account column.** `ACCOUNT_ID` is where data lands, and `SUBSCRIPTION_ACCOUNT_ID` is the customer contract. Count `ACCOUNT_ID` for "accounts" and `SUBSCRIPTION_ACCOUNT_ID` for "clients", and say which in "How I got this". Last used: 2026-09-30.
- **Quote `DATE`.** II's date column is called `DATE`, so write `"DATE"`. Last used: 2026-09-30.
- **Text flags.** `IS_REPORTING` and `HAS_DAILY_CONSUMPTION` are text with mixed case (`'true'`, `'True'`), so compare with `LOWER(…) = 'true'`. Their meaning isn't confirmed, so don't filter on them unless the user asks. A few device rows have a blank `METRIC`; they are still live entities. Last used: 2026-09-30.
- **Fresh days can be partial.** If the latest day looks low, compare it with the day before and mention it. Last used: 2026-09-30.
````

- [ ] **Step 2: Check its SQL offline**

Run: `.venv/bin/python tests/check_notes.py --dry-run`
Expected: every line is `PASS` (the npm note has 4 blocks), then `0 failed`.

- [ ] **Step 3: Check its size**

Run: `wc -l skills/snowflake/references/npm.md`
Expected: under 300 (100).

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/references/npm.md
git commit -m "Add the NPM adoption and usage reference note"
```

### Task 19: `tables.md` and `updater.md`

**Files:**
- Create: `skills/snowflake/references/tables.md`
- Create: `skills/snowflake/references/updater.md`

**Interfaces:**
- Consumes: spec §6.3, the P13 folder rule and the P10 placeholder list.
- Produces: the empty table index and the `/snowflake learn` procedure that `SKILL.md` (Task 20) points to, and that Tasks 32–34 test. Neither file has a `sql` block, so the knowledge checks skip them; their format examples use `text` blocks.

- [ ] **Step 1: Write the table index** — `skills/snowflake/references/tables.md`, exactly:

````markdown
# Table index

Check this before searching the catalog. `/snowflake learn` builds it from past runs, following
`updater.md`. Each entry says what a table holds, its key columns and their meaning, its gotchas and
when a question last used it. It never holds row counts, full column lists or customer data.

Entry format:

```text
### DATABASE.SCHEMA.TABLE
Holds: <one line>. Key columns: `COL` (meaning), `COL` (meaning). Gotchas: <or "none">.
Last used: YYYY-MM-DD.
```

## Tables

None yet. `/snowflake learn` adds them.
````

- [ ] **Step 2: Write the updater procedure** — `skills/snowflake/references/updater.md`, exactly:

````markdown
# The updater: `/snowflake learn`

Follow this only when the user types `/snowflake learn` or asks you to learn from past runs. It
uses your normal file tools and `run_query`. The notes it edits are in this skill's `references/`
folder, and the edits stay uncommitted.

## Steps

1. Call `status`. It gives the runs folder. Question folders are exactly
   `<runs>/<YYYY-MM-DD>/<question>/`. List those whose `YYYY-MM-DD/<question>` isn't a line in
   `<runs>/learned.txt`. Ignore `logs/`, `originals/`, `evals/` and every other folder. If none
   are left, say so and stop.
2. In each folder, read every `.sql` file, including ones that failed, and `summary.md`. Never open
   a `.csv`.
3. List the candidates: tables used, queries worth reusing, pitfalls (a failed query and its fix, or
   a trap noted in the summary) and definitions the user confirmed at a check-in. Keep only those
   that pass the bar below.
4. Rewrite each kept query with placeholders from this list: `{{company_name}}`, `{{account_id}}`,
   `{{start_date}}`, `{{end_date}}`, `{{search_term}}`, `{{database}}`, `{{schema}}`, `{{table}}`.
   Re-run every new or changed recipe through `run_query`, with `question="snowflake-learn"` and
   the placeholders filled with the values its source run used. Drop any recipe that fails.
5. Write the entries, in the formats below:
   - table entries go in `tables.md`
   - recipes, pitfalls and definitions go in the matching area note (`npm.md`, `customers.md`,
     `billing.md` or `finding-data.md`)

   Update an existing entry instead of adding a near-copy. Set `Last used:` to the run's date on
   every entry a run used, including the recipes and table entries its `summary.md` lists. If the
   entry already shows a later date, keep the later one.
6. Apply the size limits below.
7. Append each processed folder, and today's `snowflake-learn` folder if step 4 made one, to
   `<runs>/learned.txt`, one `YYYY-MM-DD/<question>` per line.
8. Report in a few lines what you added, updated, merged and removed. Leave the edits uncommitted.

## The bar

Keep an item only if it passes all three tests:
- **It worked**, and still works when re-run.
- **It's reusable.** It can be written with placeholders, and isn't tied to one customer or one day.
- **It's new.** If the notes already cover it, update that entry instead.

It must also pass at least one of these:
- **Changes the answer.** A definition the user confirmed at a check-in, a filter or rule needed
  for correct numbers, or a trap that produced a wrong result. Mark these `Critical.` They are
  always kept and never pruned.
- **Saved effort.** Finding it took searching or a failed attempt.
- **Came up again.** The same table or query shape appears in two or more questions.

Take business definitions only from the user's own check-in answers, never from your own guesses.

## Never store

- results or numbers
- customer names or IDs
- full column lists (store key columns and their meaning; `DESCRIBE` returns the rest in a second)
- facts that go stale, such as row counts or the latest loaded date
- near-copies of an existing recipe

## Size limits

Each note stays under about 300 lines, and `SKILL.md` under 150. When an update would push a note
past its limit, first merge similar entries. Then remove entries whose `Last used:` is more than 90
days ago, oldest first. Never remove an entry marked `Critical.`. Fix or remove a recipe that stops
working.

## Entry formats

```text
### <Recipe name>
Use for: <question shapes>. [Critical.] Last used: YYYY-MM-DD.

<sql block with {{placeholders}}>

- **<Pitfall name>.** <What goes wrong and the fix.> [Critical.] Last used: YYYY-MM-DD.

- **<Term>:** <definition>. Confirmed by the user on YYYY-MM-DD. Critical. Last used: YYYY-MM-DD.
```

Table entries use the format at the top of `tables.md`.
````

- [ ] **Step 3: Check the notes still pass offline**

Run: `.venv/bin/python tests/check_notes.py --dry-run`
Expected: 19 `PASS` lines (the four area notes) and `0 failed`. The two new files add none.

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/references/tables.md skills/snowflake/references/updater.md
git commit -m "Add the table index and the updater procedure"
```

### Task 20: `SKILL.md`

**Files:**
- Move: `Snowflake.md` → `skills/snowflake/SKILL.md` (with `git mv`, so history follows)
- Rewrite: `skills/snowflake/SKILL.md`

**Interfaces:**
- Consumes: the notes from Tasks 15–19 (their catalog content came from `Snowflake.md`) and the tool names `mcp__snowflake__run_query` and `mcp__snowflake__status` from Tasks 11–12.
- Produces: the skill's main document (§6.1). Its frontmatter `allowed-tools` is a YAML list with P7's path rules; Claude Code accepts a string or a list. The title keeps the user's edit, `# Snowflake Skill`. The error table sits under Workflow, so the body keeps §6.1's four parts.

- [ ] **Step 1: Move the file**

Run: `mkdir -p skills/snowflake && git mv Snowflake.md skills/snowflake/SKILL.md && head -1 skills/snowflake/SKILL.md`
Expected: `# Snowflake Skill`. That is the user's uncommitted title edit, which moved with the working-tree file.

- [ ] **Step 2: Replace the file's content** — `skills/snowflake/SKILL.md`, exactly:

````markdown
---
name: snowflake
description: Use for questions that New Relic's internal Snowflake warehouse answers - customer accounts and Salesforce details, account owners (AE, TSM), NPM and network monitoring adoption and ingest, billing and consumption, entitlements, and finding which table holds something - and for explicit Snowflake or SQL requests. Not for a customer's live telemetry (NRQL, dashboards), explaining networking concepts, or general writing.
allowed-tools:
  - mcp__snowflake__run_query
  - mcp__snowflake__status
  - Read(~/Code/Snowflake/**)
  - Read(~/.claude/skills/snowflake/**)
  - Write(~/Code/Snowflake/runs/**)
  - Edit(~/Code/Snowflake/runs/**)
  - Edit(~/Code/Snowflake/skills/snowflake/references/**)
---

# Snowflake Skill

Answer New Relic business-data questions in plain English with read-only Snowflake queries. The
`snowflake` MCP server runs them and saves every query and result under `runs/`.

## Workflow

1. **Understand the question.** Pick a short slug for it, such as `npm-devices-by-type`. Reuse the
   slug for follow-ups that refine the same question; a new question gets a new slug.
2. **Look before searching.** Read `references/tables.md` and the recipes in the matching area note
   (index below). Search Snowflake's catalog (`references/finding-data.md`) only if nothing fits.
3. **Check in only when it matters.** Ask one plain-English question, with the options, only when:
   - a term has more than one reasonable meaning (for example "NPM customers"), or
   - a query would be slow or expensive: a large table without an account or date filter, a
     result over 100,000 rows, or a time limit above 300 seconds.

   Otherwise run straight away.
4. **Warn before a login.** Call `status` first. If it says "Not logged in", tell the user in one
   sentence that an Okta login tab is about to open in their browser (about 20 seconds).
5. **Run the queries** with `run_query`: `question` is the slug, and `step` names the query. Run
   independent queries in parallel and dependent ones in order.
6. **Write `summary.md`** in the question folder (the folder of the `SQL:` path that `run_query`
   returns). Include the answer and "How I got this", any check-in answer the user gave, the
   recipes you used (by heading) and the `tables.md` entries you used.
7. **Answer** in this order:
   1. the result in plain English
   2. a small table, if useful
   3. "How I got this": definitions, tables, date range and caveats
   4. the SQL

   Link the question folder. Never paste a large result; the preview and the CSV path are enough.

### When `run_query` returns an error

| Code | What to do |
|---|---|
| `BLOCKED` | Explain why. Never retry it as a write. |
| `LOGIN_TIMEOUT` | Tell the user the login didn't finish. The next call reopens it. |
| `LOGIN_FAILED` | Tell the user the login failed, with the message. The next call retries. |
| `LOGIN_EXPIRED` | Tell the user a login tab will open, then call again. |
| `TIMEOUT` | Suggest a narrower query, or ask the user to allow up to 60 minutes (`timeout_seconds` up to 3600). |
| `SQL_ERROR` | Read the message, fix the query and retry up to two times. After that, tell the user. |
| `INTERNAL_ERROR` | Tell the user, and retry at most once. |

If the tools are missing or hang, `/mcp` reconnect or a new window resets the server.

## Rules

- Only read. The server refuses anything else, so never look for a way around it.
- Query production databases only. Never query `*_DEV`, `*_STAGING` or `DEV_*` unless the user
  asks.
- `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` is append-only, the financial system of record.
- Use `LIMIT` while exploring. Use date filters or `SAMPLE` on tables over 100M rows; the warehouse
  is XSMALL.
- Keep the 5-minute default time limit, and raise it only after the user agrees.
- Write outputs only to the question's `runs/` folder, never to the current project unless the
  user asks.
- Customer names and IDs stay in `runs/`. Never write them into the reference notes.

## Learning

- When the user types `/snowflake learn`, or asks you to learn from past runs, follow
  `references/updater.md` instead of the workflow above.
- After an answer, if `status` reported 5 or more unlearned question folders, add one line
  suggesting `/snowflake learn`. Do this at most once per window.
- Note edits stay uncommitted until the user asks to commit.

## Reference index

- `references/tables.md`: tables used before, with key columns and gotchas. Read it first.
- `references/npm.md`: NPM devices, device types, accounts and ingest (ELIA and Instrumentation Insights).
- `references/customers.md`: Salesforce accounts, billing addresses, AE and TSM owners, orgs, entitlements, and account ID to company.
- `references/billing.md`: usage and consumption, `ALL_DAILY_USAGE` rules, product lines and metrics.
- `references/finding-data.md`: warehouse layout, naming and discovery queries, for when nothing else fits.
- `references/updater.md`: only for `/snowflake learn`.
````

- [ ] **Step 3: Check size, name and links**

Run:

```bash
wc -l skills/snowflake/SKILL.md
grep -c "^name: snowflake$" skills/snowflake/SKILL.md
for f in $(grep -o "references/[a-z-]*\.md" skills/snowflake/SKILL.md | sort -u); do test -f "skills/snowflake/$f" || echo "MISSING $f"; done
```

Expected: under 150 lines (88), then `1`, and no `MISSING` lines. Task 23 confirms that Claude Code loads the frontmatter.

- [ ] **Step 4: Commit**

```bash
git add skills/snowflake/SKILL.md   # git mv already staged the move; this adds the new content
git commit -m "Move Snowflake.md to the skill's SKILL.md and rewrite it as the skill document"
```

### Task 21: End-to-end evals

**Files:**
- Create: `skills/snowflake/evals/evals.md` (prompts with placeholders only)
- Create: `tests/run_eval.py` (runs one prompt in a fresh headless window)
- Test: `tests/test_run_eval.py`

**Interfaces:**
- Consumes: spec §10.4 and P11/P18. It reads `runs/evals/values.toml`, which Task 27 writes with keys `company_a`, `company_b`, `company_c` and `npm_account_id`.
- Produces: `.venv/bin/python tests/run_eval.py <E1..E10> <skill|baseline>`. It writes `transcript.jsonl`, `answer.md`, `facts.json` and `stderr.txt` under `runs/evals/<YYYY-MM-DD>/<id>-<mode>/`. `facts.json` holds `skill_triggered`, `status_calls`, `run_query_calls`, `permission_denials`, `files_in_scratch_folder` and `repo_changes_outside_runs`. Tasks 29–30 grade from these files.
- Design: the skill run passes no `--allowedTools`, so it proves the skill's own `allowed-tools` (P7) work from another folder. The baseline pre-allows the two MCP tools; otherwise headless mode would deny every query and the comparison would be empty.

- [ ] **Step 1: Write the evals** — `skills/snowflake/evals/evals.md`, exactly:

````markdown
# End-to-end evals

Each prompt runs in a fresh headless Claude window, from an empty scratch folder outside the repo:
first with all skills off (baseline), then with the skill. Both have the `snowflake` MCP server.
`tests/run_eval.py` fills the placeholders from `runs/evals/values.toml`, which is gitignored and
holds the real company names and account IDs.

| ID | Prompt | Must |
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

## Checks for every prompt that triggers the skill

1. It saves its queries, CSVs and `summary.md` in its `runs/` question folder.
2. It writes nothing outside `runs/`: `files_in_scratch_folder` and `repo_changes_outside_runs` are both empty.
3. Its answer follows the §3 order: the result, a small table if useful, "How I got this", then the SQL.
4. It has no permission denials (`permission_denials` is 0).

Across the set, check-ins happen on E3 and E7, and on no other prompt. A headless window can't
reply, so a check-in shows as a final answer that asks the user to choose, with no `run_query`
call that scans the data in question.

## Pass rule

A prompt passes when its "Must" and the four checks hold. The skill must meet more checks than
the baseline on every prompt that triggers it (§10.6).
````

- [ ] **Step 2: Write the failing test** — `tests/test_run_eval.py`

```python
import pytest

from run_eval import EVALS, facts, load_prompt


def test_every_eval_prompt_loads_with_its_placeholders_filled():
    values = {"company_a": "Acme", "company_b": "Globex", "company_c": "Initech", "npm_account_id": 42}
    text = EVALS.read_text()
    prompts = {f"E{i}": load_prompt(f"E{i}", text, values) for i in range(1, 11)}
    assert prompts["E4"] == "Who are the AE and TSM for Acme?"
    assert prompts["E6"] == "How much data did account 42 ingest per day last week?"
    assert not any("{{" in p for p in prompts.values())


def test_a_missing_value_is_named():
    with pytest.raises(KeyError, match="company_a"):
        load_prompt("E4", EVALS.read_text(), {})


def test_facts_reads_a_stream_json_transcript():
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "snowflake"}},
            {"type": "tool_use", "name": "mcp__snowflake__status", "input": {}},
            {"type": "tool_use", "name": "mcp__snowflake__run_query", "input": {"sql": "SELECT 1"}},
        ]}},
        {"type": "result", "result": "Answer text", "permission_denials": []},
    ]
    assert facts(events) == {"skill_triggered": True, "status_calls": 1, "run_query_calls": 1,
                             "permission_denials": 0, "answer": "Answer text"}

```

Run: `.venv/bin/python -m pytest tests/test_run_eval.py -q`
Expected: `ModuleNotFoundError: No module named 'run_eval'`.

- [ ] **Step 3: Write the runner** — `tests/run_eval.py`

```python
"""Run one end-to-end eval (spec §10.4) in a fresh headless Claude window.

Usage: .venv/bin/python tests/run_eval.py <E1..E10> <skill|baseline>

Fills {{placeholders}} from runs/evals/values.toml and runs from an empty scratch folder outside
the repo. Saves the transcript, answer and facts under runs/evals/<YYYY-MM-DD>/<id>-<mode>/, and
prints the facts a grader needs. It never grades the answer.
"""
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "skills" / "snowflake" / "evals" / "evals.md"
VALUES = REPO / "runs" / "evals" / "values.toml"
CLAUDE = "/opt/homebrew/bin/claude"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def load_prompt(eval_id: str, evals_text: str, values: dict) -> str:
    """The prompt for eval_id from the evals.md table, with placeholders filled."""
    for line in evals_text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == eval_id:
            missing = sorted(set(PLACEHOLDER.findall(cells[1])) - set(values))
            if missing:
                raise KeyError(", ".join(missing))
            return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), cells[1])
    raise KeyError(f"no eval {eval_id}")


def facts(events: list[dict]) -> dict:
    """What happened in a stream-json transcript: skill use, tool calls, denials, final answer."""
    uses = [part for event in events if event.get("type") == "assistant"
            for part in event.get("message", {}).get("content", []) if part.get("type") == "tool_use"]
    result = next((event for event in events if event.get("type") == "result"), {})
    return {
        "skill_triggered": any(u["name"] == "Skill" and u.get("input", {}).get("skill") == "snowflake"
                               for u in uses),
        "status_calls": sum(u["name"] == "mcp__snowflake__status" for u in uses),
        "run_query_calls": sum(u["name"] == "mcp__snowflake__run_query" for u in uses),
        "permission_denials": len(result.get("permission_denials", [])),
        "answer": result.get("result", ""),
    }


def repo_changes_outside_runs() -> set[str]:
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                            capture_output=True, text=True, check=True).stdout
    return {line for line in status.splitlines() if not line[3:].startswith("runs/")}


def main(argv: list[str] | None = None) -> int:
    eval_id, mode = (argv if argv is not None else sys.argv[1:])[:2]
    if mode not in ("skill", "baseline"):
        raise SystemExit("mode must be skill or baseline")
    values = tomllib.loads(VALUES.read_text(encoding="utf-8"))
    prompt = load_prompt(eval_id, EVALS.read_text(encoding="utf-8"), values)
    out = REPO / "runs" / "evals" / date.today().isoformat() / f"{eval_id}-{mode}"
    out.mkdir(parents=True, exist_ok=True)
    before = repo_changes_outside_runs()
    cmd = [CLAUDE, "-p", prompt, "--model", "sonnet", "--output-format", "stream-json",
           "--verbose", "--no-session-persistence"]
    if mode == "baseline":  # P11: the server stays, skills go; its tools are pre-allowed
        cmd += ["--disable-slash-commands",
                "--allowedTools", "mcp__snowflake__run_query", "mcp__snowflake__status"]
    with tempfile.TemporaryDirectory() as scratch:
        proc = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=1800)
        stray = sorted(p.name for p in Path(scratch).iterdir())
    (out / "transcript.jsonl").write_text(proc.stdout, encoding="utf-8")
    (out / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    found = facts([json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")])
    (out / "answer.md").write_text(found.pop("answer"), encoding="utf-8")
    found["files_in_scratch_folder"] = stray
    found["repo_changes_outside_runs"] = sorted(repo_changes_outside_runs() - before)
    (out / "facts.json").write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"{eval_id} {mode}: {json.dumps(found)}\nSaved in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: `114 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/snowflake/evals/evals.md tests/run_eval.py tests/test_run_eval.py
git commit -m "Add the end-to-end eval prompts and their headless runner"
```

### Task 22: Snowflake settings file

**Files:**
- Create: `~/.snowflake/connections.toml` (outside the repo; not committed)

**Interfaces:**
- Produces: the `[newrelic]` connection that `default_connect()` (Task 10) opens with `connection_name="newrelic"`. It holds no secrets (D6); Okta supplies the login.

- [ ] **Step 1: Look before writing**

Run: `ls -la ~/.snowflake/ 2>&1; test -f ~/.snowflake/connections.toml && grep -n "^\[" ~/.snowflake/connections.toml`
Expected on 2026-09-30: `No such file or directory`. If the file exists, don't overwrite it. If it has no `[newrelic]` section, append the section from Step 2. If it has one, compare the values with Step 2 and stop to report any difference.

- [ ] **Step 2: Write the file with mode 600**

```bash
mkdir -p ~/.snowflake
cat > ~/.snowflake/connections.toml <<'TOML'
[newrelic]
account = "pda47359.us-east-1"
user = "JKARNIK"
authenticator = "externalbrowser"
role = "FR_PRODUCT_ANALYST"
warehouse = "TEAM_PRODUCT_ANALYST_XSMALL"
TOML
chmod 600 ~/.snowflake/connections.toml
```

The connector reads `~/.snowflake/` only when that folder exists, so `mkdir` is required.

- [ ] **Step 3: Check the connector reads it, without logging in**

Run: `.venv/bin/python -W always -c "from snowflake.connector.config_manager import CONFIG_MANAGER; print(sorted(CONFIG_MANAGER['connections']['newrelic'].items()))"`
Expected: `[('account', 'pda47359.us-east-1'), ('authenticator', 'externalbrowser'), ('role', 'FR_PRODUCT_ANALYST'), ('user', 'JKARNIK'), ('warehouse', 'TEAM_PRODUCT_ANALYST_XSMALL')]`, with no `Bad owner or permissions` warning. That warning appears if the mode isn't 600.

- [ ] **Step 4: Record progress**

Nothing to commit. Note "Task 22 done (outside repo)" in the progress file.

### Task 23: Register the server and link the skill

**Files:**
- Create: `tests/check_install.py`
- Outside the repo: a user-scope MCP registration named `snowflake` in `~/.claude.json`, and the link `~/.claude/skills/snowflake` → `/Users/jkarnik/Code/Snowflake/skills/snowflake`

**Interfaces:**
- Consumes: `server.py` (Tasks 11–12), `SKILL.md` (Task 20) and the settings file (Task 22).
- Produces: the skill and the server in every new Claude window (§4, §9), plus `.venv/bin/python tests/check_install.py`, which checks the install without a login.

- [ ] **Step 1: Look before changing anything**

Run: `/opt/homebrew/bin/python3.14 -c "import json, os; print(list(json.load(open(os.path.expanduser('~/.claude.json'))).get('mcpServers', {})))"; ls -la ~/.claude/skills/`
Expected on 2026-09-30: `['atlassian']` and an empty folder. Don't use `claude mcp list`, which starts every registered server. If `snowflake` is already registered or linked, stop and report what's there.

- [ ] **Step 2: Register the server at user scope**

Run: `/opt/homebrew/bin/claude mcp add --scope user snowflake -- /Users/jkarnik/Code/Snowflake/.venv/bin/python /Users/jkarnik/Code/Snowflake/skills/snowflake/mcp_server/server.py`
Expected: a line saying the stdio server `snowflake` was added to the user config.

- [ ] **Step 3: Link the skill folder**

Run: `ln -s /Users/jkarnik/Code/Snowflake/skills/snowflake ~/.claude/skills/snowflake && ls -la ~/.claude/skills/`
Expected: `snowflake -> /Users/jkarnik/Code/Snowflake/skills/snowflake`.

- [ ] **Step 4: Write the install check** — `tests/check_install.py`

```python
"""Check the install (spec §9 step 5) without a Snowflake login.

Opens one headless Claude window from a scratch folder, sends a prompt that needs no tools, and
checks that the skill is listed, the snowflake server is connected with both tools, and the
server started without logging in.
"""
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAUDE = "/opt/homebrew/bin/claude"


def checks(init: dict, new_log_lines: list[str]) -> list[tuple[str, bool]]:
    return [
        ("skill 'snowflake' is listed", "snowflake" in init.get("slash_commands", [])),
        ("server 'snowflake' is connected",
         {"name": "snowflake", "status": "connected"} in init.get("mcp_servers", [])),
        ("both tools are available",
         {"mcp__snowflake__run_query", "mcp__snowflake__status"} <= set(init.get("tools", []))),
        ("the server started", any(" server_started" in line for line in new_log_lines)),
        ("no login happened", not any(" login_started" in line for line in new_log_lines)),
    ]


def main() -> int:
    log = REPO / "runs" / "logs" / f"{date.today().isoformat()}.log"
    before = len(log.read_text().splitlines()) if log.exists() else 0
    with tempfile.TemporaryDirectory() as scratch:
        proc = subprocess.run([CLAUDE, "-p", "Reply with the single word OK.", "--model", "haiku",
                               "--output-format", "stream-json", "--verbose", "--no-session-persistence"],
                              cwd=scratch, capture_output=True, text=True, timeout=300)
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    new_lines = log.read_text().splitlines()[before:] if log.exists() else []
    results = checks(init, new_lines)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the install check**

Run: `.venv/bin/python tests/check_install.py`
Expected: five `PASS` lines: skill listed, server connected, both tools available, server started, no login.

If only "skill 'snowflake' is listed" fails, Claude Code isn't following the symlink (§11). Use the copy fallback:
1. Run `rm ~/.claude/skills/snowflake && cp -R skills/snowflake ~/.claude/skills/snowflake`.
2. In `skills/snowflake/references/updater.md`, replace the sentence that begins "The notes it edits are in this skill's `references/` folder" with: "Edit the notes in `~/Code/Snowflake/skills/snowflake/references/`, then run `rsync -a --delete ~/Code/Snowflake/skills/snowflake/ ~/.claude/skills/snowflake/`."
3. Note in the progress file that Task 26's README must include that `rsync` line as the update step.
4. Run the check again.

- [ ] **Step 6: Tell the user**

Say in one line that already-open Claude windows need a restart to see the skill and server. Later tasks use fresh headless windows, so this session needs no restart.

- [ ] **Step 7: Commit**

```bash
git add tests/check_install.py
git commit -m "Add an install check that loads the skill and server without a login"
```

### Task 24: Move the original SQL files into `runs/originals/`

**Files:**
- Move out of git: `company_query.sql` (tracked) → `runs/originals/company_query.sql`
- Move: `Account_owner.sql` (untracked) → `runs/originals/Account_owner.sql`
- Move: `.sfrun/addr.sql` and `.sfrun/addr.tsv` → `runs/originals/`

**Interfaces:**
- Consumes: Tasks 15–18 committed, since their notes now hold these files' knowledge (§8 step 2).
- Produces: the originals kept, gitignored, in `runs/originals/`. The updater never reads that folder (P13). `Account_owner.sql` and `addr.tsv` carry customer data, so they must end up only in gitignored places.

- [ ] **Step 1: Fingerprint the four files**

Run: `shasum -a 256 company_query.sql Account_owner.sql .sfrun/addr.sql .sfrun/addr.tsv | awk '{print $1}' | sort > /tmp/originals-before.txt && wc -l < /tmp/originals-before.txt`
Expected: `4`. If any file is missing, stop and report; never recreate or delete it.

- [ ] **Step 2: Move them**

```bash
mkdir -p runs/originals
mv company_query.sql Account_owner.sql .sfrun/addr.sql .sfrun/addr.tsv runs/originals/
git rm --cached -q company_query.sql
```

- [ ] **Step 3: Verify nothing was lost and git sees only the one removal**

Run: `(cd runs/originals && shasum -a 256 company_query.sql Account_owner.sql addr.sql addr.tsv | awk '{print $1}' | sort) | diff - /tmp/originals-before.txt && echo SAME; git check-ignore -q runs/originals/Account_owner.sql && echo IGNORED; git status --short`
Expected: `SAME`, `IGNORED`, then a status that includes `D  company_query.sql`. It must not show `Account_owner.sql` anywhere.

- [ ] **Step 4: Commit**

```bash
git commit -m "Move the original SQL files into the gitignored runs/originals/"
```

### Task 25: Retire the old toolkit

**Files:**
- Delete (tracked; git keeps their history): `CLAUDE.md`, `session_server.py`, `q`
- Delete (untracked): `.sfrun/`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 20 (`SKILL.md` replaces `CLAUDE.md`, D7) and Task 24 (the addr files are out of `.sfrun/`).
- Produces: a repo with no old toolkit (§8 steps 3 and 5).

- [ ] **Step 1: Make sure the old toolkit isn't in use (P12)**

Run: `pgrep -fl session_server.py || echo "none running"`
Expected: `none running`. If a process is listed, stop. Tell the user in plain English that an older Snowflake session from the pre-skill toolkit is still running in another window, and ask them to finish that work and say when. Never kill it.

- [ ] **Step 2: Check `.sfrun/` holds only runtime leftovers**

Run: `ls -A .sfrun`
Expected: only `cmd.fifo`, `resp.fifo` and the `q.*` temp files (on 2026-09-30: `q.hhRQp5`, `q.hhRQp5.sql` and `q.hhRQp5.sql.out`, holding a `SELECT CURRENT_USER()` query and two empty files). If anything else is there, stop and report it.

- [ ] **Step 3: Delete the toolkit**

```bash
git rm -q CLAUDE.md session_server.py q
rm -rf .sfrun
```

- [ ] **Step 4: Replace `.gitignore`** with exactly:

```gitignore
# Python virtual environment (regenerable from scratch)
.venv/

# Everything the skill produces: question folders, server logs, originals, eval values
runs/

# Python caches
__pycache__/
.pytest_cache/
```

- [ ] **Step 5: Verify**

Run: `git status --short && .venv/bin/python -m pytest -q | tail -1`
Expected: `D  CLAUDE.md`, `D  q`, `D  session_server.py` and ` M .gitignore`, then `114 passed`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "Retire the old session_server/q toolkit and its CLAUDE.md"
```

### Task 26: README

**Files:**
- Modify: `README.md` (full rewrite, §8 step 4)

**Interfaces:**
- Consumes: the commands from Tasks 1, 22, 23, 14, 21 and 27.
- Produces: the user-facing guide: what the skill is, install, update, uninstall and tests (§7).

- [ ] **Step 1: Replace `README.md`** with exactly the text below. If Task 23 used the copy fallback, add this line to "Update": "After any change in `skills/snowflake/`, run `rsync -a --delete skills/snowflake/ ~/.claude/skills/snowflake/`."

````markdown
# Snowflake skill

A personal Claude Code skill that answers New Relic business-data questions from Snowflake:
customer accounts and Salesforce details, account owners, NPM adoption and ingest, billing and
consumption, and which table holds what. Ask in plain English from any project, or type
`/snowflake`. Type `/snowflake learn` to turn past questions into better notes.

| Path | What it is |
|---|---|
| `skills/snowflake/SKILL.md` | The skill: when it applies, its workflow and rules |
| `skills/snowflake/references/` | Notes per question area, improved by `/snowflake learn` |
| `skills/snowflake/mcp_server/` | The `snowflake` MCP server: read-only guard, Okta login on first use, CSV results |
| `skills/snowflake/evals/` | End-to-end test prompts (placeholders only) |
| `tests/` | Unit tests and check scripts |
| `runs/` (gitignored) | One folder per question (`runs/<date>/<question>/`) with its SQL, CSVs and `summary.md`; server logs in `runs/logs/` |

## How it works

Each Claude window starts its own `snowflake` server, logged out. The first Snowflake query in a
window opens an Okta login tab, which takes about 20 seconds. The rest of that window reuses the
login. Windows that never query Snowflake never ask. The server runs only `SELECT`, `SHOW` and
`DESCRIBE`, and refuses everything else before it reaches Snowflake.

## Install (once)

1. `.venv/bin/pip install -r requirements.txt`
2. Create `~/.snowflake/connections.toml` with mode `600`. It holds no password; Okta handles the login.

   ```toml
   [newrelic]
   account = "pda47359.us-east-1"
   user = "JKARNIK"
   authenticator = "externalbrowser"
   role = "FR_PRODUCT_ANALYST"
   warehouse = "TEAM_PRODUCT_ANALYST_XSMALL"
   ```
3. `claude mcp add --scope user snowflake -- "$PWD/.venv/bin/python" "$PWD/skills/snowflake/mcp_server/server.py"`
4. `ln -s "$PWD/skills/snowflake" ~/.claude/skills/snowflake`
5. Restart open Claude windows. Then run `.venv/bin/python tests/check_install.py`; it should print five `PASS` lines and open no login.

## Update

Edits in this repo reach new Claude windows without reinstalling. After changing
`requirements.txt`, repeat install step 1. Note edits from `/snowflake learn` stay uncommitted
until you commit them.

## Uninstall

`claude mcp remove --scope user snowflake`, then `rm ~/.claude/skills/snowflake`. Optionally delete
`~/.snowflake/connections.toml`.

## Tests

- Unit tests, no Snowflake: `.venv/bin/python -m pytest`
- Note queries, offline: `.venv/bin/python tests/check_notes.py --dry-run`
- Live checks, which open Okta logins:
  - `.venv/bin/python tests/check_notes.py`: every example query in the notes (one login)
  - `.venv/bin/python tests/live_login_check.py`: no login without a query, one login for three queries
  - `.venv/bin/python tests/run_eval.py <E1..E10> <skill|baseline>`: one eval in a fresh window

  They read real test values (company names, account IDs) from `runs/evals/values.toml`, which is gitignored.
````

- [ ] **Step 2: Check the README names only files that exist**

Run: `for f in requirements.txt skills/snowflake/SKILL.md skills/snowflake/references skills/snowflake/mcp_server/server.py skills/snowflake/evals tests/check_install.py tests/check_notes.py tests/run_eval.py; do test -e "$f" || echo "MISSING $f"; done`
Expected: no output. `tests/live_login_check.py` arrives in Task 27; that task rechecks the README.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Rewrite the README for the Snowflake skill"
```

### Task 27: Live login checks and eval values — **LIVE (1 Okta login)**

**Files:**
- Create: `tests/live_login_check.py`
- Writes (gitignored): `runs/evals/values.toml`, and a `runs/<today>/live-login-check/` question folder

**Interfaces:**
- Consumes: the installed skill and server (Task 23) and the event names from Task 8.
- Produces: the §10.3 results, and `runs/evals/values.toml` with every P10 key. `start_date` and `end_date` span one day, so ELIA recipes stay cheap in the knowledge checks. The keys are: `company_a`, `company_b`, `company_c`, `npm_account_id`, `company_name`, `account_id`, `start_date`, `end_date`, `search_term`, `database`, `schema`, `table`. Tasks 28–30 read it.

- [ ] **Step 1: Warn the user and wait**

Tell the user in plain English that this check opens one Okta login tab in their browser, about a minute after it starts, and that they should complete it within 2 minutes. Wait for their go-ahead.

- [ ] **Step 2: Write the script** — `tests/live_login_check.py`

```python
"""Live login checks (spec §10.3) that also pick real values for the evals. LIVE: one Okta login.

Window A sends a prompt that needs no Snowflake and must not log in. Window B runs three queries
and must log in exactly once. Window B's results fill runs/evals/values.toml (gitignored), which
the knowledge checks and evals read. It prints value names only, never values.
"""
import csv
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "runs"
CLAUDE = "/opt/homebrew/bin/claude"
QUESTION = "live-login-check"
QUERIES = {
    "company-a": (
        "WITH roles AS (SELECT ATM.ACCOUNT_ID AS SFDC_ACCOUNT_ID, "
        "MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'AE' THEN U.NAME END) AS AE_NAME, "
        "MAX(CASE WHEN ATM.TEAM_MEMBER_ROLE = 'Technical Success Manager' THEN U.NAME END) AS TSM_NAME "
        "FROM TRANSFORMED.COMMON.ACCOUNT_TEAM_MEMBER_D ATM "
        "JOIN TRANSFORMED.SALES.SFDC_USER_D U ON ATM.USER_ID = U.USER_ID "
        "WHERE ATM.IS_DELETED = FALSE AND ATM.TEAM_MEMBER_ROLE IN ('AE', 'Technical Success Manager') "
        "GROUP BY ATM.ACCOUNT_ID) "
        "SELECT ACC.SFDC_ACCOUNT_NAME FROM roles R "
        "JOIN TRANSFORMED.SALES.SFDC_ACCOUNT_D ACC ON ACC.SFDC_ACCOUNT_ID = R.SFDC_ACCOUNT_ID "
        "WHERE R.AE_NAME IS NOT NULL AND R.TSM_NAME IS NOT NULL LIMIT 1"),
    "companies-bc": (
        "SELECT DISTINCT NAME FROM CONFORMED.SFDC.STG_SFDC_ACCOUNT "
        "WHERE CONTAINS(BILLING_STREET, CHR(10)) AND BILLING_COUNTRY IS NOT NULL LIMIT 2"),
    "npm-account": (
        "SELECT ACCOUNT_ID FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F "
        "WHERE METRIC = 'NetworkMonitoring' AND USAGE_DATE = DATEADD(day, -1, CURRENT_DATE()) LIMIT 1"),
}


def window(prompt: str, *extra: str) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run([CLAUDE, "-p", prompt, "--model", "haiku", "--no-session-persistence",
                        "--disable-slash-commands", *extra],
                       cwd=scratch, capture_output=True, text=True, timeout=600)


def events_by_pid(lines: list[str]) -> dict[str, list[str]]:
    """{pid: [event, ...]} from event-log lines like '2026-10-01T10:00:00 pid=42 logged_in ...'."""
    found: dict[str, list[str]] = {}
    for line in lines:
        match = re.match(r"\S+ pid=(\d+) (\S+)", line)
        if match:
            found.setdefault(match.group(1), []).append(match.group(2))
    return found


def first_column(folder: Path, step: str) -> list[str]:
    files = sorted(folder.glob(f"*-{step}.csv"))
    if not files:
        return []
    with open(files[-1], newline="", encoding="utf-8") as f:
        return [row[0] for row in list(csv.reader(f))[1:] if row]


def write_values(folder: Path, target: Path, today: date) -> list[str]:
    """Write values.toml from Window B's CSVs; return the names that are still missing."""
    a, bc, npm = first_column(folder, "company-a"), first_column(folder, "companies-bc"), first_column(folder, "npm-account")
    values = {"company_a": a[:1], "company_b": bc[:1], "company_c": bc[1:2], "npm_account_id": npm[:1]}
    missing = [name for name, found in values.items() if not found]
    lines = [f"{name} = {found[0] if name == 'npm_account_id' else repr_toml(found[0])}"
             for name, found in values.items() if found]
    if not missing:
        lines += [f"company_name = {repr_toml(a[0])}", f"account_id = {npm[0]}",
                  f'start_date = "{today - timedelta(days=2)}"', f'end_date = "{today - timedelta(days=1)}"',
                  'search_term = "ingest"', 'database = "TRANSFORMED"', 'schema = "PRODUCT_ENGINEERING"',
                  'table = "ENTITY_INGEST_DAILY_F"']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return missing


def repr_toml(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    log = RUNS / "logs" / f"{date.today().isoformat()}.log"
    start = len(log.read_text().splitlines()) if log.exists() else 0
    window("Reply with the single word OK.")
    a_lines = log.read_text().splitlines()[start:] if log.exists() else []
    steps = "\n".join(f'- step "{step}": {sql}' for step, sql in QUERIES.items())
    window(f'Call the mcp__snowflake__run_query tool three times, one after another, with question '
           f'"{QUESTION}" and exactly these steps and SQL. Call no other tool. Then reply DONE.\n{steps}',
           "--allowedTools", "mcp__snowflake__run_query")
    b_lines = log.read_text().splitlines()[start + len(a_lines):]
    a_events = [e for events in events_by_pid(a_lines).values() for e in events]
    b_events = [e for events in events_by_pid(b_lines).values() for e in events]
    missing = write_values(RUNS / date.today().isoformat() / QUESTION, RUNS / "evals" / "values.toml", date.today())
    results = [
        ("window A started a server", "server_started" in a_events),
        ("window A never logged in", "login_started" not in a_events),
        ("window B logged in exactly once", b_events.count("login_started") == 1 and b_events.count("logged_in") == 1),
        ("window B ran three queries", b_events.count("query_finished") == 3),
        ("values.toml has every eval value" + (f" (missing: {', '.join(missing)})" if missing else ""), not missing),
    ]
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Check the script offline before the login**

Run: `.venv/bin/python -c "import sys; sys.path[:0] = ['tests', 'skills/snowflake/mcp_server']; from live_login_check import QUERIES; from guard import check_sql; print({s: check_sql(q) for s, q in QUERIES.items()})"`
Expected: `{'company-a': 'SELECT', 'companies-bc': 'SELECT', 'npm-account': 'SELECT'}`.

- [ ] **Step 4: Run it**

Run: `.venv/bin/python tests/live_login_check.py`
Expected: five `PASS` lines. Don't print or paste the values file; it holds customer names.
- If "logged in exactly once" fails, read that window's lines in `runs/logs/<today>.log` and debug with superpowers:systematic-debugging before changing code.
- If only the values line fails (for example, no NPM rows yesterday), change `-1` to `-2` in the `npm-account` query and run again. That opens one more login, so tell the user first.

- [ ] **Step 5: Commit the script** (never the values)

```bash
git add tests/live_login_check.py
git commit -m "Add the live login check that also picks eval values"
```

### Task 28: Knowledge checks — **LIVE (2 Okta logins, up to 3 if notes need fixes)**

**Files:**
- Modify, only if a check fails: `skills/snowflake/references/{npm,customers,billing,finding-data}.md`

**Interfaces:**
- Consumes: `tests/check_notes.py` (Task 14), the notes (Tasks 15–18) and `runs/evals/values.toml` (Task 27).
- Produces: notes whose every `sql` block runs (§10.2). It also confirms three facts the notes state: the `CONCAT_WS` pitfall (Task 17), the RPM-ID join (§6.2) and the data-centre column behind the US-over-EU rule (Task 16).

- [ ] **Step 1: Warn the user and wait**

Say this task opens two Okta logins, a few minutes apart, and one more only if notes need fixing. Wait for the go-ahead.

- [ ] **Step 2: Run every note query (login 1)**

Run: `.venv/bin/python tests/check_notes.py | tee /tmp/check-notes.txt`
Expected: 19 `PASS` lines and `0 failed`. Keep any `FAIL` lines for Step 3.

- [ ] **Step 3: Probe the facts and any failures in one window (login 2)**

Build the prompt from the template below. Fill `<end_date>` from `runs/evals/values.toml`, list the `FAIL` lines from Step 2 (or "none"), and save it as `/tmp/probe-prompt.txt`. Then run it in a headless window from a scratch folder:

```text
Using mcp__snowflake__run_query with question "knowledge-check-probes", run these, then write
summary.md in that question folder with one short answer per item. Store no customer names.
1. SELECT CONCAT_WS(', ', 'a', NULL) IS NULL AS NULL_WINS
2. SELECT COUNT(DISTINCT U.BILLABLE_RPM_ACCOUNT_ID) AS USAGE_ACCOUNTS, COUNT(DISTINCT R.RPM_ACCOUNT_ID) AS FOUND_IN_SALESFORCE FROM USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE U LEFT JOIN TRANSFORMED.SALES.SFDC_RPM_RECORD_D R ON R.RPM_ACCOUNT_ID = U.BILLABLE_RPM_ACCOUNT_ID AND R.IS_DELETED = FALSE WHERE U.START_TIME >= '<end_date>' AND U.START_TIME < DATEADD(day, 1, '<end_date>')
3. DESCRIBE TABLE USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE, then name the data-centre column, if any.
4. For each failing note query below, find the cause with DESCRIBE or INFORMATION_SCHEMA and give corrected SQL:
<FAIL lines from Step 2, or "none">
```

Run: `cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "$(cat /tmp/probe-prompt.txt)" --model sonnet --no-session-persistence --allowedTools mcp__snowflake__run_query mcp__snowflake__status "Write(~/Code/Snowflake/runs/**)"; cd -`
Expected: a `runs/<today>/knowledge-check-probes/` folder with the SQL, the CSVs and `summary.md`.

- [ ] **Step 4: Apply what the probes found**

Read that folder's `summary.md`, plus the CSVs for items 1–3, which hold only counts, a boolean and column names.
- **Item 1:** if `NULL_WINS` is false, delete the `CONCAT_WS` pitfall from `customers.md`. The recipe stays; it works either way.
- **Item 2:** if `FOUND_IN_SALESFORCE` is under 90% of `USAGE_ACCOUNTS`, rewrite `customers.md` "How accounts join" to say the RPM-ID join covers only part of usage accounts. Otherwise leave it.
- **Item 3:** if a data-centre column exists, put it first in the `ORDER BY` of `billing.md`'s de-duplication (`ORDER BY <COLUMN> ASC, INSERTED_AT DESC`), and name it in the "US wins over EU" pitfall. If none exists, delete that pitfall, since it can't be verified (§6.2).
- **Item 4:** replace each failing block with its corrected SQL, or delete the recipe if no fix works.

Store no numbers in the notes (§6.3).

- [ ] **Step 5: Re-run the checks if Step 4 changed a note (login 3)**

Tell the user first. Run: `.venv/bin/python tests/check_notes.py --dry-run && .venv/bin/python tests/check_notes.py`
Expected: every line `PASS`, then `0 failed`.

- [ ] **Step 6: Commit** (skip if nothing changed)

```bash
git add skills/snowflake/references/
git commit -m "Fix reference notes after the live knowledge checks"
```

### Task 29: Evals E1–E5 — **LIVE (up to 10 Okta logins)**

**Files:**
- Modify, only if a skill run fails: `skills/snowflake/SKILL.md` or the matching note
- Writes (gitignored): `runs/evals/<today>/E1-baseline/` … `E5-skill/` and `runs/evals/<today>/grades.md`

**Interfaces:**
- Consumes: `tests/run_eval.py` (Task 21), `runs/evals/values.toml` (Task 27) and notes that pass live (Task 28).
- Produces: graded results for E1–E5 (§10.4). Task 30 adds E6–E10 to the same `grades.md`.

- [ ] **Step 1: Warn the user and wait**

Say this runs ten Claude windows, one at a time, over about 15 minutes. Each window that queries opens its own Okta login tab, so there are up to ten, and each must be completed. Wait for the go-ahead.

- [ ] **Step 2: Run each prompt, baseline first, one window at a time**

```bash
for id in E1 E2 E3 E4 E5; do
  .venv/bin/python tests/run_eval.py $id baseline
  .venv/bin/python tests/run_eval.py $id skill
done
```

Expected: ten `Saved in …` lines. Don't paste answers into the chat. They can hold customer names and live only in `runs/`.

- [ ] **Step 3: Grade each run into `runs/evals/<today>/grades.md`**

Write one row per run: `| ID | mode | Must | 1 saved | 2 nothing outside runs | 3 answer order | 4 no denials | notes |`. Mark each column yes or no. Grade from `answer.md`, `facts.json` and the SQL files. The skill run's question folder is the one in the `SQL:` paths of its transcript. "Must" means:
- **E1:** SQL on `ENTITY_INGEST_DAILY_F` with `METRIC = 'NetworkMonitoring'` and `GROUP BY` on `DOMAIN_TYPE`. No check-in.
- **E2:** SQL on `NRDB_TDP_USAGE_DAILY_F` with `USAGE_CATEGORY = 'NetworkMonitoring'`, the four `EVENT_NAME` mappings and last month's dates. No check-in.
- **E3:** the final answer asks which definition of "NPM customers" is meant, and names the choices. No counting query ran.
- **E4:** SQL goes from `SFDC_RPM_RECORD_D` to `SFDC_ACCOUNT_D`, `ACCOUNT_TEAM_MEMBER_D` and `SFDC_USER_D`, with roles `'AE'` and `'Technical Success Manager'`. The answer names the AE and TSM, or says none is assigned.
- **E5:** SQL on `STG_SFDC_ACCOUNT` replacing `CHR(10)` and `CHR(13)`. The answer gives a one-line address for each company.

- [ ] **Step 4: Fix skill-run failures at their cause**

For each skill run that misses its "Must" or a check, find the cause in `SKILL.md` or the note, fix the wording, and re-run that eval in skill mode only. Each re-run can open one login, so tell the user first. If `permission_denials` is above 0, the P7 rules in `allowed-tools` didn't take effect. Read the denied tool in `transcript.jsonl` and correct that rule.

- [ ] **Step 5: Commit any fixes** (never eval outputs)

```bash
git add skills/snowflake/
git commit -m "Tune the skill after evals E1-E5"
```

### Task 30: Evals E6–E10 and the pass rule — **LIVE (up to 6 Okta logins)**

**Files:** the same as Task 29.

**Interfaces:**
- Consumes: Task 29's `grades.md`.
- Produces: the full eval result and the §10.6 eval criteria.

- [ ] **Step 1: Warn the user and wait** (up to six logins; E9 and E10 should open none)

- [ ] **Step 2: Run the prompts**

```bash
for id in E6 E7 E8 E9 E10; do
  .venv/bin/python tests/run_eval.py $id baseline
  .venv/bin/python tests/run_eval.py $id skill
done
```

- [ ] **Step 3: Grade into the same `grades.md`**

"Must" means:
- **E6:** SQL on `ALL_DAILY_USAGE` filtered by `BILLABLE_RPM_ACCOUNT_ID`, `GigabytesIngested` and last week, de-duplicated with `ROW_NUMBER()` over account, `START_TIME`, `METRIC` and `PRODUCT_LINE`.
- **E7:** the final answer checks in and offers a summary, with no full-year scan.
- **E8:** the answer names `TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F` with `EVENT_NAME = 'KSnmpTrap'`, and says it holds GB, not counts. Answering from the notes without a query is fine.
- **E9, E10:** in skill mode, `skill_triggered` is false and `run_query_calls` is 0.

Then check across all ten: check-ins happen on E3 and E7 only. On every prompt where the skill triggered, the skill run meets more checks than its baseline (§10.6).

- [ ] **Step 4: Fix and re-run failures** as in Task 29 Step 4.

- [ ] **Step 5: Commit any fixes**

```bash
git add skills/snowflake/
git commit -m "Tune the skill after evals E6-E10"
```

### Task 31: Updater fixtures

**Files:**
- Create: `tests/fixtures/runs/` (six made-up question folders, 14 files)
- Create: `tests/fixtures/expected.md` (the expected outcome, §10.5)

**Interfaces:**
- Consumes: the question-folder layout (P13) and the `summary.md` contents `SKILL.md` asks for.
- Produces: the made-up runs that Tasks 32–33 feed to the updater through `--runs-dir`. They cover every §10.5 case: a table used in two questions (ELIA, in `zorblax-devices-by-collector` and `devices-by-provider`), a query that failed and was fixed (`quimbly-account-name`), a confirmed definition (`npm-customers`), a trivial one-off (`whoami`) and a near-copy of an existing recipe (`npm-gb-by-subgroup-august`). Every name and ID is invented. A canary CSV checks that the updater never opens CSVs.

- [ ] **Step 1: Create the fixtures** by running this script from the repo root:

```bash
mkdir -p tests/fixtures tests/fixtures/runs/2026-09-01/npm-gb-by-subgroup-august tests/fixtures/runs/2026-09-01/zorblax-devices-by-collector tests/fixtures/runs/2026-09-02/devices-by-provider tests/fixtures/runs/2026-09-02/whoami tests/fixtures/runs/2026-09-03/npm-customers tests/fixtures/runs/2026-09-03/quimbly-account-name
cat > tests/fixtures/expected.md <<'FIXTURE'
# Expected outcome of one updater pass over `tests/fixtures/runs/`

All company names and IDs in these runs are invented: Zorblax Networks, Quimbly Foods, 9900001,
0019900002. `CANARY-ROW-DATA-7Q` exists only inside a CSV, which the updater must never open.

After pass 1 (`git diff skills/snowflake/references/`):
1. `tables.md` gains an entry for `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F`, which two questions used.
2. `customers.md` gains a pitfall: `SFDC_ACCOUNT_D` names the column `SFDC_ACCOUNT_NAME`, not `NAME`.
3. `npm.md` gains a definition of "NPM customers": subscription accounts with NPM ingest in
   Instrumentation Insights in the last 30 days, marked `Critical.` and confirmed by the user on
   2026-09-03. The "three meanings" pitfall now points to it rather than contradicting it.
4. `npm.md` still has exactly one "NPM ingest GB by subgroup" recipe (the near-copy merged). Its
   `Last used:` stays 2026-09-30, the later date.
5. Nothing is added for `CURRENT_USER()` (the one-off).
6. At most one new recipe for devices grouped by an ELIA column. Not two near-copies.
7. None of `Zorblax`, `Quimbly`, `9900001`, `0019900002` or `CANARY-ROW-DATA-7Q` appears in any note.
8. Every note stays under 300 lines, and `SKILL.md` is unchanged.
9. `learned.txt` in the test runs folder lists all six question folders.

After pass 2: the updater reports nothing new, and `git diff` is identical to pass 1.
FIXTURE
cat > tests/fixtures/runs/2026-09-01/npm-gb-by-subgroup-august/01-subgroups.sql <<'FIXTURE'
select case event_name when 'Metric' then 'SnmpMetric' when 'Log' then 'Syslog'
            when 'KFlow' then 'KFlow' when 'KSnmpTrap' then 'SnmpTrap' else 'other' end as subgroup,
       sum(total_gb) as gb
from transformed.product_consumption.nrdb_tdp_usage_daily_f
where usage_category = 'NetworkMonitoring'
  and "DATE" >= '2026-08-01' and "DATE" < '2026-09-01'
group by subgroup
order by subgroup
FIXTURE
cat > tests/fixtures/runs/2026-09-01/npm-gb-by-subgroup-august/summary.md <<'FIXTURE'
# NPM ingest by subgroup, August 2026

Answer: NPM ingest in August split across SNMP metrics, syslog, flow and traps.

How I got this: Instrumentation Insights with `USAGE_CATEGORY = 'NetworkMonitoring'` and the event-name mapping.

Check-in: none. Recipes used: npm.md "NPM ingest GB by subgroup". Table entries used: none.
FIXTURE
printf 'COLLECTOR_NAME,DEVICES\r\nCANARY-ROW-DATA-7Q,12\r\n' > tests/fixtures/runs/2026-09-01/zorblax-devices-by-collector/01-devices.csv
cat > tests/fixtures/runs/2026-09-01/zorblax-devices-by-collector/01-devices.sql <<'FIXTURE'
SELECT COLLECTOR_NAME, COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND ACCOUNT_ID = 9900001
  AND USAGE_DATE = '2026-08-31'
GROUP BY COLLECTOR_NAME
ORDER BY DEVICES DESC
FIXTURE
cat > tests/fixtures/runs/2026-09-01/zorblax-devices-by-collector/summary.md <<'FIXTURE'
# Zorblax Networks devices by collector

Answer: Zorblax Networks (account 9900001) had NPM devices reporting through two collectors on 2026-08-31.

How I got this: ELIA, `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F`, with `METRIC = 'NetworkMonitoring'`, one day, grouped by `COLLECTOR_NAME`.

Check-in: none. Recipes used: none. Table entries used: none.
FIXTURE
cat > tests/fixtures/runs/2026-09-02/devices-by-provider/01-providers.sql <<'FIXTURE'
SELECT INSTRUMENTATION_PROVIDER, COUNT(DISTINCT ENTITY_GUID) AS DEVICES
FROM TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F
WHERE METRIC = 'NetworkMonitoring'
  AND USAGE_DATE = '2026-09-01'
GROUP BY INSTRUMENTATION_PROVIDER
ORDER BY DEVICES DESC
FIXTURE
cat > tests/fixtures/runs/2026-09-02/devices-by-provider/summary.md <<'FIXTURE'
# NPM devices by instrumentation provider

Answer: NPM devices on 2026-09-01, counted per instrumentation provider.

How I got this: ELIA, `TRANSFORMED.PRODUCT_ENGINEERING.ENTITY_INGEST_DAILY_F`, with `METRIC = 'NetworkMonitoring'`, one day, grouped by `INSTRUMENTATION_PROVIDER`.

Check-in: none. Recipes used: none. Table entries used: none.
FIXTURE
cat > tests/fixtures/runs/2026-09-02/whoami/01-query.sql <<'FIXTURE'
SELECT CURRENT_USER(), CURRENT_ROLE()
FIXTURE
cat > tests/fixtures/runs/2026-09-02/whoami/summary.md <<'FIXTURE'
# Who am I

Answer: the session runs as the analyst user and role.

Check-in: none. Recipes used: none. Table entries used: none.
FIXTURE
cat > tests/fixtures/runs/2026-09-03/npm-customers/01-count.sql <<'FIXTURE'
SELECT COUNT(DISTINCT SUBSCRIPTION_ACCOUNT_ID) AS NPM_ACCOUNTS
FROM TRANSFORMED.PRODUCT_CONSUMPTION.NRDB_TDP_USAGE_DAILY_F
WHERE USAGE_CATEGORY = 'NetworkMonitoring'
  AND "DATE" >= '2026-08-04' AND "DATE" < '2026-09-03'
FIXTURE
cat > tests/fixtures/runs/2026-09-03/npm-customers/summary.md <<'FIXTURE'
# How many NPM customers

Answer: counted subscription accounts with NPM ingest in the 30 days to 2026-09-02.

Check-in: asked which meaning of "NPM customers". The user chose: subscription accounts with any NPM ingest in Instrumentation Insights (`USAGE_CATEGORY = 'NetworkMonitoring'`) in the last 30 days.

How I got this: Instrumentation Insights, distinct `SUBSCRIPTION_ACCOUNT_ID`, 30 days. Recipes used: none. Table entries used: none.
FIXTURE
cat > tests/fixtures/runs/2026-09-03/quimbly-account-name/01-name.sql <<'FIXTURE'
SELECT NAME FROM TRANSFORMED.SALES.SFDC_ACCOUNT_D WHERE NAME ILIKE '%Quimbly%' LIMIT 10
FIXTURE
cat > tests/fixtures/runs/2026-09-03/quimbly-account-name/02-name-fixed.sql <<'FIXTURE'
SELECT SFDC_ACCOUNT_ID, SFDC_ACCOUNT_NAME
FROM TRANSFORMED.SALES.SFDC_ACCOUNT_D
WHERE SFDC_ACCOUNT_NAME ILIKE '%Quimbly%'
LIMIT 10
FIXTURE
cat > tests/fixtures/runs/2026-09-03/quimbly-account-name/summary.md <<'FIXTURE'
# Quimbly Foods Salesforce account

Answer: Quimbly Foods has Salesforce account 0019900002.

How I got this: 01 failed with SQL_ERROR "invalid identifier 'NAME'". `TRANSFORMED.SALES.SFDC_ACCOUNT_D` calls the column `SFDC_ACCOUNT_NAME`; `NAME` is the column in `CONFORMED.SFDC.STG_SFDC_ACCOUNT`. 02 used `SFDC_ACCOUNT_NAME` and worked.

Check-in: none. Recipes used: none. Table entries used: none.
FIXTURE
```

- [ ] **Step 2: Check them**

Run: `find tests/fixtures -type f | wc -l && .venv/bin/python -c "import sys; sys.path.insert(0, 'skills/snowflake/mcp_server'); from pathlib import Path; from guard import check_sql; from results import unlearned_folders; print(len(unlearned_folders(Path('tests/fixtures/runs'))), {check_sql(f.read_text()) for f in Path('tests/fixtures/runs').rglob('*.sql')})"`
Expected: `15`, then `6 {'SELECT'}`. The fixtures don't affect pytest (`114 passed`), which collects only `test_*.py`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures
git commit -m "Add made-up runs and expected results for the updater tests"
```

### Task 32: Updater pass test — **LIVE (1 Okta login, maybe 2)**

**Files:**
- Modify, only if the test fails at its cause: `skills/snowflake/references/updater.md`
- Writes (gitignored): `runs/updater-test-<time>/` (a copy of the fixtures plus the transcripts)

**Interfaces:**
- Consumes: the fixtures and `expected.md` (Task 31), `updater.md` (Task 19) and `server.py --runs-dir` (Task 11).
- Produces: the §10.5 "made-up runs" result. It runs on the real notes in a clean tree and reverts afterwards (P14).

- [ ] **Step 1: Warn the user and wait** (one login for re-running recipes; a second only if pass 2 re-runs something)

- [ ] **Step 2: Prepare a clean tree and a test runs folder**

```bash
test -z "$(git status --porcelain skills/)" || { echo "commit or stash skills/ first"; exit 1; }
T="$PWD/runs/updater-test-$(date +%H%M%S)"; mkdir -p "$T"; cp -R tests/fixtures/runs "$T/runs"
cat > "$T/mcp.json" <<JSON
{"mcpServers": {"snowflake": {"command": "$PWD/.venv/bin/python",
  "args": ["$PWD/skills/snowflake/mcp_server/server.py", "--runs-dir", "$T/runs"]}}}
JSON
echo "$T"
```

The test folder sits under `runs/`, so the skill's own `Read`/`Write`/`Edit` rules (P7) cover it, and it's gitignored. It's not a date folder, so the real updater ignores it (P13).

- [ ] **Step 3: Pass 1**

Run: `(cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "/snowflake learn" --model sonnet --mcp-config "$T/mcp.json" --strict-mcp-config --output-format stream-json --verbose --no-session-persistence) > "$T/pass1.jsonl"; git diff skills/snowflake/references/ > "$T/pass1.diff"; wc -l "$T/pass1.diff"`
Expected: a non-empty diff.

- [ ] **Step 4: Grade pass 1 against `tests/fixtures/expected.md`**

Check items 1–6 by reading `$T/pass1.diff`. For items 7–9, run:

```bash
grep -rnE "Zorblax|Quimbly|9900001|0019900002|CANARY-ROW-DATA-7Q" skills/snowflake/references/ || echo "no invented data"
wc -l skills/snowflake/references/*.md
git diff --quiet skills/snowflake/SKILL.md && echo "SKILL.md unchanged"
cat "$T/runs/learned.txt"
```

Expected: `no invented data`; every note under 300 lines; `SKILL.md unchanged`; and `learned.txt` lists the six folders, plus `<today>/snowflake-learn` if recipes were re-run.

- [ ] **Step 5: Pass 2 finds nothing new**

Run: `(cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "/snowflake learn" --model sonnet --mcp-config "$T/mcp.json" --strict-mcp-config --output-format stream-json --verbose --no-session-persistence) > "$T/pass2.jsonl"; git diff skills/snowflake/references/ | diff -q - "$T/pass1.diff" && echo "no new changes"`
Expected: `no new changes`, and the final answer in `pass2.jsonl` says nothing was left to learn.

- [ ] **Step 6: Revert the notes (P14)**

Run: `git checkout -- skills/snowflake/references/ && git status --short skills/`
Expected: no output.

- [ ] **Step 7: If an expectation failed**, fix its cause in `updater.md`, commit that fix alone, then repeat Steps 2–6. Tell the user before each repeat, since it opens a login.

```bash
git add skills/snowflake/references/updater.md
git commit -m "Tighten the updater procedure after the fixture test"
```

### Task 33: Size-limit test — **LIVE (1 Okta login)**

**Files:**
- None committed. `billing.md` is padded in the working tree and then reverted.

**Interfaces:**
- Consumes: Task 32's set-up (a fresh `$T` from Task 32 Step 2) and `updater.md`'s size limits.
- Produces: the §10.5 "Size limit" result. A note pushed past 300 lines shrinks by merging and pruning, and keeps every `Critical.` entry.

- [ ] **Step 1: Warn the user and wait** (one login)

- [ ] **Step 2: Repeat Task 32 Step 2** for a fresh `$T`, then pad `billing.md` past its limit:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
note = Path("skills/snowflake/references/billing.md")
pad = [f"- **Old padding entry {i}.** A made-up pitfall nobody has used. Last used: 2026-01-{i % 28 + 1:02d}." for i in range(150)]
pad += [f"- **Similar padding {i}.** Filter the padding table by padding date. Last used: 2026-01-15." for i in range(100)]
pad += ["- **Padding critical entry.** A made-up rule that changes the answer. Critical. Last used: 2026-01-10."]
note.write_text(note.read_text() + "\n".join(pad) + "\n")
print(len(note.read_text().splitlines()))
PY
```

Expected: about `341` (the note's length after Task 28, plus 251), well past the 300-line limit.

- [ ] **Step 3: Run the updater once**

Run: `(cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "/snowflake learn" --model sonnet --mcp-config "$T/mcp.json" --strict-mcp-config --output-format stream-json --verbose --no-session-persistence) > "$T/size.jsonl"`

The fixtures give it something to learn. Step 6 of `updater.md` then has to bring `billing.md` back under the limit.

- [ ] **Step 4: Check the result**

```bash
wc -l skills/snowflake/references/billing.md
grep -c "Padding critical entry" skills/snowflake/references/billing.md
grep -c "Repeated inserts double-count\|Gauges aren't additive" skills/snowflake/references/billing.md
grep -c "Similar padding" skills/snowflake/references/billing.md
```

Expected: under 300 lines; `1`; `2` (the real critical entries survive); and far fewer than 100 "Similar padding" lines, because they were merged. The final answer in `size.jsonl` reports what was merged and removed.

- [ ] **Step 5: Revert (P14)** — `git checkout -- skills/snowflake/references/ && git status --short skills/` shows nothing. If the check failed, fix the size-limit wording in `updater.md` and commit it as in Task 32 Step 7.

### Task 34: Speed check — **LIVE (3 Okta logins)**

**Files:**
- None committed. Notes change in the working tree between windows, then revert.

**Interfaces:**
- Consumes: the whole skill, and Task 32's set-up for a separate test runs folder.
- Produces: the §10.5 speed check. A new kind of question needs fewer `run_query` calls after `/snowflake learn`.

- [ ] **Step 1: Warn the user and wait** (three windows, one login each)

- [ ] **Step 2: Set up an empty test runs folder**

Repeat Task 32 Step 2, but create `"$T/runs"` empty (`mkdir -p "$T/runs"`) instead of copying the fixtures.

- [ ] **Step 3: Ask a new kind of question (window 1)**

Run: `(cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "Which dbt models feed the NPM Instrumentation Insights table, and which Looker dashboards use it?" --model sonnet --mcp-config "$T/mcp.json" --strict-mcp-config --output-format stream-json --verbose --no-session-persistence) > "$T/ask1.jsonl"; grep -o '"name":"mcp__snowflake__run_query"' "$T/ask1.jsonl" | wc -l`
Expected: several calls (call it N1). The notes have no recipe for dbt lineage of one table, so Claude must explore `DBT_ARTIFACTS`.

- [ ] **Step 4: Learn (window 2)**

Run: `(cd "$(mktemp -d)" && /opt/homebrew/bin/claude -p "/snowflake learn" --model sonnet --mcp-config "$T/mcp.json" --strict-mcp-config --no-session-persistence) > "$T/learn.txt"; git diff --stat skills/snowflake/references/`
Expected: `tables.md` or `finding-data.md` changed.

- [ ] **Step 5: Ask again in a fresh window (window 3)**

Run Step 3's command again, writing `"$T/ask2.jsonl"`, and count the calls (N2).
Expected: N2 < N1. Record both in the progress file. If N2 ≥ N1, read what the updater wrote and why window 3 didn't use it. Fix the cause (`SKILL.md` step 2 or the entry wording), commit the fix, and repeat Steps 2–5.

- [ ] **Step 6: Revert (P14)** — `git checkout -- skills/snowflake/references/`

### Task 35: Pass criteria and hand-off

**Files:**
- Modify: the progress file only.

**Interfaces:**
- Consumes: the results of Tasks 1–34.
- Produces: the §10.6 verdict for the user.

- [ ] **Step 1: Re-run everything offline**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python tests/check_notes.py --dry-run | tail -1 && .venv/bin/python tests/check_install.py && git status --short`
Expected: `114 passed` (more if earlier tasks added tests), `0 failed`, five `PASS` lines, and a clean tree.

- [ ] **Step 2: Check each §10.6 criterion** against its evidence:
1. unit tests (Step 1)
2. every note query runs (Task 28)
3. no login without a query, and exactly one login for three queries (Task 27)
4. all ten evals meet "Must" and the checks (Tasks 29–30)
5. the updater tests and speed check (Tasks 32–34)
6. the skill beats the baseline on every prompt that triggers it (Task 30)

- [ ] **Step 3: Leave the §11 sleep check with the user**

This check needs real time, so it can finish after hand-off. Ask the user to do it once:
1. In a Claude window, ask one Snowflake question and complete the login.
2. Leave that window open while the laptop sleeps for at least 4 hours.
3. Ask a second question in the same window.

Pass: within seconds, Claude says the session expired and a login tab will open. The log shows `query_failed code=LOGIN_EXPIRED` and then a new `login_started`, never a silent wait. Note in the progress file whether it has been done.

- [ ] **Step 4: Report to the user in plain English**

Report what passed, anything that failed or was dropped (for example, facts removed in Task 28), and where the evidence is in `runs/`. Then use superpowers:finishing-a-development-branch to offer the merge options. Don't push or merge without the user's choice.
