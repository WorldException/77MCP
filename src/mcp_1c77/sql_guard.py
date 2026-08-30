"""Read-only SQL validator for the `execute_sql_query` MCP tool.

This is the primary safety gate for running LLM-supplied SQL against a live
MSSQL database: it must reject anything other than a single `SELECT`
(optionally preceded by a `WITH` CTE) statement, including data modification
smuggled inside a CTE, a stacked/batched statement, or a stored-procedure
call. See `mssql_client.run_select_query` for the second layer of defense
(the query is executed inside a transaction that is always rolled back).
"""

from __future__ import annotations

import sqlparse
from sqlparse.tokens import DDL, DML, Keyword, Name

_FORBIDDEN_KEYWORDS = {
    "exec",
    "execute",
    "grant",
    "revoke",
    "deny",
    "bulk",
    "openrowset",
    "openquery",
    "opendatasource",
    "backup",
    "restore",
    "dbcc",
    "use",
    "shutdown",
    "kill",
    "into",
}

_FORBIDDEN_NAME_PREFIXES = ("sp_", "xp_")


def assert_readonly_select(sql: str) -> None:
    """Raise ValueError if `sql` is anything other than a single read-only
    SELECT (optionally with a leading WITH CTE) statement."""
    stripped = sqlparse.format(sql, strip_comments=True).strip()
    if not stripped:
        raise ValueError("Пустой запрос.")

    statements = [s for s in sqlparse.split(stripped) if s.strip()]
    if len(statements) == 0:
        raise ValueError("Пустой запрос.")
    if len(statements) > 1:
        raise ValueError(
            "Разрешён только один SQL-оператор за вызов "
            "(несколько операторов через ';' запрещены)."
        )

    parsed = sqlparse.parse(statements[0])
    if not parsed:
        raise ValueError("Не удалось разобрать SQL-запрос.")
    tokens = [t for t in parsed[0].flatten() if not t.is_whitespace]
    if not tokens:
        raise ValueError("Пустой запрос.")

    first = tokens[0]
    if not (
        (first.ttype is DML and first.value.upper() == "SELECT")
        or (first.ttype is Keyword.CTE and first.value.upper() == "WITH")
    ):
        raise ValueError(
            "Разрешены только запросы на выборку данных (SELECT), "
            "в т.ч. с предваряющим WITH (CTE)."
        )

    for tok in tokens:
        value = tok.value.strip().lower()
        if not value:
            continue
        if tok.ttype in (DML, DDL) and value != "select":
            raise ValueError(
                f"Оператор изменения данных запрещён: '{tok.value.strip()}'."
            )
        if tok.ttype is Keyword and value in _FORBIDDEN_KEYWORDS:
            raise ValueError(f"Ключевое слово запрещено: '{tok.value.strip()}'.")
        if tok.ttype is Name and value.startswith(_FORBIDDEN_NAME_PREFIXES):
            raise ValueError(
                f"Вызов системной/пользовательской процедуры запрещён: '{tok.value.strip()}'."
            )
