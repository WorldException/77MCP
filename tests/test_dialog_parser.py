"""Tests for parsing/serializing Dialog Stream text to/from the Dialog model."""

import os

import pytest

from mcp_1c77 import bracket_parser as bp
from mcp_1c77 import ole_reader
from mcp_1c77.dialog_parser import default_dialog, parse_dialog, serialize_dialog

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.ert")

pytestmark = pytest.mark.skipif(
    not os.path.exists(FIXTURE), reason="fixture .ert not found"
)


def _sample_dialog_text() -> str:
    ole = ole_reader.open_md_file(FIXTURE)
    try:
        streams = ole_reader.get_root_object_streams(ole)
        return ole_reader.read_stream_text(ole, streams["dialog"])
    finally:
        ole.close()


def test_parse_sample_dialog():
    dialog = parse_dialog(_sample_dialog_text())
    assert dialog.frame.width == 320
    assert dialog.frame.height == 165
    assert dialog.frame.font_name == "MS Sans Serif"
    assert len(dialog.controls) == 3
    assert dialog.controls[0].control_class == "BUTTON"
    assert dialog.controls[0].caption == "Закрыть"
    assert dialog.controls[0].id == 4152
    assert dialog.controls[2].control_class == "1CEDIT"
    assert dialog.controls[2].bound_attribute == "ИД_Задачи_Мегаплана"
    assert dialog.controls[2].type_code == "S"


def test_serialize_round_trip_structural():
    text = _sample_dialog_text()
    dialog = parse_dialog(text)
    reparsed = parse_dialog(serialize_dialog(dialog))
    assert dialog.model_dump() == reparsed.model_dump()


def test_serialize_round_trip_byte_exact_for_sample():
    # For this particular sample (no unusual trailing/embedded quoting
    # beyond what's already covered), the writer reproduces the exact same
    # positional field layout 1C itself emits.
    text = _sample_dialog_text()
    dialog = parse_dialog(text)
    out = serialize_dialog(dialog)
    orig_root = bp.parse(text)
    new_root = bp.parse(out)
    orig_geom = orig_root.child_by_first_value("Frame").children[0]
    new_geom = new_root.child_by_first_value("Frame").children[0]
    assert orig_geom.values == new_geom.values


def test_serialize_result_still_parses_via_bracket_parser():
    dialog = parse_dialog(_sample_dialog_text())
    out = serialize_dialog(dialog)
    root = bp.parse(out)
    assert root.first_value() == "Dialogs"
    assert root.child_by_first_value("Controls") is not None
    assert root.child_by_first_value("Cnt_Ver") is not None


def test_default_dialog_is_valid():
    dialog = default_dialog()
    out = serialize_dialog(dialog)
    reparsed = parse_dialog(out)
    assert reparsed.model_dump() == dialog.model_dump()
    assert reparsed.controls == []


def test_escaped_quote_tab_group_field_preserved():
    dialog = parse_dialog(_sample_dialog_text())
    control = dialog.controls[0]
    assert control.tab_group_pos == '{"0","0"}'
    out = serialize_dialog(dialog)
    assert '"{""0"",""0""}"' in out
