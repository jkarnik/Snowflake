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
