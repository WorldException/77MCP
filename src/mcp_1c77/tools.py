"""MCP tool definitions for 1C 7.7 metadata server."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path

from . import ert_writer, sql_naming
from .dialog_model import DialogControl
from .dialog_parser import default_dialog, parse_dialog, serialize_dialog
from .ert_loader import ErtLoader
from .metadata import TYPE_CODES, ConfigurationLoader
from .models import ModuleProcedure, ModuleStructure

# Global loader instance shared across all tool calls
_loader = ConfigurationLoader()
_md_path: str = ""
_data_dir: Path | None = None

# Global loader instance for external processing (.ert) files
_ert_loader = ErtLoader()

# Optional writable directory for creating/editing .ert files via MCP.
_edit_path: Path | None = None


def set_data_dir(path: str) -> None:
    """Restrict reload_configuration to files inside this directory."""
    global _data_dir
    _data_dir = Path(path).resolve()


def _resolve_within_data_dir(path: str) -> Path | None:
    """Resolve `path` and return it only if it stays inside _data_dir.

    If _data_dir is not set, no sandbox is enforced and the path is returned as-is.
    A bare filename is resolved relative to _data_dir.
    """
    p = Path(path)
    if _data_dir is None:
        return p.resolve() if p.is_absolute() else p
    candidate = (p if p.is_absolute() else _data_dir / p).resolve()
    try:
        candidate.relative_to(_data_dir)
    except ValueError:
        return None
    return candidate

_NOT_LOADED_MSG = (
    "Конфигурация не загружена. "
    "Загрузите файл 1Cv7.MD через веб-интерфейс http://localhost:8080/"
)

_DOCUMENT_SYSTEM_FIELDS: dict[str, str] = {
    "НомерДок": "Строка",
    "ДатаДок": "Дата",
    "Автор": "Справочник",
    "Фирма": "Справочник",
    "ТекущийДокумент": "Документ",
}

_CATALOG_SYSTEM_FIELDS: dict[str, str] = {
    "Код": "Строка",
    "Наименование": "Строка",
    "ПометкаУдаления": "Логический",
    "Родитель": "Справочник",
    "Владелец": "Справочник",
}

# Regex for extracting 1C 7.7 field paths: Тип.Имя.Реквизит[.ПодРеквизит...]
_QUERY_PATH_RE = re.compile(
    r'\b(Документ|Справочник|Регистр|Журнал|Перечисление)'
    r'\.([А-Яа-яЁёA-Za-z0-9_]+)'
    r'((?:\.[А-Яа-яЁёA-Za-z0-9_]+)+)',
    re.UNICODE,
)


def _ensure_loaded() -> str | None:
    """Return error message if configuration is not loaded, else None."""
    if not _loader.is_loaded:
        return _NOT_LOADED_MSG
    return None


def get_loader() -> ConfigurationLoader:
    """Get the global ConfigurationLoader instance."""
    return _loader


def init(md_path: str) -> None:
    """Initialize the loader with a configuration file. Called at server startup."""
    global _md_path
    _md_path = md_path
    _loader.load(md_path)


def reload_configuration(path: str = "") -> str:
    """Reload the current configuration or load a different file.

    If a sandbox directory was set via set_data_dir(), the path must resolve
    inside it; absolute paths outside the sandbox are rejected.

    Args:
        path: Path to 1Cv7.MD file. If empty, reloads the current file.

    Returns:
        Configuration summary text.
    """
    global _md_path
    if path:
        resolved = _resolve_within_data_dir(path)
        if resolved is None:
            return (
                f"Путь '{path}' находится вне разрешённого каталога "
                f"({_data_dir}). Загружайте файл через веб-интерфейс."
            )
        target = str(resolved)
    else:
        target = _md_path
    if not target:
        return "Путь к файлу не указан."
    _md_path = target
    config = _loader.load(target)
    return config.summary()


def list_objects(object_type: str = "") -> str:
    """List metadata objects, optionally filtered by type."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    lines = []

    type_lower = object_type.lower() if object_type else ""

    def _should_include(type_name: str) -> bool:
        if not type_lower:
            return True
        return type_lower in type_name.lower()

    if _should_include("справочник") or _should_include("catalog"):
        if config.catalogs:
            lines.append(f"## Справочники ({len(config.catalogs)})")
            for obj in config.catalogs:
                comment = f" — {obj.comment}" if obj.comment else ""
                sql = f" [SQL: {sql_naming.catalog_table(obj.id)}]" if obj.id else ""
                lines.append(f"  - {obj.name}{comment}{sql}")
            lines.append("")

    if _should_include("документ") or _should_include("document"):
        if config.documents:
            lines.append(f"## Документы ({len(config.documents)})")
            for obj in config.documents:
                comment = f" — {obj.comment}" if obj.comment else ""
                sql = (
                    f" [SQL: {sql_naming.document_header_table(obj.id)}/"
                    f"{sql_naming.document_tabular_table(obj.id)}]"
                    if obj.id else ""
                )
                lines.append(f"  - {obj.name}{comment}{sql}")
            lines.append("")

    if _should_include("регистр") or _should_include("register"):
        if config.registers:
            lines.append(f"## Регистры ({len(config.registers)})")
            for obj in config.registers:
                comment = f" — {obj.comment}" if obj.comment else ""
                sql = (
                    f" [SQL: {sql_naming.register_totals_table(obj.id)}/"
                    f"{sql_naming.register_movements_table(obj.id)}]"
                    if obj.id else ""
                )
                lines.append(f"  - {obj.name}{comment}{sql}")
            lines.append("")

    if _should_include("перечисление") or _should_include("enum"):
        if config.enums:
            lines.append(f"## Перечисления ({len(config.enums)})")
            for obj in config.enums:
                comment = f" — {obj.comment}" if obj.comment else ""
                lines.append(f"  - {obj.name}{comment}")
            lines.append("")

    if _should_include("отчёт") or _should_include("отчет") or _should_include("обработка") or _should_include("report"):
        if config.reports:
            lines.append(f"## Отчёты/Обработки ({len(config.reports)})")
            for obj in config.reports:
                comment = f" — {obj.comment}" if obj.comment else ""
                lines.append(f"  - {obj.name}{comment}")
            lines.append("")

    if _should_include("журнал") or _should_include("journal"):
        if config.journals:
            lines.append(f"## Журналы ({len(config.journals)})")
            for obj in config.journals:
                comment = f" — {obj.comment}" if obj.comment else ""
                lines.append(f"  - {obj.name}{comment}")
            lines.append("")

    if _should_include("константа") or _should_include("constant"):
        if config.constants:
            lines.append(f"## Константы ({len(config.constants)})")
            for obj in config.constants:
                comment = f" — {obj.comment}" if obj.comment else ""
                sql = f" [SQL: {sql_naming.constant_field(obj.id)} в _1SCONST]" if obj.id else ""
                lines.append(f"  - {obj.name}: {obj.type}{comment}{sql}")
            lines.append("")

    if _should_include("видрасчёта") or _should_include("видрасчета") or _should_include("calcvar"):
        if config.calc_vars:
            lines.append(f"## Виды расчётов ({len(config.calc_vars)})")
            for obj in config.calc_vars:
                comment = f" — {obj.comment}" if obj.comment else ""
                lines.append(f"  - {obj.name}{comment}")
            lines.append("")

    if (
        _should_include("плансчетов")
        or _should_include("план счетов")
        or _should_include("пс")
        or _should_include("chartofaccounts")
        or _should_include("chart of accounts")
    ):
        coa = config.chart_of_accounts
        if coa and coa.id:
            lines.append("## План счетов (1)")
            comment = f" — {coa.comment}" if coa.comment else ""
            name = coa.name or coa.id
            lines.append(f"  - {name}{comment}")
            lines.append("")

    if not lines:
        return f"Объекты типа '{object_type}' не найдены."

    return "\n".join(lines)


