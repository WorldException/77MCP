"""Tests for the edit-path-gated .ert write MCP tools (tools.py)."""

import os
import shutil

import pytest

from mcp_1c77 import tools

FIXTURE_SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.ert")


@pytest.fixture(autouse=True)
def reset_edit_path():
    yield
    tools._edit_path = None
    tools.init_ert_dirs([])


def test_write_tools_disabled_without_edit_path():
    assert tools.edit_path_enabled() is False
    assert "отключено" in tools.create_ert_file("X")
    assert "отключено" in tools.update_ert_module("X", "text")
    assert "отключено" in tools.patch_ert_module("X", [{"old_string": "a", "new_string": "b"}])
    assert "отключено" in tools.append_ert_module_text("X", "text")
    assert "отключено" in tools.replace_ert_module_lines("X", 1, 1, "text")
    assert "отключено" in tools.add_ert_dialog_control("X", "Cap", "BUTTON", 0, 0, 10, 10)
    assert "отключено" in tools.update_ert_dialog_control("X", 1)
    assert "отключено" in tools.remove_ert_dialog_control("X", 1)
    assert "отключено" in tools.set_ert_dialog_frame("X")
    assert "отключено" in tools.update_ert_print_form("X", [["a"]])
    assert "отключено" in tools.add_ert_print_form_section("X", "horizontal", "Шапка", 0, 0)
    assert "отключено" in tools.update_ert_print_form_section("X", "horizontal", "Шапка")
    assert "отключено" in tools.remove_ert_print_form_section("X", "horizontal", "Шапка")


def test_full_workflow_via_tools_layer(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])

    result = tools.create_ert_file("Robot1", module_text="Процедура X()\nКонецПроцедуры")
    assert "Создана" in result
    assert (tmp_path / "Robot1.ert").exists()

    result = tools.update_ert_module("Robot1", "Процедура Y()\nКонецПроцедуры")
    assert "обновлён" in result
    assert "Процедура Y()" in tools.get_ert_module("Robot1")

    result = tools.add_ert_dialog_control(
        "Robot1", "Закрыть", "BUTTON", 70, 142, 54, 14, action="#Закрыть"
    )
    assert "добавлен" in result
    listing = tools.list_ert_dialog_controls("Robot1")
    assert "BUTTON" in listing
    assert "Закрыть" in listing

    controls = tools._ert_loader.get_dialog("Robot1")
    from mcp_1c77.dialog_parser import parse_dialog
    control_id = parse_dialog(controls).controls[0].id

    result = tools.update_ert_dialog_control("Robot1", control_id, caption="Отмена")
    assert "обновлён" in result
    assert "Отмена" in tools.list_ert_dialog_controls("Robot1")

    result = tools.set_ert_dialog_frame("Robot1", caption="Мой отчёт", width=400)
    assert "обновлена" in result

    result = tools.remove_ert_dialog_control("Robot1", control_id)
    assert "удалён" in result
    assert "элементов управления нет" in tools.list_ert_dialog_controls("Robot1")


