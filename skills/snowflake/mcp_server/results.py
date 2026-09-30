"""Result files: one folder per question under runs/, numbered SQL and CSV files, previews."""
import csv
import fcntl
import os
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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


@dataclass
class CsvResult:
    row_count: int
    truncated: bool
    preview: list[tuple]


def _cell(value):
    """NULL becomes empty and bytes become hex; csv writes everything else with str()."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def write_csv(csv_path: Path, columns: list[str], rows: Iterable[Sequence], max_rows: int,
              preview_rows: int = 50) -> CsvResult:
    """Stream rows into a UTF-8 CSV with a header row, stopping after max_rows."""
    count, truncated, preview = 0, False, []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if not columns:  # the statement returned no result columns
            return CsvResult(0, False, [])
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            if count == max_rows:
                truncated = True
                break
            writer.writerow([_cell(v) for v in row])
            if count < preview_rows:
                preview.append(tuple(row))
            count += 1
    return CsvResult(count, truncated, preview)


def _preview_cell(value, max_cell: int) -> str:
    if value is None:
        return "NULL"
    text = value.hex() if isinstance(value, (bytes, bytearray)) else str(value)
    text = text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
    return text if len(text) <= max_cell else text[: max_cell - 1] + "…"


def format_preview(columns: list[str], rows: list[tuple], max_cell: int = 200) -> str:
    """Tab-separated header and rows. NULL shows as NULL; tabs and line breaks are escaped."""
    lines = ["\t".join(_preview_cell(c, max_cell) for c in columns)]
    lines += ["\t".join(_preview_cell(v, max_cell) for v in row) for row in rows]
    return "\n".join(lines)


def format_result(*, columns: list[str], result: CsvResult, elapsed: float, query_id: str | None,
                  sql_path: Path, csv_path: Path, max_rows: int) -> str:
    """The text that run_query returns to Claude."""
    lines = [
        f"Rows: {result.row_count} | Columns: {len(columns)} | Seconds: {elapsed:.2f}"
        f" | Query ID: {query_id or 'unknown'}",
        f"SQL: {sql_path}",
        f"CSV: {csv_path}",
    ]
    if result.preview:
        lines.append(f"Preview ({len(result.preview)} of {result.row_count} rows):")
        lines.append(format_preview(columns, result.preview))
    else:
        lines.append("Preview: no rows.")
    if result.truncated:
        lines.append(f"Note: the CSV stopped at max_rows={max_rows}. More rows exist; "
                     "narrow the query or raise max_rows.")
    return "\n".join(lines)
