"""Tests for the --allow-sql-gated execute_sql_query MCP tool (tools.py)."""

from unittest.mock import patch

import pytest

from mcp_1c77 import mssql_client, tools


@pytest.fixture(autouse=True)
def reset_sql_state():
    yield
    tools.set_sql_allowed(False)
    tools._md_path = ""
    tools._data_dir = None


def test_disabled_without_allow_sql(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    tools.set_data_dir(str(tmp_path))
    assert tools.sql_allowed() is False
    result = tools.execute_sql_query("SELECT 1")
    assert "отключены" in result
    assert "--allow-sql" in result


def test_missing_dba_file(tmp_path):
    tools.set_sql_allowed(True)
    tools.set_data_dir(str(tmp_path))
    result = tools.execute_sql_query("SELECT 1")
    assert "1Cv7.DBA не найден" in result


def test_rejects_non_select_without_connecting(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    tools.set_sql_allowed(True)
    tools.set_data_dir(str(tmp_path))
    with patch.object(mssql_client, "run_select_query") as run:
        result = tools.execute_sql_query("DROP TABLE T")
        run.assert_not_called()
    assert "отклонён" in result


def test_valid_select_calls_run_select_query(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    tools.set_sql_allowed(True)
    tools.set_data_dir(str(tmp_path))
    fake_result = mssql_client.QueryResult(
        columns=["a", "b"], rows=[(1, "x"), (2, None)], truncated=False
    )
    with patch.object(mssql_client, "run_select_query", return_value=fake_result) as run:
        result = tools.execute_sql_query("SELECT a, b FROM T", max_rows=50)
        run.assert_called_once()
        args, kwargs = run.call_args
        assert args[0] == tmp_path / "1cv7.dba"
        assert args[1] == "SELECT a, b FROM T"
        assert args[2] == 50
    assert "a | b" in result
    assert "1 | x" in result
    assert "2 | " in result


def test_truncated_result_notes_it(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    tools.set_sql_allowed(True)
    tools.set_data_dir(str(tmp_path))
    fake_result = mssql_client.QueryResult(columns=["a"], rows=[(1,)], truncated=True)
    with patch.object(mssql_client, "run_select_query", return_value=fake_result):
        result = tools.execute_sql_query("SELECT a FROM T", max_rows=1)
    assert "обрезан" in result


def test_execution_error_returned_as_text(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    tools.set_sql_allowed(True)
    tools.set_data_dir(str(tmp_path))
    with patch.object(
        mssql_client,
        "run_select_query",
        side_effect=mssql_client.QueryExecutionError("Не удалось подключиться к MSSQL: boom"),
    ):
        result = tools.execute_sql_query("SELECT 1")
    assert "Не удалось подключиться" in result
