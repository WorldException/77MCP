"""Execution of read-only SQL queries against the MSSQL database behind a
1C 7.7 base, using `pytds` — a pure Python TDS driver (no native client
library needed, works the same on Windows and Linux).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytds

from . import mssql_dba
from .sql_guard import assert_readonly_select


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


class QueryExecutionError(Exception):
    pass


def run_select_query(dba_path: str | Path, sql: str, max_rows: int) -> QueryResult:
    """Run a validated read-only SELECT query and return its rows.

    Re-validates `sql` even if the caller already did — this function must
    stay safe to call on its own. The query runs inside a transaction that
    is always rolled back, never committed: a second, database-level line of
    defense in case anything data-modifying ever slipped past the text
    validator (it does not help against non-transactional side effects like
    xp_cmdshell, which is why the validator blocks those explicitly instead
    of relying on this alone).
    """
    assert_readonly_select(sql)

    creds = mssql_dba.read_dba_dict(dba_path)

    try:
        cnx = pytds.connect(
            creds["Server"],
            creds["DB"],
            creds["UID"],
            creds["PWD"],
            port=1433,
            login_timeout=10,
            timeout=30,
            autocommit=False,
            bytes_to_unicode=True,
        )
    except Exception as e:
        raise QueryExecutionError(f"Не удалось подключиться к MSSQL: {e}") from e

    try:
        with cnx.cursor() as cursor:
            try:
                cursor.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                rows = cursor.fetchmany(max_rows + 1)
            except Exception as e:
                raise QueryExecutionError(f"Ошибка выполнения запроса: {e}") from e
            finally:
                cnx.rollback()
    finally:
        cnx.close()

    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]
    return QueryResult(columns=columns, rows=[tuple(r) for r in rows], truncated=truncated)
