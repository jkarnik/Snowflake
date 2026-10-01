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
                print(f"FAIL {where} {code}: {" ".join(message.split())}")
                if code.startswith("LOGIN_"):
                    print("Stopping: no Snowflake session, so every later block would fail too.")
                    return 1
    print(f"{failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
