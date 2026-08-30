"""Parse/serialize a `Dialog Stream` (1C 7.7 dialog/form) to and from `Dialog`.

Uses `bracket_parser` for the underlying `{...}` grammar. See dialog_model.py
for field-level documentation and the `extra`-field passthrough that keeps
edits of a real, hand-authored dialog lossless for fields this module
doesn't understand.
"""

from __future__ import annotations

from . import bracket_parser as bp
from .dialog_model import (
    CONTROL_FIELD_COUNT,
    FRAME_TAB_NODE_HEAD_LEN,
    Dialog,
    DialogControl,
    DialogFrame,
)


def parse_dialog(text: str) -> Dialog:
    """Parse raw `Dialog Stream` bracket text into a `Dialog` model."""
    root = bp.parse(text)

    frame_wrapper = root.child_by_first_value("Frame")
    if frame_wrapper is None or not frame_wrapper.children:
        raise ValueError("Dialog Stream: 'Frame' node not found")
    geom = frame_wrapper.children[0]

    tab_group_name = "Основной"
    tab_group_order = "1"
    if geom.children:
        tab_node = geom.children[0]
        if tab_node.children:
            inner = tab_node.children[0]
            tab_group_name = inner.value_at(0, "Основной")
            tab_group_order = inner.value_at(1, "1")

    frame = DialogFrame.from_values(geom.values)
    frame.tab_group_name = tab_group_name
    frame.tab_group_order = tab_group_order

    controls: list[DialogControl] = []
    controls_wrapper = root.child_by_first_value("Controls")
    if controls_wrapper is not None:
        for child in controls_wrapper.children:
            controls.append(DialogControl.from_values(child.values))

    cnt_ver_wrapper = root.child_by_first_value("Cnt_Ver")
    cnt_ver = cnt_ver_wrapper.value_at(1, "10001") if cnt_ver_wrapper else "10001"

    return Dialog(frame=frame, controls=controls, cnt_ver=cnt_ver)


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _serialize_frame(frame: DialogFrame) -> str:
    values = frame.to_values()
    head = values[:FRAME_TAB_NODE_HEAD_LEN]
    tail = values[FRAME_TAB_NODE_HEAD_LEN:]
    head_text = ",".join(_quote(v) for v in head)
    tail_text = ",".join(_quote(v) for v in tail)
    tab_node = (
        f'{{"0",\r\n'
        f"{{{_quote(frame.tab_group_name)},{_quote(frame.tab_group_order)}}}}}"
    )
    parts = [head_text, tab_node]
    if tail_text:
        parts.append(tail_text)
    return "{\"Frame\",\r\n{" + ",".join(parts) + "}}"


def _serialize_control(control: DialogControl) -> str:
    values = control.to_values()
    assert len(values) == CONTROL_FIELD_COUNT
    return "{" + ",".join(_quote(v) for v in values) + "}"


def serialize_dialog(dialog: Dialog) -> str:
    """Serialize a `Dialog` model back into `Dialog Stream` bracket text."""
    frame_text = _serialize_frame(dialog.frame)
    controls_text = ",\r\n".join(_serialize_control(c) for c in dialog.controls)
    controls_block = '{"Controls",\r\n' + controls_text + "}" if dialog.controls else '{"Controls"}'
    cnt_ver_block = f'{{"Cnt_Ver","{dialog.cnt_ver}"}}'
    return (
        '{"Dialogs",\r\n'
        + frame_text
        + ",\r\n"
        + controls_block
        + ",\r\n"
        + cnt_ver_block
        + "}"
    )


def default_dialog(caption: str = " ") -> Dialog:
    """Build a minimal valid empty dialog for a brand-new external processing."""
    frame = DialogFrame(caption=caption)
    return Dialog(frame=frame, controls=[])