def get_object(object_type: str, name: str) -> str:
    """Get detailed information about a metadata object."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    type_lower = object_type.lower()

    if type_lower in ("справочник", "catalog"):
        for obj in config.catalogs:
            if obj.name == name:
                return _format_catalog(obj)

    elif type_lower in ("документ", "document"):
        for obj in config.documents:
            if obj.name == name:
                return _format_document(obj)

    elif type_lower in ("регистр", "register"):
        for obj in config.registers:
            if obj.name == name:
                return _format_register(obj)

    elif type_lower in ("перечисление", "enum"):
        for obj in config.enums:
            if obj.name == name:
                return _format_enum(obj)

    elif type_lower in ("отчёт", "отчет", "обработка", "report"):
        for obj in config.reports:
            if obj.name == name:
                return _format_report(obj)

    elif type_lower in ("журнал", "journal"):
        for obj in config.journals:
            if obj.name == name:
                return _format_journal(obj)

    elif type_lower in ("плансчетов", "пс", "chartofaccounts"):
        if config.chart_of_accounts and config.chart_of_accounts.name == name:
            return _format_chart_of_accounts(config.chart_of_accounts)

    elif type_lower in ("константа", "constant"):
        for obj in config.constants:
            if obj.name == name:
                return _format_constant(obj)

    return f"Объект '{object_type}.{name}' не найден."


_MAX_MODULE_CHARS = 50_000
_MAX_MODULE_LINES_FOR_TRUNCATION = 1500


def _slice_module(text: str, start_line: int, end_line: int, label: str) -> str:
    """Apply explicit line range or auto-truncate large modules."""
    lines = text.splitlines()
    total = len(lines)

    # Explicit range requested
    if start_line > 0 or end_line > 0:
        start = max(1, start_line) if start_line > 0 else 1
        if start > total:
            return f"Модуль '{label}' содержит {total} строк. Запрошенная строка {start} выходит за пределы."
        end = end_line if end_line > 0 else total
        end = min(end, total)
        header = f"# {label}: строки {start}–{end} из {total}"
        return header + "\n" + "\n".join(lines[start - 1 : end])

    # No range — return full text if small enough
    if len(text) <= _MAX_MODULE_CHARS:
        return text

    # Auto-truncate large modules
    shown = min(_MAX_MODULE_LINES_FOR_TRUNCATION, total)
    header = f"# {label}: строки 1–{shown} из {total}"
    tool_hint = (
        "get_global_module"
        if label == "ГлобальныйМодуль"
        else "get_module"
    )
    footer = (
        f"\n\n---\nМодуль усечён (показаны строки 1–{shown} из {total}, "
        f"{len(text)} симв.). "
        f"Для остальных строк вызовите {tool_hint}(start_line=…, end_line=…)."
    )
    return header + "\n" + "\n".join(lines[:shown]) + footer


def get_module(object_type: str, name: str, start_line: int = 0, end_line: int = 0) -> str:
    """Get the module source code of a metadata object."""
    if err := _ensure_loaded():
        return err
    module = _loader.get_module(object_type, name)
    if module is None:
        return f"Модуль объекта '{object_type}.{name}' не найден."
    label = f"{object_type}.{name}"
    return _slice_module(module, start_line, end_line, label)


def get_form(object_type: str, name: str) -> str:
    """Get the form definition of a metadata object."""
    if err := _ensure_loaded():
        return err
    form = _loader.get_form(object_type, name)
    if form is None:
        return f"Форма объекта '{object_type}.{name}' не найдена."
    return form


def search(query: str) -> str:
    """Search across all metadata objects by name, synonym, or comment."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    query_lower = query.lower()
    results = []

    for obj in config.constants:
        if _matches(obj, query_lower):
            results.append(f"Константа: {obj.name} — {obj.comment}")

    for obj in config.catalogs:
        if _matches(obj, query_lower):
            results.append(f"Справочник: {obj.name} — {obj.comment}")

    for obj in config.documents:
        if _matches(obj, query_lower):
            results.append(f"Документ: {obj.name} — {obj.comment}")

    for obj in config.registers:
        if _matches(obj, query_lower):
            results.append(f"Регистр: {obj.name} — {obj.comment}")

    for obj in config.enums:
        if _matches(obj, query_lower):
            results.append(f"Перечисление: {obj.name} — {obj.comment}")
        for val in obj.values:
            if query_lower in val.name.lower() or query_lower in val.comment.lower():
                results.append(f"Перечисление.Значение: {obj.name}.{val.name} — {val.comment}")

    for obj in config.reports:
        if _matches(obj, query_lower):
            results.append(f"Отчёт: {obj.name} — {obj.comment}")

    for obj in config.journals:
        if _matches(obj, query_lower):
            results.append(f"Журнал: {obj.name} — {obj.comment}")

    for obj in config.calc_vars:
        if _matches(obj, query_lower):
            results.append(f"ВидРасчёта: {obj.name} — {obj.comment}")

    coa = config.chart_of_accounts
    if coa and coa.id:
        if _matches(coa, query_lower):
            results.append(f"ПланСчетов: {coa.name or coa.id} — {coa.comment}")
        for a in coa.attributes:
            if query_lower in a.name.lower() or query_lower in a.comment.lower():
                results.append(f"ПланСчетов.Субконто: {coa.name or coa.id}.{a.name} — {a.comment}")

    if not results:
        return f"По запросу '{query}' ничего не найдено."

    return f"Найдено {len(results)} результатов:\n" + "\n".join(results)


