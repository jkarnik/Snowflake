"""Run one end-to-end eval (spec §10.4) in a fresh headless Claude window.

Usage: .venv/bin/python tests/run_eval.py <E1..E10> <skill|baseline>

Fills {{placeholders}} from runs/evals/values.toml and runs from an empty scratch folder outside
the repo. Saves the transcript, answer and facts under runs/evals/<YYYY-MM-DD>/<id>-<mode>/, and
prints the facts a grader needs. It never grades the answer.
"""
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "skills" / "snowflake" / "evals" / "evals.md"
VALUES = REPO / "runs" / "evals" / "values.toml"
CLAUDE = "/opt/homebrew/bin/claude"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def load_prompt(eval_id: str, evals_text: str, values: dict) -> str:
    """The prompt for eval_id from the evals.md table, with placeholders filled."""
    for line in evals_text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == eval_id:
            missing = sorted(set(PLACEHOLDER.findall(cells[1])) - set(values))
            if missing:
                raise KeyError(", ".join(missing))
            return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), cells[1])
    raise KeyError(f"no eval {eval_id}")


def facts(events: list[dict]) -> dict:
    """What happened in a stream-json transcript: skill use, tool calls, denials, final answer."""
    uses = [part for event in events if event.get("type") == "assistant"
            for part in event.get("message", {}).get("content", []) if part.get("type") == "tool_use"]
    result = next((event for event in events if event.get("type") == "result"), None)
    return {
        "skill_triggered": any(u["name"] == "Skill" and u.get("input", {}).get("skill") == "snowflake"
                               for u in uses),
        "status_calls": sum(u["name"] == "mcp__snowflake__status" for u in uses),
        "run_query_calls": sum(u["name"] == "mcp__snowflake__run_query" for u in uses),
        "permission_denials": len(result.get("permission_denials", [])) if result else 0,
        "answer": result.get("result", "") if result else "",
        "result_seen": result is not None,
    }


def repo_changes_outside_runs() -> set[str]:
    status = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                            capture_output=True, text=True, check=True).stdout
    return {line for line in status.splitlines() if not line[3:].startswith("runs/")}


def main(argv: list[str] | None = None) -> int:
    eval_id, mode = (argv if argv is not None else sys.argv[1:])[:2]
    if mode not in ("skill", "baseline"):
        raise SystemExit("mode must be skill or baseline")
    values = tomllib.loads(VALUES.read_text(encoding="utf-8"))
    prompt = load_prompt(eval_id, EVALS.read_text(encoding="utf-8"), values)
    out = REPO / "runs" / "evals" / date.today().isoformat() / f"{eval_id}-{mode}"
    out.mkdir(parents=True, exist_ok=True)
    before = repo_changes_outside_runs()
    cmd = [CLAUDE, "-p", prompt, "--model", "sonnet", "--output-format", "stream-json",
           "--verbose", "--no-session-persistence"]
    if mode == "baseline":  # P11: the server stays, skills go; its tools are pre-allowed
        cmd += ["--disable-slash-commands",
                "--allowedTools", "mcp__snowflake__run_query", "mcp__snowflake__status"]
    with tempfile.TemporaryDirectory() as scratch:
        try:
            proc = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=1800)
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = -1
            stdout = exc.stdout.decode("utf-8", "replace") if exc.stdout else ""
            stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
        stray = sorted(p.name for p in Path(scratch).iterdir())
    (out / "transcript.jsonl").write_text(stdout, encoding="utf-8")
    (out / "stderr.txt").write_text(stderr, encoding="utf-8")
    found = facts([json.loads(line) for line in stdout.splitlines() if line.startswith("{")])
    (out / "answer.md").write_text(found.pop("answer"), encoding="utf-8")
    found["files_in_scratch_folder"] = stray
    found["repo_changes_outside_runs"] = sorted(repo_changes_outside_runs() - before)
    found["exit_code"] = exit_code
    (out / "facts.json").write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"{eval_id} {mode}: {json.dumps(found)}\nSaved in {out}")
    if exit_code != 0 or not found["result_seen"]:
        print(f"WARNING: window failed or produced no final result (exit_code={exit_code}, result_seen={found['result_seen']}) and must not be graded")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
