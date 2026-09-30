import threading
from datetime import date

from results import question_dir, save_query, slugify


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
