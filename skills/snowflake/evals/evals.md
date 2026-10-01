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
