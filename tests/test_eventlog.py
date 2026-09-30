import os
import re
from datetime import date

from eventlog import EventLog


def test_write_appends_one_line_per_event_with_time_and_pid(tmp_path):
    log = EventLog(tmp_path / "logs")
    log.write("server_started")
    log.write("logged_in", seconds=21.391, note="two\nlines")
    lines = (tmp_path / "logs" / f"{date.today().isoformat()}.log").read_text().splitlines()
    assert len(lines) == 2
    assert re.fullmatch(rf"\d{{4}}-\d\d-\d\dT\d\d:\d\d:\d\d pid={os.getpid()} server_started", lines[0])
    assert lines[1].endswith(f"pid={os.getpid()} logged_in seconds=21.39 note=two lines")


def test_write_never_raises(tmp_path):
    blocker = tmp_path / "logs"
    blocker.write_text("a file where the folder should be")
    EventLog(blocker).write("server_started")

    # Test with object whose __str__ raises
    class RaisingStr:
        def __str__(self):
            raise RuntimeError("oops")

    log = EventLog(tmp_path / "ok")
    log.write("event_with_raising_str", obj=RaisingStr())

    # Test with lone surrogate (unencodable)
    log.write("event_with_surrogate", value="\ud800")

    # Verify the surrogate event was written
    lines = (tmp_path / "ok" / f"{date.today().isoformat()}.log").read_text().splitlines()
    assert any("event_with_surrogate" in line for line in lines)
