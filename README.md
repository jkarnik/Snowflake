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