def get_configuration_info() -> str:
    """Get general information about the loaded configuration."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    lines = [config.summary()]

    # Add chart of accounts info
    if config.chart_of_accounts and config.chart_of_accounts.id:
        coa = config.chart_of_accounts
        coa_name = coa.name or coa.id
        lines.append(f"План счетов: {coa_name}")
        if coa.attributes:
            lines.append(f"  Субконто: {len(coa.attributes)}")

    return "\n".join(lines)


# --- Internal helpers for path validation ---


@dataclass
class _PathResult:
    valid: bool = False
    error: str = ""
    similar: list[str] = dc_field(default_factory=list)
    available_header: list[str] = dc_field(default_factory=list)
    available_tabular: list[str] = dc_field(default_factory=list)


def _find_object_by_id(config, obj_id: str):
    """Search catalogs, enums, documents by .id. Returns (type_name, obj) or None."""
    for cat in config.catalogs:
        if cat.id == obj_id:
            return ("Справочник", cat)
    for enm in config.enums:
        if enm.id == obj_id:
            return ("Перечисление", enm)
    for doc in config.documents:
        if doc.id == obj_id:
            return ("Документ", doc)
    return None


def _find_similar(query: str, candidates: list[str], n: int = 5) -> list[str]:
    """Return up to n similar names: substring matches first, then difflib close matches."""
    query_lower = query.lower()
    seen: set[str] = set()
    result: list[str] = []

    for c in candidates:
        if query_lower in c.lower() or c.lower() in query_lower:
            if c not in seen:
                seen.add(c)
                result.append(c)
            if len(result) >= n:
                return result

    for c in difflib.get_close_matches(query, candidates, n=n, cutoff=0.5):
        if c not in seen:
            seen.add(c)
            result.append(c)
        if len(result) >= n:
            break

    return result


def _format_ref(attr) -> str:
    """Format a reference annotation for an attribute using the global loader config."""
    if not attr.ref_type_id or attr.type not in ("Справочник", "Перечисление", "Документ"):
        return ""
    if not _loader.is_loaded:
        return f" -> [{attr.ref_type_id}]"
    found = _find_object_by_id(_loader.config, attr.ref_type_id)
    if found:
        _, obj = found
        return f' -> "{obj.name}" [{attr.ref_type_id}]'
    return f" -> [{attr.ref_type_id}]"


def _validate_path_internal(config, object_type: str, obj_name: str, path: str) -> _PathResult:
    """Core path validation logic. Returns _PathResult with valid flag or error details."""
    if not path:
        return _PathResult(error="Путь не может быть пустым")

    type_lower = object_type.lower()

    # Find the root object
    current_type = object_type
    current_obj = None

    if type_lower in ("документ", "document"):
        for doc in config.documents:
            if doc.name == obj_name:
                current_obj = doc
                current_type = "Документ"
                break
    elif type_lower in ("справочник", "catalog"):
        for cat in config.catalogs:
            if cat.name == obj_name:
                current_obj = cat
                current_type = "Справочник"
                break
    elif type_lower in ("регистр", "register"):
        for reg in config.registers:
            if reg.name == obj_name:
                current_obj = reg
                current_type = "Регистр"
                break
    elif type_lower in ("перечисление", "enum"):
        for enm in config.enums:
            if enm.name == obj_name:
                current_obj = enm
                current_type = "Перечисление"
                break
    elif type_lower in ("журнал", "journal"):
        for jrn in config.journals:
            if jrn.name == obj_name:
                current_obj = jrn
                current_type = "Журнал"
                break

    if current_obj is None:
        return _PathResult(error=f"Объект '{object_type}.{obj_name}' не найден")

    # Special case: Enum — validate single-level value access
    if current_type == "Перечисление":
        parts = path.split(".")
        if len(parts) == 1:
            val_names = [v.name for v in current_obj.values]
            if path in val_names:
                return _PathResult(valid=True)
            similar = _find_similar(path, val_names)
            return _PathResult(
                error=f"Значение '{path}' не найдено в перечислении '{obj_name}'",
                similar=similar,
            )
        return _PathResult(error="Перечисление поддерживает только одноуровневый доступ к значениям")

    # Special case: Journal — cannot validate columns
    if current_type == "Журнал":
        return _PathResult(valid=True)

    parts = path.split(".")

    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1

        # Build attribute lists for current object
        if current_type == "Документ":
            head_attrs = list(current_obj.head_attributes)
            table_attrs = list(current_obj.table_attributes)
            all_attrs = head_attrs + table_attrs
            sys_fields = _DOCUMENT_SYSTEM_FIELDS
        elif current_type == "Справочник":
            head_attrs = list(current_obj.attributes)
            table_attrs = []
            all_attrs = head_attrs
            sys_fields = _CATALOG_SYSTEM_FIELDS
        elif current_type == "Регистр":
            head_attrs = (
                list(current_obj.dimensions)
                + list(current_obj.resources)
                + list(current_obj.attributes)
            )
            table_attrs = []
            all_attrs = head_attrs
            sys_fields = {}
        else:
            return _PathResult(
                error=f"Тип '{current_type}' не поддерживает вложенное обращение к реквизитам"
            )

        # Check system fields
        if part in sys_fields:
            if is_last:
                return _PathResult(valid=True)
            return _PathResult(
                error=f"Системный реквизит '{part}' не поддерживает вложенное обращение"
            )

        # Find attribute by name
        found_attr = None
        for attr in all_attrs:
            if attr.name == part:
                found_attr = attr
                break

        if found_attr is None:
            all_names = list(sys_fields.keys()) + [a.name for a in all_attrs]
            similar = _find_similar(part, all_names)
            return _PathResult(
                error=f"Реквизит '{part}' не найден в '{current_type}.{current_obj.name}'",
                similar=similar,
                available_header=[a.name for a in head_attrs],
                available_tabular=[a.name for a in table_attrs],
            )

        if is_last:
            return _PathResult(valid=True)

        # Not last segment — must be a traversable reference
        if found_attr.type not in ("Справочник", "Перечисление", "Документ"):
            return _PathResult(
                error=(
                    f"Реквизит '{part}' имеет тип '{found_attr.type}' "
                    f"и не является ссылочным — невозможно продолжить путь"
                )
            )

        if not found_attr.ref_type_id:
            return _PathResult(
                error=f"Реквизит '{part}' является ссылочным, но ID связанного типа не задан"
            )

        ref_result = _find_object_by_id(config, found_attr.ref_type_id)
        if ref_result is None:
            return _PathResult(
                error=(
                    f"Связанный объект с ID '{found_attr.ref_type_id}' "
                    f"для реквизита '{part}' не найден в метаданных"
                )
            )

        current_type, current_obj = ref_result

    return _PathResult(valid=True)


# --- New public tool functions ---


def validate_field_path(object_type: str, name: str, path: str) -> str:
    """Validate a field path against the loaded configuration."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    result = _validate_path_internal(config, object_type, name, path)
    if result.valid:
        return f"OK: '{object_type}.{name}.{path}' — путь валиден"

    lines = [f"ОШИБКА: {result.error}"]
    if result.similar:
        lines.append(f"\nПохожие реквизиты: {', '.join(result.similar)}")
    if result.available_header:
        lines.append(f"\nДоступные реквизиты шапки: {', '.join(result.available_header[:20])}")
    if result.available_tabular:
        lines.append(f"\nДоступные реквизиты табл. части: {', '.join(result.available_tabular[:20])}")
    return "\n".join(lines)


