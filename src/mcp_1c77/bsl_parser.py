"""Lightweight line-based structural parser for 1C 7.7 module text (BSL).

Not a full tokenizer — matches whole-line patterns for procedure/function
headers, their end markers, and module-level variable declarations, in the
same spirit as the existing line-based module slicing/search in tools.py.
Supports both Russian and English 1C 7.7 syntax keywords.
"""

from __future__ import annotations

import re

from .models import ModuleProcedure, ModuleStructure, ModuleVariable

_PROC_RE = re.compile(
    r'^\s*(Процедура|Procedure|Функция|Function)\s+'
    r'([A-Za-zА-Яа-яЁё0-9_]+)\s*\(([^)]*)\)\s*(Экспорт|Export)?',
    re.IGNORECASE,
)
_END_PROC_RE = re.compile(r'^\s*(КонецПроцедуры|EndProcedure)\b', re.IGNORECASE)
_END_FUNC_RE = re.compile(r'^\s*(КонецФункции|EndFunction)\b', re.IGNORECASE)
_VAR_RE = re.compile(r'^\s*(Перем|Var)\s+(.+)', re.IGNORECASE)
_FORWARD_DECL_RE = re.compile(r'\bДалее\b', re.IGNORECASE)


def _is_function(keyword: str) -> bool:
    return keyword.lower() in ("функция", "function")


def _split_params(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _split_var_names(raw: str) -> list[tuple[str, bool]]:
    """Split a `Перем A, Б Экспорт;` declaration into [(name, exported), ...]."""
    raw = raw.strip().rstrip(";").strip()
    result: list[tuple[str, bool]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        exported = bool(re.search(r'\b(Экспорт|Export)\b', part, re.IGNORECASE))
        name = re.sub(r'\b(Экспорт|Export)\b', '', part, flags=re.IGNORECASE).strip()
        if name:
            result.append((name, exported))
    return result


def parse_module_structure(text: str) -> ModuleStructure:
    """Parse module text into module-level variables and procedures/functions.

    Local `Перем` declarations inside a procedure/function body are excluded
    from the variables list — only top-level (module-scope) declarations
    are included.
    """
    lines = text.splitlines()
    variables: list[ModuleVariable] = []
    procedures: list[ModuleProcedure] = []

    in_proc: ModuleProcedure | None = None
    pending_var_buf: str | None = None
    pending_var_start_line = 0

    for idx, line in enumerate(lines, start=1):
        if in_proc is not None:
            if _is_function(in_proc.kind) and _END_FUNC_RE.match(line):
                in_proc.end_line = idx
                procedures.append(in_proc)
                in_proc = None
            elif not _is_function(in_proc.kind) and _END_PROC_RE.match(line):
                in_proc.end_line = idx
                procedures.append(in_proc)
                in_proc = None
            continue

        if pending_var_buf is not None:
            pending_var_buf += " " + line.strip()
            if ";" in line:
                for name, exported in _split_var_names(pending_var_buf):
                    variables.append(ModuleVariable(name=name, exported=exported, line=pending_var_start_line))
                pending_var_buf = None
            continue

        proc_m = _PROC_RE.match(line)
        if proc_m:
            keyword, name, params_raw, export = proc_m.groups()
            if _FORWARD_DECL_RE.search(line[proc_m.end():]):
                # Forward declaration ("Процедура Имя(...) Далее") — no body here,
                # the real definition with a matching КонецПроцедуры appears later.
                continue
            in_proc = ModuleProcedure(
                kind="Функция" if _is_function(keyword) else "Процедура",
                name=name,
                params=_split_params(params_raw),
                exported=bool(export),
                start_line=idx,
                end_line=idx,
            )
            continue

        var_m = _VAR_RE.match(line)
        if var_m:
            body = var_m.group(2)
            if ";" in body:
                for name, exported in _split_var_names(body):
                    variables.append(ModuleVariable(name=name, exported=exported, line=idx))
            else:
                pending_var_buf = body
                pending_var_start_line = idx

    # Unterminated procedure at EOF — close it at the last line as a best effort.
    if in_proc is not None:
        in_proc.end_line = len(lines)
        procedures.append(in_proc)

    return ModuleStructure(variables=variables, procedures=procedures)
