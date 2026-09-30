"""Snowflake MCP server: read-only, and logs in on the first query in each Claude window."""
import argparse
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from connection import LazyConnection, default_connect
from eventlog import EventLog
from results import unlearned_folders

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