def validate_query(query_text: str) -> str:
    """Validate all field path references found in a 1C 7.7 query/code text."""
    if err := _ensure_loaded():
        return err
    config = _loader.config

    raw_lines = query_text.splitlines()

    # Collect all path occurrences: (line_num, obj_type, obj_name, sub_path)
    occurrences: list[tuple[int, str, str, str]] = []
    for line_num, line in enumerate(raw_lines, start=1):
        normalized = line.lstrip("|").strip()
        for m in _QUERY_PATH_RE.finditer(normalized):
            obj_type = m.group(1)
            obj_name = m.group(2)
            sub_path = m.group(3).lstrip(".")
            occurrences.append((line_num, obj_type, obj_name, sub_path))

    if not occurrences:
        return "Путей обращений к реквизитам в тексте не найдено."

    # Validate unique paths once, cache results
    seen: dict[tuple[str, str, str], _PathResult] = {}
    for _, obj_type, obj_name, sub_path in occurrences:
        key = (obj_type, obj_name, sub_path)
        if key not in seen:
            seen[key] = _validate_path_internal(config, obj_type, obj_name, sub_path)

    total = len(occurrences)
    valid_count = sum(
        1 for _, ot, on, sp in occurrences if seen[(ot, on, sp)].valid
    )
    error_count = total - valid_count

    out: list[str] = [f"Итого путей: {total}, валидных: {valid_count}, ошибок: {error_count}"]

    if error_count:
        out.append("\nОшибки:")
        for line_num, obj_type, obj_name, sub_path in occurrences:
            result = seen[(obj_type, obj_name, sub_path)]
            if not result.valid:
                entry = f"  Строка {line_num}: {obj_type}.{obj_name}.{sub_path}\n    {result.error}"
                if result.similar:
                    entry += f"\n    Похожие: {', '.join(result.similar)}"
                out.append(entry)

    return "\n".join(out)


