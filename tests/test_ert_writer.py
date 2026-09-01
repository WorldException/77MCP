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


def test_create_ert_file_with_description(tmp_path):
    path = ert_writer.create_ert_file(
        tmp_path, "Described", description="Обработка выгружает остатки на склад."
    )
    assert ert_writer.get_description(path) == "Обработка выгружает остатки на склад."


def test_create_ert_file_default_description_is_empty(tmp_path):
    path = ert_writer.create_ert_file(tmp_path, "NoDescription")
    assert ert_writer.get_description(path) == ""


def test_update_ert_description_preserves_other_streams(tmp_path):
    path = ert_writer.create_ert_file(
        tmp_path, "DescriptionEdit", module_text="Процедура X()\nКонецПроцедуры"
    )
    before = ert_writer.load_editable_streams(path)

    ert_writer.update_ert_description(tmp_path, "DescriptionEdit", "Справка по обработке.")
    after = ert_writer.load_editable_streams(path)

    for name in before:
        if name == "Inplace description":
            assert before[name] != after[name]
        else:
            assert before[name] == after[name], name

    assert ert_writer.get_description(path) == "Справка по обработке."


def test_create_ert_module_stream_uses_crlf_on_disk(tmp_path):
    # Regression: every real 1C 7.7 sample stores MD Programm text with
    # \r\n; LF-only text (the normal output of any text tool) crashed the
    # Configurator with no error message the moment the module tab opened.
    path = ert_writer.create_ert_file(
        tmp_path, "CrlfProc", module_text="Процедура X()\nY = 1;\nКонецПроцедуры"
    )
    ole = ole_reader.open_md_file(path)
    try:
        streams = ole_reader.get_root_object_streams(ole)
        module = ole_reader.read_module_text(ole, streams["module"])
    finally:
        ole.close()
    assert "\r\n" in module
    assert "\r\r\n" not in module
    assert module.replace("\r\n", "\n") == "Процедура X()\nY = 1;\nКонецПроцедуры"


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


def test_patch_ert_module_applies_edits_in_order(tmp_path):
    ert_writer.create_ert_file(
        tmp_path, "Patchable", module_text="Процедура X()\n\tA = 1;\nКонецПроцедуры"
    )
    text = ert_writer.patch_ert_module(
        tmp_path,
        "Patchable",
        [("A = 1;", "A = 2;", False), ("Процедура X()", "Процедура Y()", False)],
    )
    assert text == "Процедура Y()\n\tA = 2;\nКонецПроцедуры"
    assert ert_writer.load_editable_streams(tmp_path / "Patchable.ert")


def test_patch_ert_module_rejects_missing_old_string(tmp_path):
    ert_writer.create_ert_file(tmp_path, "PatchMiss", module_text="A = 1;")
    with pytest.raises(ert_writer.ErtPatchError):
        ert_writer.patch_ert_module(tmp_path, "PatchMiss", [("B = 1;", "B = 2;", False)])


def test_patch_ert_module_rejects_ambiguous_old_string(tmp_path):
    ert_writer.create_ert_file(tmp_path, "PatchAmbig", module_text="A = 1;\nA = 1;")
    with pytest.raises(ert_writer.ErtPatchError):
        ert_writer.patch_ert_module(tmp_path, "PatchAmbig", [("A = 1;", "A = 2;", False)])


def test_patch_ert_module_replace_all(tmp_path):
    ert_writer.create_ert_file(tmp_path, "PatchAll", module_text="A = 1;\nA = 1;")
    text = ert_writer.patch_ert_module(tmp_path, "PatchAll", [("A = 1;", "A = 2;", True)])
    assert text == "A = 2;\nA = 2;"


def test_patch_ert_module_leaves_file_untouched_on_failure(tmp_path):
    path = ert_writer.create_ert_file(tmp_path, "PatchAtomic", module_text="A = 1;")
    before = ert_writer.load_editable_streams(path)
    with pytest.raises(ert_writer.ErtPatchError):
        ert_writer.patch_ert_module(
            tmp_path, "PatchAtomic", [("A = 1;", "A = 2;", False), ("nope", "x", False)]
        )
    after = ert_writer.load_editable_streams(path)
    assert before == after


