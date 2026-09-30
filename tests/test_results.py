import csv
import threading
from datetime import date, datetime
from decimal import Decimal

from results import CsvResult, format_preview, format_result, question_dir, save_query, slugify, write_csv


def test_slugify_keeps_letters_digits_and_single_hyphens():
    assert slugify("NPM devices by type", "question") == "npm-devices-by-type"
    assert slugify("  Devices__by--Type!! ", "question") == "devices-by-type"


def test_slugify_makes_odd_names_safe():  # Review Focus 4
    assert slugify("../../etc", "question") == "etc"
    assert slugify("Ünïcode Şirket", "question") == "unicode-sirket"
    assert slugify("🚀", "question") == "question"
    assert slugify("", "query") == "query"
    assert slugify("a" * 300, "question") == "a" * 60


def test_question_dir_uses_local_date_and_slug(tmp_path):
    folder = question_dir(tmp_path, "NPM devices by type", today=date(2026, 10, 1))
    assert folder == tmp_path / "2026-10-01" / "npm-devices-by-type"
    assert folder.is_dir()


def test_question_dir_stays_inside_runs(tmp_path):  # Review Focus 4
    folder = question_dir(tmp_path, "../../etc", today=date(2026, 10, 1))
    assert folder.resolve().is_relative_to(tmp_path.resolve())


def test_save_query_numbers_files_and_saves_sql(tmp_path):
    first = save_query(tmp_path, "devices", "SELECT 1")
    second = save_query(tmp_path, "By Type", "SELECT 2;\n\n")
    assert [p.name for p in first] == ["01-devices.sql", "01-devices.csv"]
    assert [p.name for p in second] == ["02-by-type.sql", "02-by-type.csv"]
    assert first[0].read_text() == "SELECT 1\n"
    assert second[0].read_text() == "SELECT 2;\n"
    assert not first[1].exists()  # only a successful query writes its CSV


def test_save_query_continues_past_99(tmp_path):
    (tmp_path / "99-old.sql").write_text("SELECT 1\n")
    assert save_query(tmp_path, "next", "SELECT 2")[0].name == "100-next.sql"


def test_parallel_saves_get_distinct_numbers(tmp_path):  # Review Focus 1
    barrier = threading.Barrier(20)
    names = []

    def work(i):
        barrier.wait()
        names.append(save_query(tmp_path, f"step{i}", f"SELECT {i}")[0].name)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(int(n.split("-")[0]) for n in names) == list(range(1, 21))


TRICKY = [
    ("a,b", 'say "hi"', "tab\there", "line\nbreak", None, "Demirören Teknoloji Şirketi"),
    (Decimal("1.50"), datetime(2026, 9, 30, 14, 5), True, b"\x00\xff", 42, ""),
]


def read_back(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_csv_round_trip_keeps_tricky_values(tmp_path):
    path = tmp_path / "01-q.csv"
    result = write_csv(path, ["c1", "c2", "c3", "c4", "c5", "c6"], iter(TRICKY), max_rows=100)
    rows = read_back(path)
    assert rows[0] == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert rows[1] == ["a,b", 'say "hi"', "tab\there", "line\nbreak", "", "Demirören Teknoloji Şirketi"]
    assert rows[2] == ["1.50", "2026-09-30 14:05:00", "True", "00ff", "42", ""]
    assert (result.row_count, result.truncated) == (2, False)
    assert result.preview == TRICKY


def test_large_result_writes_every_row_and_keeps_a_50_row_preview(tmp_path):
    path = tmp_path / "01-big.csv"
    result = write_csv(path, ["n"], ((i,) for i in range(5000)), max_rows=100000)
    assert len(read_back(path)) == 5001
    assert (result.row_count, result.truncated, len(result.preview)) == (5000, False, 50)


def test_max_rows_truncates_the_csv(tmp_path):
    path = tmp_path / "01-big.csv"
    result = write_csv(path, ["n"], ((i,) for i in range(150)), max_rows=100)
    assert len(read_back(path)) == 101
    assert (result.row_count, result.truncated) == (100, True)


def test_exactly_max_rows_is_not_truncated(tmp_path):
    result = write_csv(tmp_path / "01-x.csv", ["n"], ((i,) for i in range(100)), max_rows=100)
    assert (result.row_count, result.truncated) == (100, False)


def test_zero_rows_writes_a_header_only_csv(tmp_path):  # Review Focus 5
    path = tmp_path / "01-none.csv"
    result = write_csv(path, ["a", "b"], iter([]), max_rows=10)
    assert read_back(path) == [["a", "b"]]
    assert (result.row_count, result.truncated, result.preview) == (0, False, [])


def test_no_result_columns_writes_an_empty_csv(tmp_path):  # Review Focus 5
    path = tmp_path / "01-nothing.csv"
    result = write_csv(path, [], iter([]), max_rows=10)
    assert path.read_text() == ""
    assert result.row_count == 0


def test_preview_escapes_tabs_and_line_breaks_and_shows_nulls():
    text = format_preview(["a", "b"], [("x\ty", "line1\nline2\r"), (None, "back\\slash")])
    assert text.splitlines() == ["a\tb", "x\\ty\tline1\\nline2\\r", "NULL\tback\\\\slash"]


def test_preview_shortens_long_cells_to_200_characters():
    cell = format_preview(["a"], [("z" * 500,)]).splitlines()[1]
    assert len(cell) == 200
    assert cell.endswith("…")


def test_result_text_has_header_paths_and_preview(tmp_path):
    result = CsvResult(row_count=2, truncated=False, preview=[(1, "a"), (2, "b")])
    text = format_result(columns=["n", "s"], result=result, elapsed=1.234, query_id="01abc",
                         sql_path=tmp_path / "01-q.sql", csv_path=tmp_path / "01-q.csv", max_rows=100000)
    lines = text.splitlines()
    assert lines[0] == "Rows: 2 | Columns: 2 | Seconds: 1.23 | Query ID: 01abc"
    assert lines[1] == f"SQL: {tmp_path / '01-q.sql'}"
    assert lines[2] == f"CSV: {tmp_path / '01-q.csv'}"
    assert lines[3] == "Preview (2 of 2 rows):"
    assert lines[4:] == ["n\ts", "1\ta", "2\tb"]


def test_result_text_notes_truncation(tmp_path):
    result = CsvResult(row_count=100, truncated=True, preview=[(i,) for i in range(50)])
    text = format_result(columns=["n"], result=result, elapsed=0.5, query_id="q1",
                         sql_path=tmp_path / "a.sql", csv_path=tmp_path / "a.csv", max_rows=100)
    assert "Preview (50 of 100 rows):" in text
    assert text.splitlines()[-1] == ("Note: the CSV stopped at max_rows=100. More rows exist; "
                                     "narrow the query or raise max_rows.")


def test_result_text_for_zero_rows(tmp_path):  # Review Focus 5
    result = CsvResult(row_count=0, truncated=False, preview=[])
    text = format_result(columns=["a"], result=result, elapsed=0.1, query_id=None,
                         sql_path=tmp_path / "a.sql", csv_path=tmp_path / "a.csv", max_rows=10)
    assert text.splitlines()[0] == "Rows: 0 | Columns: 1 | Seconds: 0.10 | Query ID: unknown"
    assert text.splitlines()[-1] == "Preview: no rows."