def search_field(field_name: str, object_type: str = "") -> str:
    """Search for a field by name across all metadata objects (reverse lookup)."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    field_lower = field_name.lower()
    type_lower = object_type.lower() if object_type else ""

    found: list[str] = []
    not_found: list[str] = []

    # Search documents
    if not type_lower or type_lower in ("документ", "document"):
        for doc in config.documents:
            doc_attrs = list(doc.head_attributes) + list(doc.table_attributes)
            matches = [a for a in doc_attrs if a.name.lower() == field_lower]
            if matches:
                for a in matches:
                    ref = _format_ref(a)
                    comment = f" — {a.comment}" if a.comment else ""
                    found.append(f"Документ.{doc.name}: {a.name}: {a.type}({a.length}.{a.precision}){ref}{comment}")
            else:
                not_found.append(f"Документ.{doc.name}")

    # Search catalogs
    if not type_lower or type_lower in ("справочник", "catalog"):
        for cat in config.catalogs:
            matches = [a for a in cat.attributes if a.name.lower() == field_lower]
            if matches:
                for a in matches:
                    ref = _format_ref(a)
                    comment = f" — {a.comment}" if a.comment else ""
                    found.append(f"Справочник.{cat.name}: {a.name}: {a.type}({a.length}.{a.precision}){ref}{comment}")
            else:
                not_found.append(f"Справочник.{cat.name}")

    # Search registers
    if not type_lower or type_lower in ("регистр", "register"):
        for reg in config.registers:
            all_attrs = list(reg.dimensions) + list(reg.resources) + list(reg.attributes)
            matches = [a for a in all_attrs if a.name.lower() == field_lower]
            if matches:
                for a in matches:
                    comment = f" — {a.comment}" if a.comment else ""
                    found.append(f"Регистр.{reg.name}: {a.name}: {a.type}({a.length}.{a.precision}){comment}")
            else:
                not_found.append(f"Регистр.{reg.name}")

    # Search chart of accounts (subconto attributes)
    if not type_lower or type_lower in ("плансчетов", "план счетов", "пс", "chartofaccounts"):
        coa = config.chart_of_accounts
        if coa and coa.id:
            coa_name = coa.name or coa.id
            matches = [a for a in coa.attributes if a.name.lower() == field_lower]
            if matches:
                for a in matches:
                    ref = _format_ref(a)
                    comment = f" — {a.comment}" if a.comment else ""
                    found.append(f"ПланСчетов.{coa_name}: {a.name}: {a.type}({a.length}.{a.precision}){ref}{comment}")
            else:
                not_found.append(f"ПланСчетов.{coa_name}")

    lines: list[str] = []
    if found:
        lines.append(f"Реквизит '{field_name}' найден в {len(found)} объектах:")
        lines.extend(f"  {f}" for f in found)
    else:
        lines.append(f"Реквизит '{field_name}' не найден ни в одном объекте.")

    if not_found:
        display = not_found[:20]
        lines.append(f"\nНЕ найден в ({len(not_found)} объектах):")
        lines.extend(f"  {nf}" for nf in display)
        if len(not_found) > 20:
            lines.append(f"  ... и ещё {len(not_found) - 20}")

    return "\n".join(lines)


def get_objects_batch(object_type: str, names: list[str]) -> str:
    """Get metadata for multiple objects of the same type in a single call."""
    if err := _ensure_loaded():
        return err
    results = [get_object(object_type, name) for name in names]
    return "\n\n---\n\n".join(results)


def get_global_module(start_line: int = 0, end_line: int = 0) -> str:
    """Get the global module source code."""
    if err := _ensure_loaded():
        return err
    module = _loader.get_global_module()
    if module is None:
        return "Глобальный модуль не найден в конфигурации."
    return _slice_module(module, start_line, end_line, "ГлобальныйМодуль")


def list_modules() -> str:
    """List all modules available in the configuration, including the global module."""
    if err := _ensure_loaded():
        return err
    modules = _loader.list_modules()
    if not modules:
        return "Модули не найдены в конфигурации."

    lines = [f"Найдено модулей: {len(modules)}", ""]

    for m in modules:
        if m["kind"] == "global":
            lines.append(f"  * {m['name']} (глобальный)")
        else:
            lines.append(f"  - {m['type']}.{m['name']}")

    return "\n".join(lines)


def search_in_modules(query: str, context_lines: int = 0, limit: int = 200) -> str:
    """Search for text across all module source code in the configuration."""
    if err := _ensure_loaded():
        return err

    query_lower = query.lower()
    output_lines: list[str] = []
    total_matches = 0
    hit_limit = False

    for label, text in _loader.iter_module_entries():
        if hit_limit:
            break
        remaining = limit - total_matches
        if remaining <= 0:
            break
        matches = _find_lines_in_text(text, query_lower, max_results=remaining, context_lines=context_lines)
        for line_num, line_text, ctx_block in matches:
            if context_lines > 0 and ctx_block:
                for cn, cl in ctx_block:
                    prefix = "  " if cn != line_num else ""
                    output_lines.append(f"{label}:{cn}:{prefix}{cl}")
                output_lines.append("--")
            else:
                output_lines.append(f"{label}:{line_num}: {line_text}")
        total_matches += len(matches)
        if total_matches >= limit:
            hit_limit = True

    if not output_lines:
        return f"По запросу '{query}' в модулях ничего не найдено."

    lines = [f"Найдено {total_matches} совпадений в модулях по запросу '{query}':", ""]
    lines.extend(output_lines)
    if hit_limit:
        lines.append(f"\nДостигнут лимит совпадений ({limit}). "
                     f"Используйте limit=… для расширения или уточните запрос.")
    return "\n".join(lines)


def resolve_id(object_id: str) -> str:
    """Resolve an internal object ID to its type and name."""
    if err := _ensure_loaded():
        return err
    result = _loader.resolve_id(object_id)
    if result is None:
        return f"Объект с ID '{object_id}' не найден."
    type_name, name = result
    return f"ID '{object_id}' -> {type_name}.{name}"


# --- Module structure tools (procedures/functions/variables) ---


def _resolve_single_module_structure(
    object_type: str, name: str
) -> tuple[ModuleStructure | None, str, str | None]:
    """Resolve a single module's parsed structure.

    Empty object_type and name together mean the global module; explicit
    "глобальный"/"global" also means the global module. Otherwise both
    object_type and name must be given. Returns (structure, label, error).
    """
    if not object_type and not name:
        structure = _loader.get_global_module_structure()
        if structure is None:
            return None, "ГлобальныйМодуль", "Глобальный модуль не найден в конфигурации."
        return structure, "ГлобальныйМодуль", None

    if object_type.lower() in ("глобальный", "global"):
        structure = _loader.get_global_module_structure()
        if structure is None:
            return None, "ГлобальныйМодуль", "Глобальный модуль не найден в конфигурации."
        return structure, "ГлобальныйМодуль", None

    if not object_type or not name:
        return (
            None,
            "",
            "Укажите object_type и name вместе, либо оставьте оба параметра "
            "пустыми для обращения к глобальному модулю.",
        )

    structure = _loader.get_module_structure(object_type, name)
    label = f"{object_type}.{name}"
    if structure is None:
        return None, label, f"Модуль объекта '{label}' не найден."
    return structure, label, None


def list_module_procedures(object_type: str = "", name: str = "") -> str:
    """List all procedures and functions declared in a module."""
    if err := _ensure_loaded():
        return err
    structure, label, error = _resolve_single_module_structure(object_type, name)
    if error:
        return error
    if not structure.procedures:
        return f"В модуле '{label}' процедуры и функции не найдены."

    lines = [f"# {label}: процедуры и функции ({len(structure.procedures)})", ""]
    for p in structure.procedures:
        params = ", ".join(p.params)
        exp = " Экспорт" if p.exported else ""
        lines.append(f"  - {p.kind} {p.name}({params}){exp}  [строки {p.start_line}-{p.end_line}]")
    return "\n".join(lines)


def get_module_variables(object_type: str = "", name: str = "") -> str:
    """List module-level variables (Перем/Var) declared in a module."""
    if err := _ensure_loaded():
        return err
    structure, label, error = _resolve_single_module_structure(object_type, name)
    if error:
        return error
    if not structure.variables:
        return f"В модуле '{label}' переменные модуля не найдены."

    lines = [f"# {label}: переменные модуля ({len(structure.variables)})", ""]
    for v in structure.variables:
        exp = " Экспорт" if v.exported else ""
        lines.append(f"  - {v.name}{exp}  [строка {v.line}]")
    return "\n".join(lines)


def _find_procedure(structure: ModuleStructure, proc_name: str) -> ModuleProcedure | None:
    proc_name_lower = proc_name.lower()
    for p in structure.procedures:
        if p.name.lower() == proc_name_lower:
            return p
    return None


def get_procedure_source(proc_name: str, object_type: str = "", name: str = "") -> str:
    """Get the source text of a specific procedure or function by name.

    If object_type/name are omitted, searches across all modules in the
    configuration (including the global module).
    """
    if err := _ensure_loaded():
        return err

    if object_type or name:
        structure, label, error = _resolve_single_module_structure(object_type, name)
        if error:
            return error
        match = _find_procedure(structure, proc_name)
        if match is None:
            return f"Процедура/функция '{proc_name}' не найдена в модуле '{label}'."
        text = (
            _loader.get_global_module()
            if label == "ГлобальныйМодуль"
            else _loader.get_module(object_type, name)
        )
        return _slice_module(text, match.start_line, match.end_line, f"{label}.{proc_name}")

    found: list[tuple[str, ModuleProcedure]] = []
    for m in _loader.list_modules():
        if m["kind"] == "global":
            structure = _loader.get_global_module_structure()
            label = "ГлобальныйМодуль"
        else:
            structure = _loader.get_module_structure(m["type"], m["name"])
            label = f"{m['type']}.{m['name']}"
        if structure is None:
            continue
        match = _find_procedure(structure, proc_name)
        if match is not None:
            found.append((label, match))

    if not found:
        return f"Процедура/функция '{proc_name}' не найдена ни в одном модуле."

    if len(found) == 1:
        label, match = found[0]
        if label == "ГлобальныйМодуль":
            text = _loader.get_global_module()
        else:
            obj_type, obj_name = label.split(".", 1)
            text = _loader.get_module(obj_type, obj_name)
        return _slice_module(text, match.start_line, match.end_line, f"{label}.{proc_name}")

    lines = [f"Найдено {len(found)} совпадений для '{proc_name}':", ""]
    for label, match in found:
        lines.append(f"  - {label}  [строки {match.start_line}-{match.end_line}]")
    lines.append("\nУточните object_type и name для получения исходника конкретной процедуры.")
    return "\n".join(lines)


def list_enums() -> str:
    """List all enumerations with their values."""
    if err := _ensure_loaded():
        return err
    config = _loader.config
    if not config.enums:
        return "Перечисления не найдены в конфигурации."

    lines = [f"# Перечисления ({len(config.enums)})", ""]
    for e in config.enums:
        comment = f" — {e.comment}" if e.comment else ""
        lines.append(f"## {e.name}{comment}")
        if e.values:
            for v in e.values:
                vcomment = f" — {v.comment}" if v.comment else ""
                lines.append(f"  - {v.name}{vcomment}")
        else:
            lines.append("  (значений нет)")
        lines.append("")
    return "\n".join(lines)


# --- Formatting helpers ---


def _format_catalog(obj) -> str:
    lines = [
        f"# Справочник: {obj.name}",
        f"ID: {obj.id}",
        f"SQL-таблица: {sql_naming.catalog_table(obj.id)} ({sql_naming.NOTE})",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")

    lines.append("\n## Системные реквизиты (всегда доступны)")
    for fname, ftype in _CATALOG_SYSTEM_FIELDS.items():
        sql_field = sql_naming.CATALOG_SQL_SYSTEM_FIELDS.get(fname, "")
        sql = f" [SQL: {sql_field}]" if sql_field else ""
        lines.append(f"  - {fname}: {ftype}{sql}")

    if obj.attributes:
        lines.append(f"\n## Реквизиты ({len(obj.attributes)})")
        for a in obj.attributes:
            ref = _format_ref(a)
            periodic = "  [периодический]" if a.periodic else ""
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){ref}{periodic}{sql}")
            if a.comment:
                lines.append(f"    {a.comment}")

    if obj.forms:
        lines.append(f"\n## Формы ({len(obj.forms)})")
        for f in obj.forms:
            lines.append(f"  - {f.name} (id={f.id})")

    return "\n".join(lines)


def _format_document(obj) -> str:
    lines = [
        f"# Документ: {obj.name}",
        f"ID: {obj.id}",
        f"SQL-таблица шапки: {sql_naming.document_header_table(obj.id)} ({sql_naming.NOTE})",
        f"SQL-таблица табличной части: {sql_naming.document_tabular_table(obj.id)} ({sql_naming.NOTE})",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.number_length:
        lines.append(f"Длина номера: {obj.number_length}")

    lines.append("\n## Системные реквизиты (всегда доступны в запросах 7.7)")
    for fname, ftype in _DOCUMENT_SYSTEM_FIELDS.items():
        sql_field = sql_naming.DOCUMENT_SQL_SYSTEM_FIELDS.get(fname, "")
        sql = f" [SQL: {sql_field}]" if sql_field else ""
        lines.append(f"  - {fname}: {ftype}{sql}")

    if obj.head_attributes:
        lines.append(f"\n## Реквизиты шапки ({len(obj.head_attributes)})")
        for a in obj.head_attributes:
            ref = _format_ref(a)
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){ref}{sql}")
            if a.comment:
                lines.append(f"    {a.comment}")

    if obj.table_attributes:
        lines.append(f"\n## Табличная часть ({len(obj.table_attributes)})")
        for a in obj.table_attributes:
            ref = _format_ref(a)
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){ref}{sql}")
            if a.comment:
                lines.append(f"    {a.comment}")

    return "\n".join(lines)


def _format_register(obj) -> str:
    lines = [
        f"# Регистр: {obj.name}",
        f"ID: {obj.id}",
        f"SQL-таблица итогов: {sql_naming.register_totals_table(obj.id)} ({sql_naming.NOTE})",
        f"SQL-таблица движений: {sql_naming.register_movements_table(obj.id)} ({sql_naming.NOTE})",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")

    if obj.dimensions:
        lines.append(f"\n## Измерения ({len(obj.dimensions)})")
        for a in obj.dimensions:
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){sql}")

    if obj.resources:
        lines.append(f"\n## Ресурсы ({len(obj.resources)})")
        for a in obj.resources:
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){sql}")

    if obj.attributes:
        lines.append(f"\n## Реквизиты ({len(obj.attributes)})")
        for a in obj.attributes:
            sql = f" [SQL: {sql_naming.attribute_field(a.id)}]" if a.id else ""
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){sql}")

    return "\n".join(lines)


def _format_enum(obj) -> str:
    lines = [
        f"# Перечисление: {obj.name}",
        f"ID: {obj.id}",
        "SQL: нет прямого SQL-представления (значение кодируется в самом ссылочном поле)",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")

    if obj.values:
        lines.append(f"\n## Значения ({len(obj.values)})")
        for v in obj.values:
            comment = f" — {v.comment}" if v.comment else ""
            lines.append(f"  - {v.name}{comment}")

    return "\n".join(lines)


def _format_report(obj) -> str:
    lines = [
        f"# Отчёт/Обработка: {obj.name}",
        f"ID: {obj.id}",
        "SQL: нет прямого SQL-представления",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")
    return "\n".join(lines)


def _format_journal(obj) -> str:
    lines = [
        f"# Журнал: {obj.name}",
        f"ID: {obj.id}",
        "SQL: нет прямого SQL-представления (документы журнала хранятся в общем _1SJOURN)",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")

    if obj.forms:
        lines.append(f"\n## Формы ({len(obj.forms)})")
        for f in obj.forms:
            lines.append(f"  - {f.name} (id={f.id})")

    return "\n".join(lines)


def _format_constant(obj) -> str:
    lines = [
        f"# Константа: {obj.name}",
        f"ID: {obj.id}",
        f"Тип: {obj.type}({obj.length}.{obj.precision})",
        f"SQL-поле: {sql_naming.constant_field(obj.id)} в _1SCONST ({sql_naming.NOTE})",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")
    return "\n".join(lines)


def _format_chart_of_accounts(obj) -> str:
    lines = [
        f"# План счетов: {obj.name or obj.id}",
        f"ID: {obj.id}",
        "SQL: нет прямого SQL-представления",
    ]
    if obj.comment:
        lines.append(f"Комментарий: {obj.comment}")
    if obj.synonym:
        lines.append(f"Синоним: {obj.synonym}")
    if obj.code_length:
        lines.append(f"Длина кода: {obj.code_length}")

    if obj.attributes:
        lines.append(f"\n## Субконто ({len(obj.attributes)})")
        for a in obj.attributes:
            ref = _format_ref(a)
            lines.append(f"  - {a.name}: {a.type}({a.length}.{a.precision}){ref}")
            if a.comment:
                lines.append(f"    {a.comment}")

    if obj.forms:
        lines.append(f"\n## Формы ({len(obj.forms)})")
        for f in obj.forms:
            lines.append(f"  - {f.name} (id={f.id})")

    return "\n".join(lines)


def _matches(obj, query_lower: str) -> bool:
    """Check if object matches search query."""
    name = getattr(obj, "name", "").lower()
    synonym = getattr(obj, "synonym", "").lower()
    comment = getattr(obj, "comment", "").lower()
    return query_lower in name or query_lower in synonym or query_lower in comment


def _find_lines_in_text(
    text: str,
    query_lower: str,
    max_results: int = 200,
    context_lines: int = 0,
) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """Find lines in text containing the query (case-insensitive).

    Returns list of (match_line_num, match_line, context_block) tuples.
    context_block contains [(line_num, line_text), ...] including the match
    line and surrounding lines when context_lines > 0.
    When context_lines == 0, context_block is empty (backward-compat).
    """
    all_lines = text.splitlines()
    total = len(all_lines)
    results: list[tuple[int, str, list[tuple[int, str]]]] = []

    for i, line in enumerate(all_lines):
        if query_lower in line.lower():
            stripped = line.strip()
            if context_lines > 0:
                ctx_start = max(0, i - context_lines)
                ctx_end = min(total, i + context_lines + 1)
                ctx_block = [
                    (j + 1, all_lines[j].rstrip()) for j in range(ctx_start, ctx_end)
                ]
            else:
                ctx_block = []
            results.append((i + 1, stripped, ctx_block))
            if len(results) >= max_results:
                break
    return results


# --- External processing (.ert) tools ---


def init_ert_dirs(dirs: list[str]) -> None:
    """Configure directories scanned for external processing (.ert) files. Called at startup."""
    _ert_loader.set_dirs(dirs)


def get_ert_loader() -> ErtLoader:
    """Get the global ErtLoader instance."""
    return _ert_loader


def list_ert_files() -> str:
    """List all discovered external processing (*.ert) files."""
    entries = _ert_loader.list_files()
    if not entries:
        return "Внешние обработки (*.ert) не найдены."
    lines = [f"Найдено внешних обработок: {len(entries)}", ""]
    for e in entries:
        lines.append(f"  - {e.name}  ({e.path})")
    return "\n".join(lines)


def find_ert_file(name: str) -> str:
    """Find an external processing file by name."""
    entry = _ert_loader.find(name)
    if entry is None:
        candidates = [e.name for e in _ert_loader.list_files()]
        similar = _find_similar(name, candidates)
        msg = f"Внешняя обработка '{name}' не найдена."
        if similar:
            msg += f" Похожие: {', '.join(similar)}"
        return msg
    return f"Найдена: {entry.name}\nПуть: {entry.path}"


def list_ert_procedures(name: str) -> str:
    """List all procedures and functions declared in an external processing module."""
    structure = _ert_loader.get_module_structure(name)
    if structure is None:
        return f"Обработка '{name}' не найдена или не содержит модуля."
    if not structure.procedures:
        return f"В обработке '{name}' процедуры и функции не найдены."

    lines = [f"# Обработка.{name}: процедуры и функции ({len(structure.procedures)})", ""]
    for p in structure.procedures:
        params = ", ".join(p.params)
        exp = " Экспорт" if p.exported else ""
        lines.append(f"  - {p.kind} {p.name}({params}){exp}  [строки {p.start_line}-{p.end_line}]")
    return "\n".join(lines)


def get_ert_procedure_source(name: str, proc_name: str) -> str:
    """Get the source text of a specific procedure/function of an external processing module."""
    structure = _ert_loader.get_module_structure(name)
    if structure is None:
        return f"Обработка '{name}' не найдена или не содержит модуля."
    match = _find_procedure(structure, proc_name)
    if match is None:
        return f"Процедура/функция '{proc_name}' не найдена в обработке '{name}'."
    text = _ert_loader.get_module(name)
    return _slice_module(text, match.start_line, match.end_line, f"Обработка.{name}.{proc_name}")


def get_ert_module(name: str, start_line: int = 0, end_line: int = 0) -> str:
    """Get the module source code of an external processing file."""
    text = _ert_loader.get_module(name)
    if text is None:
        return f"Обработка '{name}' не найдена или не содержит модуля."
    return _slice_module(text, start_line, end_line, f"Обработка.{name}")


def search_in_ert_modules(query: str, context_lines: int = 0, limit: int = 200) -> str:
    """Search for text across all external processing (.ert) module source code."""
    query_lower = query.lower()
    output_lines: list[str] = []
    total_matches = 0

    for label, text in _ert_loader.iter_module_entries():
        remaining = limit - total_matches
        if remaining <= 0:
            break
        matches = _find_lines_in_text(text, query_lower, max_results=remaining, context_lines=context_lines)
        for line_num, line_text, ctx_block in matches:
            if context_lines > 0 and ctx_block:
                for cn, cl in ctx_block:
                    prefix = "  " if cn != line_num else ""
                    output_lines.append(f"{label}:{cn}:{prefix}{cl}")
                output_lines.append("--")
            else:
                output_lines.append(f"{label}:{line_num}: {line_text}")
        total_matches += len(matches)

    if not output_lines:
        return f"По запросу '{query}' во внешних обработках ничего не найдено."

    lines = [f"Найдено {total_matches} совпадений во внешних обработках по запросу '{query}':", ""]
    lines.extend(output_lines)
    return "\n".join(lines)


def get_ert_form(name: str) -> str:
    """Get the form (Dialog Stream) definition of an external processing file."""
    form = _ert_loader.get_dialog(name)
    if form is None:
        return f"Форма обработки '{name}' не найдена."
    return form


def reload_ert_files() -> str:
    """Rescan configured directories for external processing (*.ert) files."""
    entries = _ert_loader.rescan()
    return f"Пересканировано. Найдено внешних обработок: {len(entries)}"


def list_ert_dialog_controls(name: str) -> str:
    """List the parsed controls of an external processing's form (dialog)."""
    text = _ert_loader.get_dialog(name)
    if text is None:
        return f"Форма обработки '{name}' не найдена."
    dialog = parse_dialog(text)
    lines = [
        f"# Обработка.{name}: форма \"{dialog.frame.caption.strip()}\" "
        f"({dialog.frame.width}x{dialog.frame.height}), элементов: {len(dialog.controls)}",
        "",
    ]
    if not dialog.controls:
        lines.append("  (элементов управления нет)")
    for c in dialog.controls:
        parts = [f"id={c.id}", c.control_class]
        if c.caption:
            parts.append(f'"{c.caption}"')
        parts.append(f"[{c.x},{c.y},{c.width},{c.height}]")
        if c.bound_attribute:
            type_name = TYPE_CODES.get(c.type_code, c.type_code)
            parts.append(f"-> {c.bound_attribute} ({type_name})")
        if c.action:
            parts.append(f"действие: {c.action}")
        lines.append("  - " + "  ".join(parts))
    return "\n".join(lines)


