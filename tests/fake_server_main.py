"""Run the real MCP server over stdio with a noisy fake connector. Used only by test_stdio.py."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "snowflake" / "mcp_server"))

import server  # noqa: E402
from fakes import FakeConnector  # noqa: E402


class NoisyConnector(FakeConnector):
    def __call__(self):
        os.write(1, b"raw bytes on fd 1 during login\n")    # as a child process or C library might
        return super().__call__()


if __name__ == "__main__":
    server.default_connect = NoisyConnector(prints="Going to open: https://okta.example/login")
    server.main(sys.argv[1:])
