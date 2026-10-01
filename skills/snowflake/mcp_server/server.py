"""Snowflake MCP server: read-only, and logs in on the first query in each Claude window."""
import argparse
import time
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from connection import LazyConnection, classify_error, default_connect
from eventlog import EventLog
from guard import Blocked, check_sql
from results import format_result, question_dir, save_query, unlearned_folders, write_csv

REPO = Path(__file__).resolve().parents[3]


def build_server(runs_dir: Path, connection: LazyConnection, log: EventLog) -> MCPServer:
    server = MCPServer("snowflake")

    @server.tool(structured_output=False)
    def status() -> str:
        """Say whether this Claude window is logged in to Snowflake. Never logs in; no side effects.

        Call it before the first query. If it says "Not logged in", tell the user an Okta login tab
        is about to open in their browser (about 20 seconds). It also gives the runs folder and how
        many question folders /snowflake learn hasn't read yet.
        """
        state = connection.state()
        if state["state"] == "logged_in":
            line = (f"Logged in as {state['user']} (role {state['role']}, "
                    f"warehouse {state['warehouse']}).")
        elif state["state"] == "logging_in":
            line = f"Login in progress: waiting for the Okta tab ({state['seconds_left']} s left)."
        else:
            line = "Not logged in. The next run_query opens an Okta login tab in the browser."
        return (f"{line}\nRuns folder: {runs_dir}\n"
                f"Unlearned question folders: {len(unlearned_folders(runs_dir))}")

    @server.tool(structured_output=False)
    def run_query(
        sql: Annotated[str, Field(description="Exactly one SELECT, SHOW or DESCRIBE statement.")],
        question: Annotated[str, Field(description=(
            "Short slug naming this question's folder, e.g. npm-devices-by-type. "
            "Reuse it for follow-ups that refine the same question."))],
        step: Annotated[str, Field(description="Short name for this query within the question.")] = "query",
        timeout_seconds: Annotated[int, Field(ge=1, le=3600, description=(
            "Statement time limit. Keep 300 unless the user agreed to a longer run."))] = 300,
        max_rows: Annotated[int, Field(ge=1, description="Most rows written to the CSV.")] = 100000,
    ) -> str:
        """Run one read-only statement on New Relic's Snowflake; save its SQL and CSV under runs/.

        The first call in a window opens an Okta login in the browser. Returns a header line, the
        file paths and a preview of up to 50 rows. Errors start with a code: BLOCKED, LOGIN_TIMEOUT,
        LOGIN_FAILED, LOGIN_EXPIRED, TIMEOUT, SQL_ERROR or INTERNAL_ERROR.
        """
        started = time.monotonic()
        try:
            folder = question_dir(runs_dir, question)
            sql_path, csv_path = save_query(folder, step, sql)
        except OSError as exc:
            raise ToolError(f"INTERNAL_ERROR: could not save the SQL under {runs_dir}: {exc}") from None
        where = f"{folder.parent.name}/{folder.name}/{sql_path.name}"

        def fail(code: str, message: str) -> ToolError:
            log.write("query_failed", code=code, seconds=time.monotonic() - started, file=where)
            return ToolError(f"{code}: {message}\nSQL: {sql_path}")

        try:
            check_sql(sql)
        except Blocked as exc:
            raise fail("BLOCKED", str(exc)) from None
        conn = None
        try:
            conn = connection.get()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, timeout=timeout_seconds)
                columns = [d[0] for d in cursor.description or []]
                result = write_csv(csv_path, columns, cursor, max_rows)
                query_id = cursor.sfqid
            finally:
                cursor.close()
        except Exception as exc:
            code, message = classify_error(exc)
            if code == "LOGIN_EXPIRED" and conn is not None:
                connection.discard(conn)
            csv_path.unlink(missing_ok=True)        # only a successful query leaves a CSV
            raise fail(code, message) from None
        elapsed = time.monotonic() - started
        log.write("query_finished", seconds=elapsed, rows=result.row_count, file=where)
        return format_result(columns=columns, result=result, elapsed=elapsed, query_id=query_id,
                             sql_path=sql_path, csv_path=csv_path, max_rows=max_rows)

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=REPO / "runs",
                        help="where question folders and logs go (default: <repo>/runs)")
    runs_dir = parser.parse_args(argv).runs_dir.resolve()
    log = EventLog(runs_dir / "logs")
    log.write("server_started")
    connection = LazyConnection(default_connect, log=log)
    build_server(runs_dir, connection, log).run()


if __name__ == "__main__":
    main()
