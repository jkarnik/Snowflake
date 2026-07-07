# Snowflake Query Toolkit

A small set of scripts for querying Snowflake without triggering a browser SSO
popup on every query. Snowflake auth here is Okta SSO via `externalbrowser`, so
each new Python process would normally re-authenticate. The "skill" this repo
provides is a **persistent session**: authenticate once, then run any number of
queries instantly.

- **`README.md`** (this file) — what the scripts are and how they fit together.
- **[CLAUDE.md](CLAUDE.md)** — the operating runbook (exact connect/run commands).
- **[Snowflake.md](Snowflake.md)** — what the data is (tables, business rules).

## The skill: one persistent session

Instead of connecting per query, one background process holds the connection
open and serves queries over named pipes (FIFOs). You authenticate in the
browser **once** per work session; every query after that returns with no
re-auth.

```
  ./q  ──SQL──▶  cmd.fifo  ──▶  session_server.py  ──runs on live connection
   ▲                                    │
   └────── results ◀── resp.fifo ◀──────┘
```

### Run it

```bash
# 1. Make this session's working folder + start the session (opens the browser once).
#    Everything a session produces goes under runs/, keeping the repo root clean.
RUN="runs/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$RUN"; ln -sfn "${RUN#runs/}" runs/latest
.venv/bin/python session_server.py > runs/latest/server.log 2>&1 &

# 2. Wait until authenticated
until grep -q "SESSION READY" runs/latest/server.log; do sleep 1; done

# 3. Query — SQL on stdin, tab-separated results on stdout
echo "SELECT CURRENT_USER();" | ./q

# 4. Shut down cleanly when done
echo QUIT > .sfrun/cmd.fifo
```

Write generated SQL, result exports, CSVs, and any scratch files into
`runs/latest/` — not the repo root. `runs/` is gitignored.

## Files

### Core session tooling

| File | What it does |
|------|--------------|
| `session_server.py` | Long-lived process. Authenticates once, then loops: reads a `.sql` file path from `cmd.fifo`, runs the statements on the open connection, writes tab-separated results to `<file>.out`, and returns that path on `resp.fifo`. Splits input on `;`; errors are written as `ERROR:` + traceback. Exits on `QUIT`. |
| `q` | Thin client (zsh). Reads SQL from stdin, hands it to the running server via the FIFOs, and prints the results. This is the everyday entry point — pipe SQL in, get results out. |

### Runtime / environment

| Path | What it is |
|------|------------|
| `.sfrun/` | Runtime artifacts — the `cmd.fifo` / `resp.fifo` pipes and temp `.sql`/`.out` files. Gitignored; recreated each time the server starts. |
| `runs/<timestamp>/` | One folder per work session holding the server log and all query artifacts. `runs/latest` symlinks the current session. Gitignored. |
| `runs/latest/server.log` | Current session's server stdout/stderr (look here for `SESSION READY`). |
| `.venv/` | Python env with `snowflake-connector-python[secure-local-storage]`. Run everything with `.venv/bin/python`. |


## Connection settings

All scripts connect with the same parameters (edit in `session_server.py`
if yours differ):

- **account** `pda47359.us-east-1`
- **user** `JKARNIK`
- **authenticator** `externalbrowser` (Okta SSO)
- **role** `FR_PRODUCT_ANALYST`
- **warehouse** `TEAM_PRODUCT_ANALYST_XSMALL`

## Query discipline

From [Snowflake.md](Snowflake.md) — always `LIMIT` while exploring, use date
filters or `SAMPLE` on 100M+ row tables, and **never** `DELETE`/`DROP` on
`USAGE_AND_RATING.USAGE.ALL_DAILY_USAGE` (append-only financial system of record).
