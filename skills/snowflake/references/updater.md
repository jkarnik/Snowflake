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
