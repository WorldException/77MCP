"""Data model for the MOXCEL binary spreadsheet format (1C 7.7 `Page.1`).

Reverse-engineered from https://github.com/DmitryDreytser/v7Moxel
(`v7Moxel/Moxel/Moxel/*.cs`, MIT-licensed open-source MOXCEL reader/writer),
and verified by parsing all 311 real `Page.1` streams found in
`work/ExtForms/*.ert` (see docs/external-ert.md §10 for the write-up).

A MOXCEL stream is a printable table template ("печатная форма") — the
grid of cells 1C prints or fills in when a report/processing builds its
output. It is functionally similar to a tiny spreadsheet: rows, columns,
per-cell text/formula, formatting flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAGIC = b"MOXCEL"

# CSheetFormat.dwFlags bits (v7Moxel: Moxel.MoxelCellFlags)
FLAG_FONT_NAME = 0x00000001
FLAG_FONT_SIZE = 0x00000002
FLAG_FONT_WEIGHT = 0x00000004
FLAG_FONT_ITALIC = 0x00000008
FLAG_FONT_UNDERLINE = 0x00000010
FLAG_BORDER_LEFT = 0x00000020
FLAG_BORDER_TOP = 0x00000040
FLAG_BORDER_RIGHT = 0x00000080
FLAG_BORDER_BOTTOM = 0x00000100
FLAG_BORDER_COLOR = 0x00000200
FLAG_ROW_HEIGHT = 0x00000400
FLAG_COLUMN_WIDTH = 0x00000800
FLAG_ALIGN_H = 0x00001000
FLAG_ALIGN_V = 0x00002000
FLAG_FONT_COLOR = 0x00004000
FLAG_BACKGROUND = 0x00008000
FLAG_PATTERN_TYPE = 0x00010000
FLAG_PATTERN_COLOR = 0x00020000
FLAG_CONTROL = 0x00040000
FLAG_TYPE = 0x00080000
FLAG_PROTECT = 0x00100000
FLAG_DATA = 0x00200000
FLAG_TEXT_ORIENTATION = 0x00400000
FLAG_VALUE = 0x40000000
FLAG_TEXT = 0x80000000

# CSheetFormat.bType (ContentType, v7Moxel: Moxel.ContentType) — interpretation
# of DataCell.text when FLAG_TYPE is set. Verified against the real corpus
# (work/ExtForms/*.ert): TEXT cells mostly omit FLAG_TYPE (0 is the implicit
# default); EXPRESSION/PATTERN cells set it consistently. FIXED_PATTERN is
# defined by the format but never observed in any real sample.
CONTENT_TYPE_TEXT = 0  # `text` is a literal string, printed as-is
CONTENT_TYPE_EXPRESSION = 1  # `text` is a 1C expression/attribute name, evaluated at print time
CONTENT_TYPE_PATTERN = 2  # `text` is a literal string with `[Expression]` placeholders
CONTENT_TYPE_FIXED_PATTERN = 3  # like PATTERN, but re-evaluated only once (1C UI: "фиксированный шаблон")

CONTENT_TYPE_NAMES: dict[int, str] = {
    CONTENT_TYPE_TEXT: "text",
    CONTENT_TYPE_EXPRESSION: "expression",
    CONTENT_TYPE_PATTERN: "pattern",
    CONTENT_TYPE_FIXED_PATTERN: "fixed_pattern",
}
CONTENT_TYPE_BY_NAME: dict[str, int] = {v: k for k, v in CONTENT_TYPE_NAMES.items()}

CELL_FORMAT_SIZE = 30  # bytes, CSheetFormat, Pack=1
LOGFONT_SIZE = 60  # bytes, LOGFONT, Pack=1
PICTURE_SIZE = 40  # bytes, Picture, Pack=1

# 1C's fixed 56-color palette (v7Moxel: Moxel.a1CPallete), index -> 0xRRGGBB
PALETTE: list[int] = [
    0x000000, 0xFFFFFF, 0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00, 0xFF00FF, 0x00FFFF,
    0x800000, 0x008000, 0x808000, 0x000080, 0x800080, 0x008080, 0x808080, 0xC0C0C0,
    0x8080FF, 0x802060, 0xFFFFC0, 0xA0E0E0, 0x600080, 0xFF8080, 0x0080C0, 0xC0C0FF,
    0x00CFFF, 0x69FFFF, 0xE0FFED, 0xDD9CB3, 0xB38FEE, 0x2A6FF9, 0x3FB8CD, 0x488436,
    0x958C41, 0x8E5E42, 0xA0627A, 0x624FAC, 0x1D2FBE, 0x286676, 0x004500, 0x453E01,
    0x6A2813, 0x85396A, 0x4A3285, 0xC0DCC0, 0xA6CAF0, 0x800000, 0x008000, 0x000080,
    0x808000, 0x800080, 0x008080, 0x808080, 0xFFFBF0, 0xA0A0A4, 0x313900, 0xD98534,
]


@dataclass
class CellFormat:
    """CSheetFormat: 30-byte per-cell/row/column/header formatting record.

    The `w1` field means row height (Rows), column width (Columns), or
    "show" (Header/Footer) depending on which flag is set and which
    container the format belongs to — same union as 1C's C++ struct.
    `w2` similarly means start-page (Header/Footer) or column/row position
    (rarely used). Only the flags actually set are meaningful; unset fields
    should be treated as 0/ignored.
    """

    flags: int = 0
    w1: int = 0  # wShow / wColumnPosition / wHeight
    w2: int = 0  # wStartPage / wWidth / wRowPosition
    font_number: int = 0
    font_size: int = 0
    font_bold: int = 0  # clFontWeight: 0=none, 4=normal, 7=bold
    font_italic: bool = False
    font_underline: bool = False
    align_h: int = 0
    align_v: int = 0
    pattern_type: int = 0
    border_left: int = 0
    border_top: int = 0
    border_right: int = 0
    border_bottom: int = 0
    pattern_color: int = 0
    border_color: int = 0
    font_color: int = 0
    background: int = 0
    control_content: int = 0
    content_type: int = 0
    allow_edit: bool = False
    reserved: int = 0

    def has(self, flag: int) -> bool:
        return bool(self.flags & flag)


@dataclass
class DataCell:
    """A cell (or column/row/header default) — format plus optional payload."""

    format: CellFormat = field(default_factory=CellFormat)
    text_orientation: int = 0  # only meaningful for MOXCEL version 7
    text: str | None = None  # visible/printed text (FLAG_TEXT)
    value: str | None = None  # underlying expression/value (FLAG_VALUE)
    data: bytes | None = None  # opaque extra data (FLAG_DATA)


@dataclass
class Font:
    """LOGFONT (Win32), as embedded in MOXCEL's font table."""

    height: int = 0
    weight: int = 0
    italic: bool = False
    underline: bool = False
    charset: int = 204  # RUSSIAN_CHARSET
    face_name: str = "Arial"


