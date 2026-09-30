import threading
import time

import pytest

from connection import LazyConnection, LoginFailed, LoginTimeout
from eventlog import EventLog
from fakes import FakeConnector


def test_nothing_connects_before_the_first_get():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    assert lazy.state() == {"state": "logged_out"}
    assert connector.calls == 0


def test_first_get_logs_in_once_and_reuses_the_connection():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    first = lazy.get()
    assert lazy.get() is first
    assert connector.calls == 1
    assert lazy.state() == {"state": "logged_in", "user": "JKARNIK", "role": "FR_PRODUCT_ANALYST",
                            "warehouse": "TEAM_PRODUCT_ANALYST_XSMALL"}


def test_concurrent_first_calls_log_in_once():
    connector = FakeConnector(delay=0.2)
    lazy = LazyConnection(connector)
    barrier = threading.Barrier(5)
    got = []

    def work():
        barrier.wait()
        got.append(lazy.get())

    threads = [threading.Thread(target=work) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert connector.calls == 1
    assert len({id(conn) for conn in got}) == 1


def test_login_output_never_reaches_stdout(capsys):
    LazyConnection(FakeConnector(prints="Going to open: https://okta.example/login")).get()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Going to open" in captured.err


def test_state_answers_at_once_during_a_pending_login():  # Review Focus 3
    lazy = LazyConnection(FakeConnector(delay=0.5))
    threading.Thread(target=lazy.get, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    assert lazy.state()["state"] == "logging_in"
    assert time.monotonic() - started < 0.05


def test_login_timeout_then_the_next_call_opens_a_new_login():
    connector = FakeConnector(delay=5)          # the user never finishes the first tab
    lazy = LazyConnection(connector, login_timeout=0.2)
    with pytest.raises(LoginTimeout):
        lazy.get()
    connector.delay = 0                         # the user finishes the second tab
    assert lazy.get() is connector.connections[-1]
    assert connector.calls == 2


def test_a_login_finished_after_the_timeout_is_kept():
    connector = FakeConnector(delay=0.4)
    lazy = LazyConnection(connector, login_timeout=0.1)
    with pytest.raises(LoginTimeout):
        lazy.get()
    time.sleep(0.5)
    assert lazy.state()["state"] == "logged_in"
    lazy.get()
    assert connector.calls == 1


def test_a_login_error_raises_login_failed_and_the_next_call_retries():
    connector = FakeConnector(error=RuntimeError("IdP said no"))
    lazy = LazyConnection(connector)
    with pytest.raises(LoginFailed, match="IdP said no"):
        lazy.get()
    connector.error = None
    lazy.get()
    assert connector.calls == 2


def test_login_events_are_logged(tmp_path):
    LazyConnection(FakeConnector(), log=EventLog(tmp_path)).get()
    text = next(tmp_path.glob("*.log")).read_text()
    assert " login_started" in text
    assert " logged_in seconds=" in text
