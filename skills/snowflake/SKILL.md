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
  - Edit(~/.claude/skills/snowflake/references/**)
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
4. **Warn before a login.** Call `status` on its own first, before any query, and wait for its
   answer. If it says "Not logged in", tell the user in one sentence that an Okta login tab is
   about to open in their browser (about 20 seconds).
5. **Run the queries** with `run_query`: `question` is the slug, and `step` names the query. Run
   independent queries in parallel and dependent ones in order.
6. **Write `summary.md`** in the question folder (the folder of the `SQL:` path that `run_query`
   returns). Include the answer and "How I got this", any check-in answer the user gave, the
   recipes you used (by heading) and the `tables.md` entries you used.
7. **Answer** in this order:
   1. the result in plain English
   2. a small table, if useful
   3. "How I got this": definitions, tables, date range and caveats
   4. the SQL you ran, in a code block

   Link the question folder, but the link doesn't replace the SQL. Never paste a large result; the
   preview and the CSV path are enough.

### When `run_query` returns an error

| Code | What to do |
|---|---|
| `BLOCKED` | Explain why. Never retry it as a write. |
| `LOGIN_TIMEOUT` | Tell the user the login didn't finish. The next call reopens it. |
| `LOGIN_FAILED` | Tell the user the login failed, with the message. The next call retries. |
| `LOGIN_EXPIRED` | Tell the user a login tab will open, then call again. |
| `TIMEOUT` | Suggest a narrower query, or ask the user to allow up to 60 minutes (`timeout_seconds` up to 3600). |
| `SQL_ERROR` | Read the message. If it's about connecting or the network, not the SQL, don't change the query: tell the user, who may need to reconnect to the VPN. Otherwise fix the query and retry up to two times, then tell the user. |
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
- Customer data (names, IDs, results) stays in `runs/`. Never write it into the reference notes.

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
