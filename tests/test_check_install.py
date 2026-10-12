"""Tests for the install check. No Claude window opens: the window is replaced with a stub."""
import json
import subprocess
from datetime import date

import pytest

import check_install

# What Claude Code 2.1.285 reports: every server entry also carries "source", and other servers sit beside ours.
INIT = {
    "type": "system",
    "subtype": "init",
    "claude_code_version": "2.1.285",
    "slash_commands": ["compact", "snowflake"],
    "mcp_servers": [
        {"name": "snowflake", "status": "connected", "source": "user"},
        {"name": "jira", "status": "connected", "source": "user"},
    ],
    "tools": ["Read", "mcp__snowflake__run_query", "mcp__snowflake__status"],
}
SERVER_CHECK = "server 'snowflake' is connected"
LOG = ["2026-10-12T09:00:00 pid=42 server_started"]


def stub_window(monkeypatch, tmp_path, *, stdout="", returncode=0, timed_out=False, started=False):
    """Replace `claude -p ...` so no window opens. started=True makes the "server" log server_started."""
    monkeypatch.setattr(check_install, "REPO", tmp_path)
    log = tmp_path / "runs" / "logs" / f"{date.today().isoformat()}.log"
    log.parent.mkdir(parents=True)
    log.write_text("2026-10-11T09:00:00 pid=7 login_started\n")  # an earlier window's login must not count

    def run(cmd, **kwargs):
        if timed_out:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        if started:
            with log.open("a") as f:
                f.write(LOG[0] + "\n")
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(check_install.subprocess, "run", run)


def test_every_check_passes_when_the_snowflake_entry_carries_extra_fields():
    results = check_install.checks(INIT, LOG)
    assert len(results) == 5
    assert all(ok for _, ok in results), results


@pytest.mark.parametrize("servers", [
    [{"name": "snowflake", "status": "failed", "source": "user"},
     {"name": "jira", "status": "connected", "source": "user"}],
    [{"name": "jira", "status": "connected", "source": "user"}],
    [],
])
def test_the_server_check_still_fails_unless_snowflake_itself_is_connected(servers):
    results = check_install.checks({**INIT, "mcp_servers": servers}, LOG)
    assert [name for name, ok in results if not ok] == [SERVER_CHECK]


def test_a_cli_2_1_285_window_prints_five_pass_lines(monkeypatch, tmp_path, capsys):
    stub_window(monkeypatch, tmp_path, stdout=json.dumps(INIT) + "\n", started=True)
    assert check_install.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5 and all(line.startswith("PASS ") for line in lines), lines


def test_a_window_that_times_out_prints_one_line_and_exits_nonzero(monkeypatch, tmp_path, capsys):
    stub_window(monkeypatch, tmp_path, timed_out=True)
    assert check_install.main() != 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1, lines
    assert "check window failed" in lines[0] and "timed out" in lines[0]
    assert not lines[0].startswith(("PASS", "FAIL"))


@pytest.mark.parametrize("stdout", [
    "",  # claude died before it printed anything
    json.dumps({"type": "result", "result": "OK"}) + "\n",  # it printed events, but never an init
])
def test_a_window_with_no_init_event_prints_one_line_and_exits_nonzero(monkeypatch, tmp_path, capsys, stdout):
    stub_window(monkeypatch, tmp_path, stdout=stdout, returncode=1)
    assert check_install.main() != 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1, lines
    assert "check window failed" in lines[0] and "no init event" in lines[0]
    assert not lines[0].startswith(("PASS", "FAIL"))
