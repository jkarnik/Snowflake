# Snowflake Repo — Operating Instructions

Reference doc for data architecture, table inventory, and business rules: [Snowflake.md](Snowflake.md).
This file is **how to connect and run queries**. Snowflake.md is **what the data is**.

## Connecting: use ONE persistent session (never per-query connects)

Snowflake auth here is Okta SSO via `externalbrowser`. Every new Python process =
a new connection = a new browser popup. So **do not** run a fresh `python` connect
per query. Instead, start one long-lived session and feed queries to it.

### Setup (once per work session)

1. Create this session's working folder and start the background session server
   (opens the browser **once**). All logs and artifacts go under `runs/`, not the
   repo root:
   ```bash
   RUN="runs/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$RUN"; ln -sfn "${RUN#runs/}" runs/latest
   .venv/bin/python session_server.py > runs/latest/server.log 2>&1 &
   ```
2. Wait until it's authenticated:
   ```bash
   until grep -q "SESSION READY" runs/latest/server.log; do sleep 1; done
   ```
3. Run queries through the thin client — SQL on stdin, results on stdout:
   ```bash
   echo "SELECT CURRENT_USER();" | ./q
   ```

The session holds the connection open, so `./q` returns instantly with **no** re-auth
for the rest of the session. Statements are split on `;`. Errors print as `ERROR:` + traceback.

**Keep the root clean:** write every artifact this session produces — generated SQL,
result exports, CSVs, scratch files — under `runs/latest/`. Never drop working files
in the repo root. `runs/` is gitignored.

### Shutting down
```bash
echo QUIT > .sfrun/cmd.fifo   # stops the server cleanly
```

## Files
- `session_server.py` — long-lived connection; serves queries over FIFOs in `.sfrun/` (`cmd.fifo` / `resp.fifo`).
- `q` — client wrapper; pipe SQL in, get tab-separated results out.
- `.sfrun/` — runtime artifacts (FIFOs, temp SQL). Gitignored; recreated on each server start.
- `runs/<timestamp>/` — one folder per work session for logs and all query artifacts; `runs/latest` symlinks the current one. Gitignored.
- `.venv/` — Python env with `snowflake-connector-python[secure-local-storage]`. Run everything with `.venv/bin/python`.

## Query discipline (from Snowflake.md)
- Always `LIMIT` during exploration; use date filters or `SAMPLE` on 100M+ row tables (XSMALL warehouse).
- Never `DELETE`/`DROP` on `USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` — append-only, financial system of record.
- Query production DBs (CONFORMED, TRANSFORMED, REPORTING) unless explicitly testing.
