import threading
import time
from datetime import date

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from snowflake.connector.errors import ProgrammingError

import server as server_module
from connection import LazyConnection, LoginExpired
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


@pytest.mark.anyio
async def test_both_tools_are_read_only_so_claude_code_can_run_them_in_parallel(make):
    server, _, _ = make()
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    # Claude Code runs an MCP tool alongside others only when its annotations set readOnlyHint.
    hints = {t.name: t.annotations.read_only_hint if t.annotations else None for t in tools}
    assert hints == {"status": True, "run_query": True}


TODAY = date.today().isoformat()


@pytest.mark.anyio
async def test_run_query_saves_sql_and_csv_and_returns_a_preview(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="SELECT 1 AS n", question="NPM devices", step="count")
    folder = tmp_path / "runs" / TODAY / "npm-devices"
    assert not is_error
    assert text.splitlines()[0].startswith("Rows: 1 | Columns: 1 | Seconds: ")
    assert f"SQL: {folder / '01-count.sql'}" in text
    assert (folder / "01-count.sql").read_text() == "SELECT 1 AS n\n"
    assert (folder / "01-count.csv").read_bytes() == b"N\r\n1\r\n"
    assert connector.calls == 1
    assert connector.connections[0].executed == [("SELECT 1 AS n", 300)]


@pytest.mark.anyio
async def test_blocked_sql_is_saved_but_never_reaches_snowflake(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="DELETE FROM t", question="oops")
    folder = tmp_path / "runs" / TODAY / "oops"
    assert is_error
    assert "BLOCKED: Delete statements are not allowed" in text
    assert (folder / "01-query.sql").read_text() == "DELETE FROM t\n"
    assert not (folder / "01-query.csv").exists()
    assert connector.calls == 0


@pytest.mark.anyio
async def test_follow_ups_share_the_folder_and_count_up(make, tmp_path):
    server, _, _ = make()
    await call(server, "run_query", sql="SELECT 1", question="q", step="first")
    await call(server, "run_query", sql="SELECT 2", question="q", step="second")
    names = sorted(p.name for p in (tmp_path / "runs" / TODAY / "q").iterdir())
    assert names == ["01-first.csv", "01-first.sql", "02-second.csv", "02-second.sql"]


@pytest.mark.anyio
async def test_a_sql_error_returns_its_code_and_leaves_no_csv(make, tmp_path):
    server, _, lazy = make()
    lazy.get().fail_with = ProgrammingError(msg="SQL compilation error: invalid identifier 'FOO'", errno=904)
    is_error, text = await call(server, "run_query", sql="SELECT foo FROM t", question="q")
    assert is_error
    assert "SQL_ERROR: " in text and "invalid identifier 'FOO'" in text
    assert (tmp_path / "runs" / TODAY / "q" / "01-query.sql").exists()
    assert not (tmp_path / "runs" / TODAY / "q" / "01-query.csv").exists()


@pytest.mark.anyio
async def test_an_expired_session_is_dropped_and_the_next_call_logs_in(make):
    server, connector, lazy = make()
    lazy.get().fail_with = LoginExpired("The Snowflake session expired.")
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "LOGIN_EXPIRED: " in text
    is_error, _ = await call(server, "run_query", sql="SELECT 1", question="q")
    assert not is_error
    assert connector.calls == 2


@pytest.mark.anyio
async def test_a_login_timeout_returns_its_code(make):
    server, _, _ = make(FakeConnector(delay=2), login_timeout=0.2)
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "LOGIN_TIMEOUT: " in text


@pytest.mark.anyio
async def test_a_statement_timeout_returns_its_code(make):
    server, _, lazy = make()
    conn = lazy.get()
    conn.fail_with = ProgrammingError(msg="SQL execution was cancelled by the client due to a timeout.",
                                      errno=604)
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q", timeout_seconds=5)
    assert is_error and "TIMEOUT: " in text
    assert conn.executed[-1] == ("SELECT 1", 5)


@pytest.mark.anyio
async def test_unexpected_errors_still_reach_claude(make):
    server, _, lazy = make()
    lazy.get().fail_with = RuntimeError("disk on fire")
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q")
    assert is_error and "INTERNAL_ERROR: RuntimeError: disk on fire" in text


@pytest.mark.anyio
async def test_max_rows_caps_the_csv(make, tmp_path):
    server, _, lazy = make()
    lazy.get().result = (["N"], [(i,) for i in range(10)])
    _, text = await call(server, "run_query", sql="SELECT n FROM t", question="q", max_rows=3)
    assert "Note: the CSV stopped at max_rows=3." in text
    assert len((tmp_path / "runs" / TODAY / "q" / "01-query.csv").read_text().splitlines()) == 4


@pytest.mark.anyio
@pytest.mark.parametrize("args", [{"timeout_seconds": 7200}, {"timeout_seconds": 0}, {"max_rows": 0}])
async def test_out_of_range_arguments_are_refused(make, args):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="SELECT 1", question="q", **args)
    assert is_error
    assert next(iter(args)) in text
    assert connector.calls == 0


@pytest.mark.anyio
async def test_queries_are_logged_without_results(make, tmp_path):
    server, _, lazy = make()
    lazy.get().result = (["SECRET_COLUMN"], [("secret value",)])
    await call(server, "run_query", sql="SELECT 1", question="q")
    log_text = next((tmp_path / "runs" / "logs").glob("*.log")).read_text()
    assert " query_finished seconds=" in log_text and " rows=1 " in log_text
    assert "secret value" not in log_text and "SECRET_COLUMN" not in log_text


@pytest.mark.anyio
async def test_a_guard_crash_still_returns_a_code(make, tmp_path):
    server, connector, _ = make()
    is_error, text = await call(server, "run_query", sql="DESC.RIBE TABLE db.sch.t", question="q")
    assert is_error
    assert "INTERNAL_ERROR: " in text
    assert "SQL: " in text
    assert (tmp_path / "runs" / TODAY / "q" / "01-query.sql").exists()
    assert connector.calls == 0
    log_text = next((tmp_path / "runs" / "logs").glob("*.log")).read_text()
    assert " query_failed code=INTERNAL_ERROR" in log_text


@pytest.mark.anyio
async def test_a_failure_mid_stream_deletes_the_partial_csv(make, tmp_path):
    server, _, lazy = make()
    def rows():
        yield (1,)
        yield (2,)
        raise ProgrammingError(msg="Connection lost", errno=250)
    lazy.get().result = (["N"], rows())
    is_error, text = await call(server, "run_query", sql="SELECT n FROM t", question="q")
    assert is_error
    assert "SQL_ERROR: " in text
    assert (tmp_path / "runs" / TODAY / "q" / "01-query.sql").exists()
    assert not (tmp_path / "runs" / TODAY / "q" / "01-query.csv").exists()