def get_ert_print_form(name: str) -> str:
    """Show the parsed print form (Page.1/MOXCEL table) of an external processing."""
    entry = _ert_loader.find(name)
    if entry is None:
        return f"Обработка '{name}' не найдена."
    try:
        sheet = ert_writer.get_print_form(Path(entry.path))
    except FileNotFoundError:
        return f"Печатная форма обработки '{name}' не найдена."
    except Exception as e:
        return f"Не удалось разобрать печатную форму обработки '{name}': {e}"

    if sheet.n_rows == 0 and sheet.n_columns == 0 and not sheet.rows:
        return f"Обработка '{name}' не использует печатную форму (таблицу)."

    lines = [
        f"# Обработка.{name}: печатная форма ({sheet.n_columns} кол. x {sheet.n_rows} стр., "
        f"версия MOXCEL {sheet.version})",
        "",
    ]
    if sheet.objects:
        lines.append(
            f"(в форме также {len(sheet.objects)} встроенных объектов — линии/картинки/OLE, "
            f"не показаны, разбор только текстовых ячеек)"
        )
        lines.append("")
    any_cell = False
    for row_idx in sorted(sheet.rows):
        row = sheet.rows[row_idx]
        cells = [
            f"{col_idx}={cell.text if cell.text is not None else cell.value}"
            for col_idx, cell in sorted(row.cells.items())
            if cell.text or cell.value
        ]
        if cells:
            any_cell = True
            lines.append(f"  строка {row_idx}: " + "; ".join(cells))
    if not any_cell:
        lines.append("  (текстовых ячеек нет)")
    return "\n".join(lines)