def test_append_ert_module_text_adds_newline_separator(tmp_path):
    ert_writer.create_ert_file(tmp_path, "Append", module_text="Процедура X()\nКонецПроцедуры")
    text = ert_writer.append_ert_module_text(
        tmp_path, "Append", "Процедура Y()\nКонецПроцедуры"
    )
    assert text == "Процедура X()\nКонецПроцедуры\nПроцедура Y()\nКонецПроцедуры"


def test_append_ert_module_text_no_double_newline(tmp_path):
    ert_writer.create_ert_file(tmp_path, "AppendNL", module_text="A\n")
    text = ert_writer.append_ert_module_text(tmp_path, "AppendNL", "B")
    assert text == "A\nB"


def test_append_ert_module_text_empty_module(tmp_path):
    ert_writer.create_ert_file(tmp_path, "AppendEmpty", module_text="")
    text = ert_writer.append_ert_module_text(tmp_path, "AppendEmpty", "A")
    assert text == "A"


def test_append_ert_module_text_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ert_writer.append_ert_module_text(tmp_path, "DoesNotExist", "text")


def test_replace_ert_module_lines(tmp_path):
    ert_writer.create_ert_file(
        tmp_path, "Lines", module_text="line1\nline2\nline3\nline4"
    )
    text = ert_writer.replace_ert_module_lines(
        tmp_path, "Lines", 2, 3, "newline2\nnewline3"
    )
    assert text == "line1\nnewline2\nnewline3\nline4"


def test_replace_ert_module_lines_out_of_range_raises(tmp_path):
    ert_writer.create_ert_file(tmp_path, "LinesBad", module_text="line1\nline2")
    with pytest.raises(ert_writer.ErtPatchError):
        ert_writer.replace_ert_module_lines(tmp_path, "LinesBad", 1, 5, "x")


def test_create_ert_with_print_form_rows(tmp_path):
    path = ert_writer.create_ert_file(
        tmp_path, "WithReport",
        print_form_rows=[["Наименование", "Кол-во"], ["Товар1", "5"]],
    )
    sheet = ert_writer.get_print_form(path)
    assert sheet.n_columns == 2
    assert sheet.n_rows == 2
    assert sheet.cell_text(0, 0) == "Наименование"
    assert sheet.cell_text(1, 1) == "5"


def test_update_ert_print_form_preserves_other_streams(tmp_path):
    path = ert_writer.create_ert_file(tmp_path, "ReportEdit")
    before = ert_writer.load_editable_streams(path)

    ert_writer.update_ert_print_form(tmp_path, "ReportEdit", [["a", "b"]])
    after = ert_writer.load_editable_streams(path)

    for name in before:
        if name == "Page.1":
            assert before[name] != after[name]
        else:
            assert before[name] == after[name], name

    sheet = ert_writer.get_print_form(path)
    assert sheet.cell_text(0, 0) == "a"
    assert sheet.cell_text(0, 1) == "b"


def test_update_ert_print_form_sheet_preserves_cells_and_other_streams(tmp_path):
    from mcp_1c77.moxel_model import MoxelSection

    path = ert_writer.create_ert_file(
        tmp_path, "SectionsEdit",
        print_form_rows=[["Наименование", "Кол-во"], ["Товар1", "5"]],
    )
    before = ert_writer.load_editable_streams(path)

    sheet = ert_writer.get_editable_print_form(tmp_path, "SectionsEdit")
    sheet.horizontal_sections.append(MoxelSection(begin=0, end=0, level=0, name="Шапка"))
    ert_writer.update_ert_print_form_sheet(tmp_path, "SectionsEdit", sheet)

    after = ert_writer.load_editable_streams(path)
    for name in before:
        if name == "Page.1":
            assert before[name] != after[name]
        else:
            assert before[name] == after[name], name

    reloaded = ert_writer.get_print_form(path)
    assert reloaded.cell_text(0, 0) == "Наименование"
    assert reloaded.cell_text(1, 1) == "5"
    assert reloaded.horizontal_sections == [MoxelSection(begin=0, end=0, level=0, name="Шапка")]
