"""Data model for a 1C 7.7 external processing dialog (form).

Reverse-engineered from `Dialog Stream` in real .ert files (see
docs/external-ert.md). A dialog is a bracket-list tree:

    {"Dialogs",
     {"Frame", {<30 positional fields>, {"0", {<tab name>, <tab order>}}}},
     {"Controls",
      {<43 positional fields per control>},
      ...},
     {"Cnt_Ver", "10001"}}

Only a handful of positional fields have confirmed semantics (geometry,
caption, control class, id, action, bound attribute, type code). All other
positions are constant across every sample this project could inspect, but
that has only been verified for BUTTON/STATIC/1CEDIT/BMASKED/CHECKBOX
controls — to stay safe for control classes not seen in the samples (and to
never corrupt a real hand-authored file when editing it), every unknown
position is captured verbatim into `extra` on parse and replayed unchanged
on serialize; only positions this module explicitly understands are ever
rewritten.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

FRAME_FIELD_COUNT = 30
CONTROL_FIELD_COUNT = 43

# Indices into a control's positional field list with confirmed meaning.
_CONTROL_CAPTION = 0
_CONTROL_CLASS = 1
_CONTROL_STYLE_FLAGS = 2
_CONTROL_X = 3
_CONTROL_Y = 4
_CONTROL_WIDTH = 5
_CONTROL_HEIGHT = 6
_CONTROL_ID = 9
_CONTROL_ACTION = 11
_CONTROL_BOUND_ATTRIBUTE = 12
_CONTROL_TYPE_CODE = 14
_CONTROL_LENGTH = 15
_CONTROL_TAB_GROUP_NAME = 41
_CONTROL_TAB_GROUP_POS = 42

CONTROL_KNOWN_INDICES = {
    _CONTROL_CAPTION,
    _CONTROL_CLASS,
    _CONTROL_STYLE_FLAGS,
    _CONTROL_X,
    _CONTROL_Y,
    _CONTROL_WIDTH,
    _CONTROL_HEIGHT,
    _CONTROL_ID,
    _CONTROL_ACTION,
    _CONTROL_BOUND_ATTRIBUTE,
    _CONTROL_TYPE_CODE,
    _CONTROL_LENGTH,
    _CONTROL_TAB_GROUP_NAME,
    _CONTROL_TAB_GROUP_POS,
}

# Default values for control positions this module doesn't model, observed
# identically across every sampled BUTTON/STATIC/1CEDIT/BMASKED/CHECKBOX
# control — used only when creating a brand-new control from scratch.
DEFAULT_CONTROL_EXTRA: dict[int, str] = {
    7: "0", 8: "0", 10: "", 13: "-1",
    16: "0", 17: "0", 18: "0", 19: "0", 20: "0",
    21: "", 22: "", 23: "", 24: "0",
    25: "-11", 26: "0", 27: "0", 28: "0", 29: "0", 30: "0",
    31: "0", 32: "0", 33: "0", 34: "0", 35: "0", 36: "0", 37: "0",
    38: "MS Sans Serif", 39: "-1", 40: "-1",
}

# Indices into the Frame node's positional field list with confirmed meaning.
_FRAME_FONT_NAME = 13
_FRAME_WIDTH = 14
_FRAME_HEIGHT = 15
_FRAME_CAPTION = 16

FRAME_KNOWN_INDICES = {_FRAME_FONT_NAME, _FRAME_WIDTH, _FRAME_HEIGHT, _FRAME_CAPTION}

# Number of flat fields (out of 30) that precede the nested
# `{"0", {tab_group_name, tab_group_order}}` child — i.e. the child is
# inserted between values[FRAME_TAB_NODE_HEAD_LEN - 1] and
# values[FRAME_TAB_NODE_HEAD_LEN], observed identically in every sampled
# Dialog Stream (28 leading values, then the tab-group child, then the
# remaining 2 trailing values).
FRAME_TAB_NODE_HEAD_LEN = 28

DEFAULT_FRAME_EXTRA: dict[int, str] = {
    0: "-11", 1: "0", 2: "0", 3: "0", 4: "400", 5: "0", 6: "0", 7: "0",
    8: "204", 9: "1", 10: "2", 11: "1", 12: "34",
    17: "", 18: "", 19: "0", 20: "",
    21: "1", 22: "1", 23: "6", 24: "29", 25: "-1", 26: "0", 27: "0",
    28: "1", 29: "1",
}


class DialogControl(BaseModel):
    """One control (button, static text, input field, ...) on a dialog."""

    id: int
    caption: str = ""
    control_class: str
    style_flags: str = "0"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    action: str = ""
    bound_attribute: str = ""
    type_code: str = ""
    length: str = "0"
    tab_group_name: str = "Основной"
    tab_group_pos: str = '{"0","0"}'
    extra: dict[int, str] = Field(default_factory=lambda: dict(DEFAULT_CONTROL_EXTRA))

    def to_values(self) -> list[str]:
        values = [""] * CONTROL_FIELD_COUNT
        for i, v in self.extra.items():
            if 0 <= i < CONTROL_FIELD_COUNT:
                values[i] = v
        values[_CONTROL_CAPTION] = self.caption
        values[_CONTROL_CLASS] = self.control_class
        values[_CONTROL_STYLE_FLAGS] = self.style_flags
        values[_CONTROL_X] = str(self.x)
        values[_CONTROL_Y] = str(self.y)
        values[_CONTROL_WIDTH] = str(self.width)
        values[_CONTROL_HEIGHT] = str(self.height)
        values[_CONTROL_ID] = str(self.id)
        values[_CONTROL_ACTION] = self.action
        values[_CONTROL_BOUND_ATTRIBUTE] = self.bound_attribute
        values[_CONTROL_TYPE_CODE] = self.type_code
        values[_CONTROL_LENGTH] = self.length
        values[_CONTROL_TAB_GROUP_NAME] = self.tab_group_name
        values[_CONTROL_TAB_GROUP_POS] = self.tab_group_pos
        return values

    @classmethod
    def from_values(cls, values: list[str]) -> DialogControl:
        def at(i: int, default: str = "") -> str:
            return values[i] if i < len(values) else default

        extra = {
            i: v
            for i, v in enumerate(values)
            if i not in CONTROL_KNOWN_INDICES
        }
        return cls(
            id=int(at(_CONTROL_ID, "0") or "0"),
            caption=at(_CONTROL_CAPTION),
            control_class=at(_CONTROL_CLASS),
            style_flags=at(_CONTROL_STYLE_FLAGS, "0"),
            x=int(at(_CONTROL_X, "0") or "0"),
            y=int(at(_CONTROL_Y, "0") or "0"),
            width=int(at(_CONTROL_WIDTH, "0") or "0"),
            height=int(at(_CONTROL_HEIGHT, "0") or "0"),
            action=at(_CONTROL_ACTION),
            bound_attribute=at(_CONTROL_BOUND_ATTRIBUTE),
            type_code=at(_CONTROL_TYPE_CODE),
            length=at(_CONTROL_LENGTH, "0"),
            tab_group_name=at(_CONTROL_TAB_GROUP_NAME, "Основной"),
            tab_group_pos=at(_CONTROL_TAB_GROUP_POS, '{"0","0"}'),
            extra=extra,
        )


class DialogFrame(BaseModel):
    """The dialog window itself: geometry, font, caption, tab group."""

    width: int = 320
    height: int = 165
    font_name: str = "MS Sans Serif"
    caption: str = " "
    tab_group_name: str = "Основной"
    tab_group_order: str = "1"
    extra: dict[int, str] = Field(default_factory=lambda: dict(DEFAULT_FRAME_EXTRA))

    def to_values(self) -> list[str]:
        values = [""] * FRAME_FIELD_COUNT
        for i, v in self.extra.items():
            if 0 <= i < FRAME_FIELD_COUNT:
                values[i] = v
        values[_FRAME_FONT_NAME] = self.font_name
        values[_FRAME_WIDTH] = str(self.width)
        values[_FRAME_HEIGHT] = str(self.height)
        values[_FRAME_CAPTION] = self.caption
        return values

    @classmethod
    def from_values(cls, values: list[str]) -> DialogFrame:
        def at(i: int, default: str = "") -> str:
            return values[i] if i < len(values) else default

        extra = {
            i: v
            for i, v in enumerate(values)
            if i not in FRAME_KNOWN_INDICES
        }
        return cls(
            font_name=at(_FRAME_FONT_NAME, "MS Sans Serif"),
            width=int(at(_FRAME_WIDTH, "320") or "320"),
            height=int(at(_FRAME_HEIGHT, "165") or "165"),
            caption=at(_FRAME_CAPTION, " "),
            extra=extra,
        )


class Dialog(BaseModel):
    """A full dialog (form): frame + controls."""

    frame: DialogFrame = Field(default_factory=DialogFrame)
    controls: list[DialogControl] = Field(default_factory=list)
    cnt_ver: str = "10001"

    def next_control_id(self) -> int:
        if not self.controls:
            return 4152
        return max(c.id for c in self.controls) + 1

    def find_control(self, control_id: int) -> DialogControl | None:
        for c in self.controls:
            if c.id == control_id:
                return c
        return None
