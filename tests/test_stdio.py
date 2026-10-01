import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

SCRIPT = Path(__file__).with_name("fake_server_main.py")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_the_stdio_server_survives_login_noise_and_logs_in_once(tmp_path):
    runs = tmp_path / "runs"
    params = StdioServerParameters(command=sys.executable, args=[str(SCRIPT), "--runs-dir", str(runs)])
    async with Client(params) as client:
        assert sorted(t.name for t in (await client.list_tools()).tools) == ["run_query", "status"]
        first = await client.call_tool("status", {})
        assert first.content[0].text.startswith("Not logged in")
        for i in range(3):
            result = await client.call_tool("run_query", {"sql": f"SELECT {i}", "question": "stdio-check"})
            assert not result.is_error, result.content[0].text
        last = await client.call_tool("status", {})
        assert last.content[0].text.startswith("Logged in as JKARNIK")
    log_text = next((runs / "logs").glob("*.log")).read_text()
    assert log_text.count(" server_started") == 1
    assert log_text.count(" login_started") == 1
    assert log_text.count(" query_finished") == 3
