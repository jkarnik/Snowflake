import sys
import threading
import time

import pytest
from snowflake.connector.errors import OperationalError, ProgrammingError

from connection import (LazyConnection, LoginExpired, LoginFailed, LoginTimeout, classify_error,
                        default_connect)
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


def test_overlapping_logins_restore_stdout():
    original = sys.stdout
    connector = FakeConnector(delay=0.4)        # login 1 finishes at about 0.4 s
    lazy = LazyConnection(connector, login_timeout=0.1)
    before = set(threading.enumerate())
    with pytest.raises(LoginTimeout):
        lazy.get()                              # login 1 times out at 0.1 s but keeps running
    connector.delay = 0.5                       # login 2 starts at 0.1 s and finishes at 0.6 s, after login 1
    with pytest.raises(LoginTimeout):
        lazy.get()                              # times out at 0.2 s, while both logins are still running
    for thread in set(threading.enumerate()) - before:
        thread.join()                           # wait until both login threads have left their redirects
    assert sys.stdout is original


def test_an_expired_session_never_opens_a_browser_inside_a_query():
    conn = LazyConnection(FakeConnector()).get()
    with pytest.raises(LoginExpired):
        conn._reauthenticate()          # what the connector calls when the session has expired


def test_discard_forgets_the_connection_and_the_next_get_logs_in_again():
    connector = FakeConnector()
    lazy = LazyConnection(connector)
    conn = lazy.get()
    lazy.discard(conn)
    assert lazy.state() == {"state": "logged_out"}
    assert lazy.get() is not conn
    assert connector.calls == 2


def test_default_connect_uses_the_newrelic_settings(monkeypatch):
    import snowflake.connector

    seen = {}
    monkeypatch.setattr(snowflake.connector, "connect", lambda **kw: seen.update(kw) or "conn")
    assert default_connect() == "conn"
    assert seen == {"connection_name": "newrelic", "client_session_keep_alive": True,
                    "session_parameters": {"QUERY_TAG": "snowflake-skill"}}


@pytest.mark.parametrize("exc,code", [
    (LoginTimeout("slow"), "LOGIN_TIMEOUT"),
    (LoginFailed("no"), "LOGIN_FAILED"),
    (LoginExpired("gone"), "LOGIN_EXPIRED"),
    (OperationalError(msg="Connection is closed", errno=250002), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="Session no longer exists.", errno=390112), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="Authentication token has expired.", errno=390114), "LOGIN_EXPIRED"),
    (ProgrammingError(msg="SQL execution was cancelled by the client due to a timeout.", errno=604), "TIMEOUT"),
    (ProgrammingError(msg="Statement reached its statement or warehouse timeout.", errno=630), "TIMEOUT"),
    (ProgrammingError(msg="SQL compilation error: Object 'X' does not exist.", errno=2003), "SQL_ERROR"),
    (OSError(28, "No space left on device"), "INTERNAL_ERROR"),
    (RuntimeError("bug"), "INTERNAL_ERROR"),
])
def test_classify_error_maps_failures_to_codes(exc, code):
    assert classify_error(exc)[0] == code


def test_a_sql_error_keeps_snowflakes_message():
    code, message = classify_error(ProgrammingError(msg="SQL compilation error: invalid identifier 'FOO'", errno=904))
    assert code == "SQL_ERROR"
    assert "invalid identifier 'FOO'" in message