# --- External processing (.ert) write tools (edit-path only) ---


_EDIT_DISABLED_MSG = (
    "Редактирование обработок отключено: сервер запущен без --edit-path. "
    "Перезапустите сервер с параметром --edit-path <каталог> для включения "
    "инструментов создания/редактирования .ert."
)


def init_edit_path(path: str) -> None:
    """Configure the writable directory for .ert creation/editing. Called at startup."""
    global _edit_path
    _edit_path = Path(path).resolve()


def edit_path_enabled() -> bool:
    return _edit_path is not None


def _edit_target_error(name: str) -> str | None:
    """Return an error message if `name` cannot be used as an edit-path write target."""
    if _edit_path is None:
        return _EDIT_DISABLED_MSG
    try:
        ert_writer._validate_name(name)
    except ert_writer.ErtNameError as e:
        return str(e)
    return None


def create_ert_file(
    name: str,
    module_text: str = "",
    caption: str = "",
    print_form_rows: list[list[str]] | None = None,
) -> str:
    """Create a new external processing (.ert) in the --edit-path directory."""
    if err := _edit_target_error(name):
        return err
    dialog = default_dialog(caption) if caption else default_dialog()
    try:
        path = ert_writer.create_ert_file(_edit_path, name, module_text, dialog, print_form_rows)
    except (ert_writer.ErtNameError, FileExistsError) as e:
        return str(e)
    _ert_loader.rescan()
    return f"Создана обработка '{name}': {path}"