@dataclass
class MoxelRow:
    format: CellFormat = field(default_factory=CellFormat)
    cells: dict[int, DataCell] = field(default_factory=dict)


@dataclass
class CellsUnion:
    left: int
    top: int
    right: int
    bottom: int


@dataclass
class MoxelSection:
    begin: int
    end: int
    level: int
    name: str


@dataclass
class MoxelArea:
    name: str
    area_type: int
    col_begin: int
    row_begin: int
    col_end: int
    row_end: int


@dataclass
class MoxelObject:
    """An embedded drawing object (line/rectangle/text-block/picture/OLE).

    Only text-blocks (the common case for print form field labels drawn as
    boxes) and simple shapes round-trip losslessly. Picture/OLE payloads
    are captured as opaque bytes for read-only inspection; the writer does
    not support (re)creating them — see docs/external-ert.md.
    """

    cell: DataCell
    object_type: int  # 0=None,1=Line,2=Rectangle,3=Text,4=Ole,5=Picture
    column_start: int
    row_start: int
    offset_left: int
    offset_top: int
    column_end: int
    row_end: int
    offset_right: int
    offset_bottom: int
    z_order: int
    payload: bytes | None = None  # raw bytes for Picture/Ole types, else None


@dataclass
class MoxelSheet:
    """A full parsed/constructable MOXCEL document (`Page.1`)."""

    version: int = 6
    n_columns: int = 0
    n_rows: int = 0
    def_format: CellFormat = field(default_factory=CellFormat)
    fonts: dict[int, Font] = field(default_factory=dict)
    strings: dict[int, str] = field(default_factory=dict)
    header: DataCell = field(default_factory=DataCell)
    footer: DataCell = field(default_factory=DataCell)
    columns: dict[int, DataCell] = field(default_factory=dict)
    rows: dict[int, MoxelRow] = field(default_factory=dict)
    objects: list[MoxelObject] = field(default_factory=list)
    unions: list[CellsUnion] = field(default_factory=list)
    vertical_sections: list[MoxelSection] = field(default_factory=list)
    horizontal_sections: list[MoxelSection] = field(default_factory=list)
    vertical_page_breaks: list[int] = field(default_factory=list)
    horizontal_page_breaks: list[int] = field(default_factory=list)
    areas: list[MoxelArea] = field(default_factory=list)

    def cell_text(self, row: int, col: int) -> str | None:
        r = self.rows.get(row)
        if r is None:
            return None
        c = r.cells.get(col)
        if c is None:
            return None
        return c.text if c.text is not None else c.value
