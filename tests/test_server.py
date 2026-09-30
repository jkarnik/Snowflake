import threading
import time

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

import server as server_module
from connection import LazyConnection
from eventlog import EventLog
from fakes import FakeConnector
from server import build_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def make(tmp_path):
    def _make(connector=None, login_timeout=120.0):
        connector = connector or FakeConnector()
        log = EventLog(tmp_path / "runs" / "logs")
        lazy = LazyConnection(connector, login_timeout=login_timeout, log=log)
        return build_server(tmp_path / "runs", lazy, log), connector, lazy
    return _make


async def call(server, tool, **args):
    async with Client(server) as client:
        result = await client.call_tool(tool, args)
    return result.is_error, result.content[0].text


@pytest.mark.anyio
async def test_status_never_logs_in(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "status")
    assert not is_error
    assert text.splitlines() == [
        "Not logged in. The next run_query opens an Okta login tab in the browser.",
        f"Runs folder: {tmp_path / 'runs'}",
        "Unlearned question folders: 0",
    ]
    assert connector.calls == 0


@pytest.mark.anyio
async def test_status_after_login_names_user_role_and_warehouse(make):
    server, _, lazy = make()
    lazy.get()
    _, text = await call(server, "status")
    assert text.splitlines()[0] == ("Logged in as JKARNIK (role FR_PRODUCT_ANALYST, "
                                    "warehouse TEAM_PRODUCT_ANALYST_XSMALL).")


@pytest.mark.anyio
async def test_status_during_a_pending_login_answers_at_once(make):  # Review Focus 3
    server, _, lazy = make(FakeConnector(delay=1.0))
    threading.Thread(target=lazy.get, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    _, text = await call(server, "status")
    assert text.startswith("Login in progress")
    assert time.monotonic() - started < 0.5


@pytest.mark.anyio
async def test_status_counts_unlearned_question_folders(make, tmp_path):
    for rel in ["2026-10-01/a", "2026-10-01/b"]:
        (tmp_path / "runs" / rel).mkdir(parents=True)
    (tmp_path / "runs" / "learned.txt").write_text("2026-10-01/a\n")
    server, _, _ = make()
    _, text = await call(server, "status")
    assert text.splitlines()[-1] == "Unlearned question folders: 1"


def test_main_logs_server_start_without_logging_in(tmp_path, monkeypatch):
    monkeypatch.setattr(MCPServer, "run", lambda self, *args, **kwargs: None)
    server_module.main(["--runs-dir", str(tmp_path / "runs")])
    log_text = next((tmp_path / "runs" / "logs").glob("*.log")).read_text()
    assert " server_started" in log_text
    assert "login" not in log_text


def test_default_runs_dir_is_at_the_repo_root():
    assert (server_module.REPO / "skills" / "snowflake" / "mcp_server" / "server.py").is_file()
