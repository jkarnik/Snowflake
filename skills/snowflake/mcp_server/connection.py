"""One Snowflake connection per Claude window: log in on first use, never block past the timeout."""
import contextlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from eventlog import EventLog


class LoginTimeout(Exception):
    """The browser login didn't finish in time."""


class LoginFailed(Exception):
    """The login ended with an error."""


class LoginExpired(Exception):
    """The session lapsed; the next call opens a fresh login."""


class _Attempt:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.done = threading.Event()
        self.error: BaseException | None = None

    def remaining(self, timeout: float) -> float:
        return max(0.0, self.started + timeout - time.monotonic())


class LazyConnection:
    def __init__(self, connect: Callable[[], Any], login_timeout: float = 120.0,
                 log: EventLog | None = None) -> None:
        self._connect = connect
        self._timeout = login_timeout
        self._log = log
        self._lock = threading.Lock()       # never held while a login waits
        self._conn: Any = None
        self._attempt: _Attempt | None = None

    def _event(self, event: str, **fields: object) -> None:
        if self._log is not None:
            self._log.write(event, **fields)

    def get(self) -> Any:
        """Return the live connection, logging in first if needed (at most one login at a time)."""
        with self._lock:
            if self._conn is not None:
                return self._conn
            attempt = self._attempt
            if attempt is None or attempt.done.is_set() or attempt.remaining(self._timeout) == 0:
                attempt = self._attempt = _Attempt()
                self._event("login_started")
                threading.Thread(target=self._login, args=(attempt,), daemon=True).start()
        if not attempt.done.wait(attempt.remaining(self._timeout)):
            self._event("login_timeout", seconds=float(self._timeout))
            raise LoginTimeout(f"The Okta login didn't finish within {self._timeout:.0f} seconds.")
        with self._lock:
            if self._conn is not None:
                return self._conn
        raise LoginFailed(f"The Okta login failed: {attempt.error}")

    def _login(self, attempt: _Attempt) -> None:
        # The connector's browser wait has no timeout, so it runs here while get() waits with one.
        started = time.monotonic()
        try:
            with contextlib.redirect_stdout(sys.stderr):    # stdout carries the MCP protocol
                conn = self._connect()
        except Exception as exc:
            attempt.error = exc
            self._event("login_failed", seconds=time.monotonic() - started, error=type(exc).__name__)
            attempt.done.set()
            return
        with self._lock:
            keep = self._conn is None
            if keep:
                self._conn = conn
            current = self._attempt
        if keep:
            self._event("logged_in", seconds=time.monotonic() - started)
        else:
            with contextlib.suppress(Exception):
                conn.close()                # a newer login already won
        attempt.done.set()
        if current is not None:
            current.done.set()              # wake callers waiting on a newer attempt

    def state(self) -> dict:
        """Never blocks: logged_out, logging_in (with seconds_left) or logged_in (with names)."""
        with self._lock:
            conn, attempt = self._conn, self._attempt
        if conn is not None:
            return {"state": "logged_in", "user": conn.user, "role": conn.role, "warehouse": conn.warehouse}
        if attempt is not None and not attempt.done.is_set() and attempt.remaining(self._timeout) > 0:
            return {"state": "logging_in", "seconds_left": round(attempt.remaining(self._timeout))}
        return {"state": "logged_out"}
