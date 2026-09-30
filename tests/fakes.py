"""A fake Snowflake connector for tests: no network, no browser."""
import time


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.sfqid = None
        self._rows = iter(())

    def execute(self, sql, timeout=None):
        self.conn.executed.append((sql, timeout))
        if self.conn.fail_with is not None:
            raise self.conn.fail_with
        columns, rows = self.conn.result
        self.description = [(name,) for name in columns] or None
        self.sfqid = f"fake-query-{len(self.conn.executed)}"
        self._rows = iter(rows)
        return self

    def __iter__(self):
        return self._rows

    def close(self):
        pass


class FakeConnection:
    user, role, warehouse = "JKARNIK", "FR_PRODUCT_ANALYST", "TEAM_PRODUCT_ANALYST_XSMALL"

    def __init__(self):
        self.executed = []                  # (sql, timeout) per execute()
        self.result = (["N"], [(1,)])       # (column names, rows) the next query returns
        self.fail_with = None               # an exception the next query raises
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class FakeConnector:
    """Stands in for snowflake.connector.connect: counts logins, and can be slow, fail or print."""

    def __init__(self, delay=0.0, error=None, prints=None):
        self.delay, self.error, self.prints = delay, error, prints
        self.calls = 0
        self.connections = []

    def __call__(self):
        self.calls += 1
        delay, error = self.delay, self.error
        if self.prints:
            print(self.prints)              # the real connector prints its login URL
        time.sleep(delay)
        if error is not None:
            raise error
        conn = FakeConnection()
        self.connections.append(conn)
        return conn
