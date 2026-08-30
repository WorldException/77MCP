"""Tests for the read-only SQL validator used by execute_sql_query."""

import pytest

from mcp_1c77.sql_guard import assert_readonly_select

ACCEPTED = [
    "SELECT * FROM T",
    "select top 5 * from _1SUSERS",
    "SELECT * FROM T -- trailing comment",
    "SELECT * FROM T /* block comment */ WHERE 1=1",
    "WITH cte AS (SELECT 1 AS x) SELECT * FROM cte",
    "SELECT 'insert into fake' AS col",
    "SELECT 'drop table x; delete from y' AS col",
]

REJECTED = [
    "",
    "   ",
    "INSERT INTO T VALUES (1)",
    "UPDATE T SET a=1",
    "DELETE FROM T",
    "MERGE INTO T USING S ON T.id=S.id WHEN MATCHED THEN UPDATE SET a=1",
    "CREATE TABLE T (a int)",
    "ALTER TABLE T ADD b int",
    "DROP TABLE T",
    "TRUNCATE TABLE T",
    "SELECT * FROM T; DROP TABLE T",
    "SELECT 1; SELECT 2",
    "EXEC sp_who",
    "EXECUTE sp_who",
    "sp_executesql N'select 1'",
    "xp_cmdshell 'dir'",
    "SELECT * INTO NewT FROM T",
    "WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x",
    "GRANT SELECT ON T TO public",
    "BACKUP DATABASE work TO DISK='x'",
]


@pytest.mark.parametrize("sql", ACCEPTED)
def test_accepts_readonly_select(sql):
    assert_readonly_select(sql)  # must not raise


@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_non_readonly(sql):
    with pytest.raises(ValueError):
        assert_readonly_select(sql)
