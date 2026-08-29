"""Tests for building/mutating .ert files (ert_writer.py)."""

import pytest

from mcp_1c77 import ert_writer, ole_reader
from mcp_1c77.dialog_model import DialogControl
from mcp_1c77.dialog_parser import parse_dialog


def test_create_ert_file_then_read_back(tmp_path):
    path = ert_writer.create_ert_file(
        tmp_path, "NewProc", module_text="Процедура X()\nКонецПроцедуры"
    )
    assert path.exists()

    ole = ole_reader.open_md_file(path)
    try:
        streams = ole_reader.get_root_object_streams(ole)
        module = ole_reader.read_module_text(ole, streams["module"])
        assert "Процедура X()" in module
        dialog_text = ole_reader.read_stream_text(ole, streams["dialog"])
        dialog = parse_dialog(dialog_text)
        assert dialog.controls == []
    finally:
        ole.close()


def test_create_ert_refuses_existing(tmp_path):
    ert_writer.create_ert_file(tmp_path, "Dup")
    with pytest.raises(FileExistsError):
        ert_writer.create_ert_file(tmp_path, "Dup")


@pytest.mark.parametrize("bad_name", ["", "a/b", "a\\b", "..", "../evil"])
def test_create_ert_refuses_bad_name(tmp_path, bad_name):
    with pytest.raises(ert_writer.ErtNameError):
        ert_writer.create_ert_file(tmp_path, bad_name)


def test_update_ert_module_preserves_other_streams(tmp_path):
    path = ert_writer.create_ert_file(tmp_path, "Preserve", module_text="A")
    before = ert_writer.load_editable_streams(path)

    ert_writer.update_ert_module(tmp_path, "Preserve", "B")
    after = ert_writer.load_editable_streams(path)

    for name in before:
        if name == "MD Programm text":
            assert before[name] != after[name]
        else:
            assert before[name] == after[name], name


def test_update_ert_dialog_add_update_remove_control(tmp_path):
    ert_writer.create_ert_file(tmp_path, "FormTest")

    dialog = ert_writer.get_editable_dialog(tmp_path, "FormTest")
    control = DialogControl(
        id=dialog.next_control_id(),
        caption="Закрыть",
        control_class="BUTTON",
        x=70, y=142, width=54, height=14,
        action="#Закрыть",
    )
    dialog.controls.append(control)
    ert_writer.update_ert_dialog(tmp_path, "FormTest", dialog)

    dialog2 = ert_writer.get_editable_dialog(tmp_path, "FormTest")
    assert len(dialog2.controls) == 1
    assert dialog2.controls[0].caption == "Закрыть"

    dialog2.controls[0].caption = "Отмена"
    ert_writer.update_ert_dialog(tmp_path, "FormTest", dialog2)
    dialog3 = ert_writer.get_editable_dialog(tmp_path, "FormTest")
    assert dialog3.controls[0].caption == "Отмена"

    dialog3.controls.clear()
    ert_writer.update_ert_dialog(tmp_path, "FormTest", dialog3)
    dialog4 = ert_writer.get_editable_dialog(tmp_path, "FormTest")
    assert dialog4.controls == []


def test_update_ert_module_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ert_writer.update_ert_module(tmp_path, "DoesNotExist", "text")
