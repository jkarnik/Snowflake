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
        "WHERE METRIC = 'NetworkMonitoring' AND USAGE_DATE = DATEADD(day, -2, CURRENT_DATE()) LIMIT 1"),
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
