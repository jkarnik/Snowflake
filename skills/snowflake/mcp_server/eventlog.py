"""Append-only event log: runs/logs/<YYYY-MM-DD>.log, one line per event. Never query results."""
import os
import threading
from datetime import datetime
from pathlib import Path


class EventLog:
    def __init__(self, logs_dir: Path) -> None:
        self._dir = Path(logs_dir)
        self._lock = threading.Lock()

    def write(self, event: str, **fields: object) -> None:
        """Append `<local time> pid=<n> <event> key=value …`. Logging must never break a query."""
        try:
            now = datetime.now()
            parts = [now.strftime("%Y-%m-%dT%H:%M:%S"), f"pid={os.getpid()}", event]
            for key, value in fields.items():
                text = f"{value:.2f}" if isinstance(value, float) else str(value)
                parts.append(f"{key}={text.replace(chr(10), ' ')}")
            with self._lock:
                self._dir.mkdir(parents=True, exist_ok=True)
                with open(self._dir / f"{now:%Y-%m-%d}.log", "a", encoding="utf-8", errors="replace") as f:
                    f.write(" ".join(parts) + "\n")
        except Exception:
            pass
