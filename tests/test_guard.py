import pytest

from guard import Blocked, check_sql

ALLOWED = {
    "select": ("SELECT 1", "SELECT"),
    "with": ("WITH a AS (SELECT 1 AS x) SELECT * FROM a", "SELECT"),
    "union": ("SELECT 1 UNION ALL SELECT 2", "SELECT"),
    "intersect": ("SELECT 1 INTERSECT SELECT 1", "SELECT"),
    "minus": ("SELECT 1 MINUS SELECT 2", "SELECT"),
    "show": ("SHOW TABLES IN SCHEMA TRANSFORMED.SALES", "SHOW"),
    "show_parsed_as_command": ("SHOW PARAMETERS LIKE 'ALLOW_ID_TOKEN' IN ACCOUNT", "SHOW"),
    "describe": ("DESCRIBE TABLE CONFORMED.SFDC.STG_SFDC_ACCOUNT", "DESCRIBE"),
    "desc_view": ("DESC VIEW CONFORMED.ENTITIES.STG_ENTITIES", "DESCRIBE"),
    # Review Focus 2: real Snowflake read syntax must pass.
    "qualify": ("SELECT a, ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) rn FROM t QUALIFY rn = 1", "SELECT"),
    "flatten": ("SELECT f.value FROM t, LATERAL FLATTEN(input => t.v) f", "SELECT"),
    "cast_iff_ilike": ("SELECT x::DATE, IFF(a ILIKE '%y%', 1, 0) FROM t", "SELECT"),
    "pivot": ("SELECT * FROM t PIVOT(SUM(amount) FOR month IN ('JAN', 'FEB')) AS p", "SELECT"),
    "sample": ("SELECT * FROM t SAMPLE (1) LIMIT 10", "SELECT"),
    "dollar_string": ("SELECT $$a;b$$", "SELECT"),
    "trailing_semicolon": ("SELECT 1;", "SELECT"),
    "trailing_comment": ("SELECT 1; -- note", "SELECT"),
    "semicolon_in_string": ("SELECT 'x; DROP TABLE t' AS y", "SELECT"),
}


@pytest.mark.parametrize("sql,kind", ALLOWED.values(), ids=ALLOWED.keys())
def test_allows_single_reads(sql, kind):
    assert check_sql(sql) == kind


REFUSED = {
    "delete": ("DELETE FROM t WHERE 1=1", "Delete"),
    "insert": ("INSERT INTO t SELECT 1", "Insert"),
    "update": ("UPDATE t SET a = 1", "Update"),
    "merge": ("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.a = s.a", "Merge"),
    "create": ("CREATE TABLE t AS SELECT 1", "Create"),
    "drop": ("DROP TABLE t", "Drop"),
    "alter": ("ALTER TABLE t ADD COLUMN c INT", "Alter"),
    "truncate": ("TRUNCATE TABLE t", "TruncateTable"),
    "grant": ("GRANT SELECT ON TABLE t TO ROLE r", "Grant"),
    "use": ("USE WAREHOUSE X", "Use"),
    "call": ("CALL my_proc(1)", "CALL"),
    "copy": ("COPY INTO t FROM @stage", "Copy"),
    "put": ("PUT file:///tmp/x.csv @~/stage", "Put"),
    "get": ("GET @~/stage file:///tmp/", "GET"),
    "explain": ("EXPLAIN SELECT 1", "EXPLAIN"),
    "select_into": ("SELECT * INTO t2 FROM t", "INTO"),
    "two_statements": ("SELECT 1; DELETE FROM t", "2 statements"),
    "write_after_comment": ("SELECT 1; -- hi\nDELETE FROM t", "2 statements"),
    "write_behind_comment": ("/* SELECT */ DELETE FROM t", "Delete"),
    "unparseable": ("BEGIN DELETE FROM t; END", "could not parse"),
    "garbage": ("SELEC * FRM t", "Alias"),
    "empty": ("", "no statement"),
    "only_comment": ("-- nothing", "no statement"),
}


@pytest.mark.parametrize("sql,reason", REFUSED.values(), ids=REFUSED.keys())
def test_refuses_everything_else(sql, reason):
    with pytest.raises(Blocked) as exc:
        check_sql(sql)
    assert reason in str(exc.value)