def _require_edit_target(name: str) -> str | None:
    """Like _edit_target_error, but also requires the file to already exist
    inside edit-path (for update tools), giving a specific error otherwise."""
    if err := _edit_target_error(name):
        return err
    target = _edit_path / f"{name}.ert"
    if not target.exists():
        existing = _ert_loader.find(name)
        if existing is not None:
            return (
                f"Обработка '{name}' найдена по пути {existing.path}, но это не "
                f"каталог --edit-path ({_edit_path}) — редактирование недоступно "
                f"для файлов вне каталога редактирования."
            )
        return f"Обработка '{name}' не найдена в каталоге редактирования ({_edit_path})."
    return None


def update_ert_module(name: str, new_text: str) -> str:
    """Replace the module (BSL) source of an existing edit-path .ert."""
    if err := _require_edit_target(name):
        return err
    ert_writer.update_ert_module(_edit_path, name, new_text)
    _ert_loader.rescan()
    return f"Модуль обработки '{name}' обновлён."


def set_ert_dialog_frame(
    name: str, caption: str | None = None, width: int | None = None, height: int | None = None
) -> str:
    """Update the window title/size of an existing edit-path .ert's dialog."""
    if err := _require_edit_target(name):
        return err
    dialog = ert_writer.get_editable_dialog(_edit_path, name)
    if caption is not None:
        dialog.frame.caption = caption
    if width is not None:
        dialog.frame.width = width
    if height is not None:
        dialog.frame.height = height
    ert_writer.update_ert_dialog(_edit_path, name, dialog)
    _ert_loader.rescan()
    return f"Форма обработки '{name}' обновлена."


def add_ert_dialog_control(
    name: str,
    caption: str,
    control_class: str,
    x: int,
    y: int,
    width: int,
    height: int,
    action: str = "",
    bound_attribute: str = "",
    type_code: str = "",
    tab_group_name: str = "Основной",
) -> str:
    """Add a new control to an existing edit-path .ert's dialog (form)."""
    if err := _require_edit_target(name):
        return err
    dialog = ert_writer.get_editable_dialog(_edit_path, name)
    control = DialogControl(
        id=dialog.next_control_id(),
        caption=caption,
        control_class=control_class,
        x=x, y=y, width=width, height=height,
        action=action,
        bound_attribute=bound_attribute,
        type_code=type_code,
        tab_group_name=tab_group_name,
    )
    dialog.controls.append(control)
    ert_writer.update_ert_dialog(_edit_path, name, dialog)
    _ert_loader.rescan()
    return f"Элемент управления id={control.id} добавлен в форму обработки '{name}'."


def update_ert_dialog_control(
    name: str,
    control_id: int,
    caption: str | None = None,
    control_class: str | None = None,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    action: str | None = None,
    bound_attribute: str | None = None,
    type_code: str | None = None,
    tab_group_name: str | None = None,
) -> str:
    """Update fields of an existing control on an edit-path .ert's dialog."""
    if err := _require_edit_target(name):
        return err
    dialog = ert_writer.get_editable_dialog(_edit_path, name)
    control = dialog.find_control(control_id)
    if control is None:
        return f"Элемент управления id={control_id} не найден в форме обработки '{name}'."
    if caption is not None:
        control.caption = caption
    if control_class is not None:
        control.control_class = control_class
    if x is not None:
        control.x = x
    if y is not None:
        control.y = y
    if width is not None:
        control.width = width
    if height is not None:
        control.height = height
    if action is not None:
        control.action = action
    if bound_attribute is not None:
        control.bound_attribute = bound_attribute
    if type_code is not None:
        control.type_code = type_code
    if tab_group_name is not None:
        control.tab_group_name = tab_group_name
    ert_writer.update_ert_dialog(_edit_path, name, dialog)
    _ert_loader.rescan()
    return f"Элемент управления id={control_id} формы обработки '{name}' обновлён."


def update_ert_print_form(name: str, rows: list[list[str]]) -> str:
    """Replace the print form (Page.1/MOXCEL table) of an existing edit-path .ert
    with a simple grid of cell text (no formatting/objects)."""
    if err := _require_edit_target(name):
        return err
    ert_writer.update_ert_print_form(_edit_path, name, rows)
    _ert_loader.rescan()
    return f"Печатная форма обработки '{name}' обновлена ({len(rows)} строк)."


def remove_ert_dialog_control(name: str, control_id: int) -> str:
    """Remove a control from an existing edit-path .ert's dialog."""
    if err := _require_edit_target(name):
        return err
    dialog = ert_writer.get_editable_dialog(_edit_path, name)
    control = dialog.find_control(control_id)
    if control is None:
        return f"Элемент управления id={control_id} не найден в форме обработки '{name}'."
    dialog.controls.remove(control)
    ert_writer.update_ert_dialog(_edit_path, name, dialog)
    _ert_loader.rescan()
    return f"Элемент управления id={control_id} удалён из формы обработки '{name}'."
