"""Check the install (spec §9 step 5) without a Snowflake login.

Opens one headless Claude window from a scratch folder, sends a prompt that needs no tools, and
checks that the skill is listed, the snowflake server is connected with both tools, and the
server started without logging in. If the window times out or reports no init event, nothing was
checked: it prints one "check window failed" line and exits 1 instead of per-check results.
"""
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAUDE = "/opt/homebrew/bin/claude"
TIMEOUT_SECONDS = 300


def checks(init: dict, new_log_lines: list[str]) -> list[tuple[str, bool]]:
    return [
        ("skill 'snowflake' is listed", "snowflake" in init.get("slash_commands", [])),
        ("server 'snowflake' is connected",
         any(server.get("name") == "snowflake" and server.get("status") == "connected"
             for server in init.get("mcp_servers", []))),
        ("both tools are available",
         {"mcp__snowflake__run_query", "mcp__snowflake__status"} <= set(init.get("tools", []))),
        ("the server started", any(" server_started" in line for line in new_log_lines)),
        ("no login happened", not any(" login_started" in line for line in new_log_lines)),
    ]


def main() -> int:
    log = REPO / "runs" / "logs" / f"{date.today().isoformat()}.log"
    before = len(log.read_text().splitlines()) if log.exists() else 0
    try:
        with tempfile.TemporaryDirectory() as scratch:
            proc = subprocess.run([CLAUDE, "-p", "Reply with the single word OK.", "--model", "haiku",
                                   "--output-format", "stream-json", "--verbose", "--no-session-persistence"],
                                  cwd=scratch, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"The check window failed: it timed out after {TIMEOUT_SECONDS} s, so the install was not checked.")
        return 1
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    if init is None:
        print(f"The check window failed: it produced no init event (claude exited with code {proc.returncode}), "
              "so the install was not checked.")
        return 1
    new_lines = log.read_text().splitlines()[before:] if log.exists() else []
    results = checks(init, new_lines)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
