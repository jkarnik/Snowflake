"""Result files: one folder per question under runs/, numbered SQL and CSV files, previews."""
import fcntl
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

MAX_SLUG = 60
_NUMBERED = re.compile(r"^(\d+)-")


def slugify(text: str, fallback: str) -> str:
    """Lowercase ASCII slug: spaces and underscores become hyphens; only a-z, 0-9 and single hyphens stay."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[\s_]+", "-", ascii_text.lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:MAX_SLUG].rstrip("-") or fallback


def question_dir(runs_dir: Path, question: str, today: date | None = None) -> Path:
    """Create and return runs/<YYYY-MM-DD>/<question-slug>/, using the local date."""
    day = (today or date.today()).isoformat()
    folder = Path(runs_dir) / day / slugify(question, "question")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_query(folder: Path, step: str, sql: str) -> tuple[Path, Path]:
    """Save the SQL as NN-<step>.sql with the next free number; return (sql_path, csv_path).

    A lock on the folder keeps numbers unique when queries run in parallel, even across windows.
    """
    name = slugify(step, "query")
    lock_fd = os.open(folder, os.O_RDONLY)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        used = [int(m.group(1)) for p in folder.iterdir() if (m := _NUMBERED.match(p.name))]
        sql_path = folder / f"{max(used, default=0) + 1:02d}-{name}.sql"
        sql_path.write_text(sql.rstrip() + "\n", encoding="utf-8")
    finally:
        os.close(lock_fd)  # closing the descriptor releases the lock
    return sql_path, sql_path.with_suffix(".csv")
