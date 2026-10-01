import pytest
from snowflake.connector.errors import ProgrammingError

import check_notes
from check_notes import extract_sql_blocks, fill_placeholders, main
from fakes import FakeConnector

NOTE = """# Note

```sql
SELECT 1
```

Text.

```sql
SELECT * FROM t WHERE name = '{{company_name}}' AND id = {{account_id}}
```

```text
not sql
```
"""


def test_extract_sql_blocks_finds_each_sql_fence_and_its_line():
    assert extract_sql_blocks(NOTE) == [
        (3, "SELECT 1"),
        (9, "SELECT * FROM t WHERE name = '{{company_name}}' AND id = {{account_id}}"),
    ]


def test_fill_placeholders_doubles_single_quotes():
    sql = fill_placeholders("SELECT '{{company_name}}', {{account_id}}",
                            {"company_name": "Macy's", "account_id": 42})
    assert sql == "SELECT 'Macy''s', 42"


def test_fill_placeholders_lists_missing_names():
    with pytest.raises(KeyError, match="account_id, company_name"):
        fill_placeholders("SELECT {{company_name}}, {{account_id}}", {})


def test_dry_run_passes_good_notes_and_fails_writes(tmp_path, capsys):
    notes = tmp_path / "references"
    notes.mkdir()
    (notes / "good.md").write_text(NOTE)
    args = ["--notes", str(notes), "--values", str(tmp_path / "none.toml"), "--dry-run"]
    assert main(args) == 0
    (notes / "bad.md").write_text("```sql\nDELETE FROM t\n```\n")
    assert main(args) == 1
    assert "FAIL bad.md:1 BLOCKED" in capsys.readouterr().out


def test_live_failure_line_keeps_the_whole_error_message(tmp_path, capsys, monkeypatch):
    class FailingConnector(FakeConnector):
        def __call__(self):
            conn = super().__call__()
            conn.fail_with = ProgrammingError(
                msg="SQL compilation error:\nObject 'FOO.BAR' does not exist or not authorized.",
                errno=2003
            )
            return conn

    notes = tmp_path / "references"
    notes.mkdir()
    (notes / "test.md").write_text("```sql\nSELECT * FROM FOO.BAR\n```\n")

    monkeypatch.setattr(check_notes, "default_connect", FailingConnector())
    args = ["--notes", str(notes), "--values", str(tmp_path / "none.toml")]
    assert main(args) == 1

    output = capsys.readouterr().out
    assert "SQL compilation error:" in output
    assert "does not exist or not authorized" in output
    # Verify it's on one line (no newline between the two parts)
    for line in output.split("\n"):
        if "FAIL test.md:1" in line:
            assert "SQL compilation error:" in line
            assert "does not exist or not authorized" in line
