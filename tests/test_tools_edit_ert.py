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
    assert "отключено" in tools.add_ert_dialog_control("X", "Cap", "BUTTON", 0, 0, 10, 10)
    assert "отключено" in tools.update_ert_dialog_control("X", 1)
    assert "отключено" in tools.remove_ert_dialog_control("X", 1)
    assert "отключено" in tools.set_ert_dialog_frame("X")


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
