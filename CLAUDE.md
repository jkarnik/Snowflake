# Snowflake Repo — Operating Instructions

Reference doc for data architecture, table inventory, and business rules: [Snowflake.md](Snowflake.md).
This file is **how to connect and run queries**. Snowflake.md is **what the data is**.

## Connecting: use ONE persistent session (never per-query connects)

Snowflake auth here is Okta SSO via `externalbrowser`. Every new Python process =
a new connection = a new browser popup. So **do not** run a fresh `python` connect
per query. Instead, start one long-lived session and feed queries to it.

### Setup (once per work session)

1. Start the background session server (opens the browser **once**):
   ```bash
   .venv/bin/python session_server.py > .sf_server.log 2>&1 &
   ```
2. Wait until it's authenticated:
   ```bash
   until grep -q "SESSION READY" .sf_server.log; do sleep 1; done
   ```
3. Run queries through the thin client — SQL on stdin, results on stdout:
   ```bash
   echo "SELECT CURRENT_USER();" | ./q
   ```

The session holds the connection open, so `./q` returns instantly with **no** re-auth
for the rest of the session. Statements are split on `;`. Errors print as `ERROR:` + traceback.

### Shutting down
```bash
echo QUIT > .sf_cmd.fifo   # stops the server cleanly
```

## Files
- `session_server.py` — long-lived connection; serves queries over FIFOs (`.sf_cmd.fifo` / `.sf_resp.fifo`).
- `q` — client wrapper; pipe SQL in, get tab-separated results out.
- `.venv/` — Python env with `snowflake-connector-python[secure-local-storage]`. Run everything with `.venv/bin/python`.
- `query.py` — legacy one-shot (opens a new connection each run; avoid — kept only for a quick standalone test).

## Query discipline (from Snowflake.md)
- Always `LIMIT` during exploration; use date filters or `SAMPLE` on 100M+ row tables (XSMALL warehouse).
- Never `DELETE`/`DROP` on `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` — append-only, financial system of record.
- Query production DBs (CONFORMED, TRANSFORMED, REPORTING) unless explicitly testing.