def test_patch_ert_module_workflow(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("PatchMe", module_text="Процедура X()\n\tA = 1;\nКонецПроцедуры")

    result = tools.patch_ert_module(
        "PatchMe",
        [
            {"old_string": "A = 1;", "new_string": "A = 2;"},
            {"old_string": "Процедура X()", "new_string": "Процедура Y()"},
        ],
    )
    assert "обновлён" in result
    module = tools.get_ert_module("PatchMe")
    assert "Процедура Y()" in module
    assert "A = 2;" in module


def test_patch_ert_module_ambiguous_old_string_returns_error(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("PatchAmbig", module_text="A = 1;\nA = 1;")

    result = tools.patch_ert_module("PatchAmbig", [{"old_string": "A = 1;", "new_string": "A = 2;"}])
    assert "встречается" in result


def test_patch_ert_module_replace_all_via_tools(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("PatchAllTools", module_text="A = 1;\nA = 1;")

    result = tools.patch_ert_module(
        "PatchAllTools", [{"old_string": "A = 1;", "new_string": "A = 2;", "replace_all": True}]
    )
    assert "обновлён" in result
    assert tools.get_ert_module("PatchAllTools").count("A = 2;") == 2


def test_patch_ert_module_missing_old_string_returns_error(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("PatchMiss", module_text="A = 1;")

    result = tools.patch_ert_module("PatchMiss", [{"old_string": "nope", "new_string": "x"}])
    assert "не найден" in result


def test_append_ert_module_text_workflow(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("AppendTools", module_text="Процедура X()\nКонецПроцедуры")

    result = tools.append_ert_module_text("AppendTools", "Процедура Y()\nКонецПроцедуры")
    assert "дополнен" in result
    module = tools.get_ert_module("AppendTools")
    assert "Процедура X()" in module
    assert "Процедура Y()" in module


def test_replace_ert_module_lines_workflow(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("LinesTools", module_text="line1\nline2\nline3")

    result = tools.replace_ert_module_lines("LinesTools", 2, 2, "newline2")
    assert "обновлён" in result
    # MD Programm text is always stored with \r\n on disk (matches every
    # real 1C 7.7 sample; see ert_writer._encode_module).
    assert tools.get_ert_module("LinesTools").replace("\r\n", "\n") == "line1\nnewline2\nline3"


def test_replace_ert_module_lines_out_of_range_returns_error(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("LinesBadTools", module_text="line1\nline2")

    result = tools.replace_ert_module_lines("LinesBadTools", 1, 10, "x")
    assert "вне диапазона" in result


def test_print_form_workflow(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])

    tools.create_ert_file("Report1")
    result = tools.get_ert_print_form("Report1")
    assert "не использует печатную форму" in result

    result = tools.update_ert_print_form(
        "Report1", [["Наименование", "Кол-во"], ["Товар1", "5"]]
    )
    assert "обновлена" in result

    result = tools.get_ert_print_form("Report1")
    assert "Наименование" in result
    assert "Товар1" in result


def test_print_form_sections_workflow(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])

    tools.create_ert_file("Report2")
    tools.update_ert_print_form(
        "Report2", [["Наименование", "Кол-во"], ["Товар1", "5"]]
    )

    result = tools.list_ert_print_form_sections("Report2")
    assert "(нет)" in result

    result = tools.add_ert_print_form_section("Report2", "horizontal", "Шапка", 0, 0)
    assert "добавлена" in result
    result = tools.add_ert_print_form_section("Report2", "horizontal", "Строка", 1, 1)
    assert "добавлена" in result
    result = tools.add_ert_print_form_section("Report2", "vertical", "Основная", 0, 1, level=1)
    assert "добавлена" in result

    # duplicate name in the same orientation is refused
    result = tools.add_ert_print_form_section("Report2", "horizontal", "Шапка", 2, 2)
    assert "уже существует" in result

    # invalid orientation is refused
    result = tools.add_ert_print_form_section("Report2", "diagonal", "X", 0, 0)
    assert "Недопустимая ориентация" in result

    listing = tools.list_ert_print_form_sections("Report2")
    assert "Шапка" in listing and "Строка" in listing and "Основная" in listing

    # cell data set earlier must survive the section edits
    form = tools.get_ert_print_form("Report2")
    assert "Наименование" in form
    assert "Товар1" in form

    result = tools.update_ert_print_form_section(
        "Report2", "horizontal", "Шапка", end=1, new_name="Заголовок"
    )
    assert "обновлена" in result
    listing = tools.list_ert_print_form_sections("Report2")
    assert "Заголовок" in listing and "Шапка" not in listing

    result = tools.update_ert_print_form_section("Report2", "horizontal", "Нет такой")
    assert "не найдена" in result

    result = tools.remove_ert_print_form_section("Report2", "vertical", "Основная")
    assert "удалена" in result
    listing = tools.list_ert_print_form_sections("Report2")
    assert "Основная" not in listing

    result = tools.remove_ert_print_form_section("Report2", "vertical", "Основная")
    assert "не найдена" in result


def test_update_ert_print_form_disabled_without_edit_path():
    assert "отключено" in tools.update_ert_print_form("X", [["a"]])


def test_create_ert_refuses_duplicate(tmp_path):
    tools.init_edit_path(str(tmp_path))
    tools.init_ert_dirs([str(tmp_path)])
    tools.create_ert_file("Dup")
    result = tools.create_ert_file("Dup")
    assert "уже существует" in result


def test_write_tools_cannot_target_readonly_ert_dir(tmp_path):
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    shutil.copy(FIXTURE_SAMPLE, readonly_dir / "Existing.ert")

    edit_dir = tmp_path / "editable"
    edit_dir.mkdir()

    tools.init_ert_dirs([str(readonly_dir), str(edit_dir)])
    tools.init_edit_path(str(edit_dir))

    result = tools.update_ert_module("Existing", "новый текст")
    assert "не каталог --edit-path" in result or "не найдена" in result
    assert not (edit_dir / "Existing.ert").exists()
