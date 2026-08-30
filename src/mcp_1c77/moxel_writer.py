"""Serializer for the MOXCEL binary spreadsheet format (`Page.1`).

Writes the subset of MOXCEL this project can safely construct: a grid of
text/value cells with optional column widths and row heights, no embedded
objects/pictures/OLE (see moxel_model.py for why those are read-only) and
no fonts beyond the implicit default (cells reference font 0, which is not
required to exist in `fonts` — 1C falls back to a system default when a
referenced font id is missing, same as an unset FontName flag).

Round-trips through moxel_reader.parse_moxel (see tests/test_moxel.py) but,
like ole_writer.py, has not been validated against real 1C 7.7 — see
docs/external-ert.md.
"""

from __future__ import annotations

import dataclasses
import struct

from .moxel_model import (
    CELL_FORMAT_SIZE,
    FLAG_COLUMN_WIDTH,
    FLAG_DATA,
    FLAG_ROW_HEIGHT,
    FLAG_TEXT,
    FLAG_VALUE,
    LOGFONT_SIZE,
    MAGIC,
    CellFormat,
    CellsUnion,
    DataCell,
    Font,
    MoxelArea,
    MoxelRow,
    MoxelSection,
    MoxelSheet,
)

_HEADER_PREFIX = MAGIC + b"\x00" * 5  # bytes 0..10, matches every real sample
_TRAILER = b"\x00\x00"  # fixed 2-byte trailer observed in every real sample


class MoxelWriteError(ValueError):
    pass


def _cstring(text: str) -> bytes:
    body = text.encode("cp1251", errors="replace")
    n = len(body)
    if n < 0xFF:
        return bytes([n]) + body
    if n < 0xFFFF:
        return b"\xff" + struct.pack("<H", n) + body
    return b"\xff\xff\xff" + struct.pack("<I", n) + body


def _count(n: int) -> bytes:
    if n <= 65534:
        return struct.pack("<H", n)
    return struct.pack("<H", 0xFFFF) + struct.pack("<i", n)


def _int_array(values: list[int]) -> bytes:
    return _count(len(values)) + b"".join(struct.pack("<i", v) for v in values)


def _cell_format(fmt: CellFormat) -> bytes:
    buf = bytearray(CELL_FORMAT_SIZE)
    struct.pack_into("<I", buf, 0, fmt.flags & 0xFFFFFFFF)
    struct.pack_into("<hh", buf, 4, fmt.w1, fmt.w2)
    struct.pack_into("<hh", buf, 8, fmt.font_number, fmt.font_size)
    buf[12] = fmt.font_bold & 0xFF
    buf[13] = 1 if fmt.font_italic else 0
    buf[14] = 1 if fmt.font_underline else 0
    buf[15] = fmt.align_h & 0xFF
    buf[16] = fmt.align_v & 0xFF
    buf[17] = fmt.pattern_type & 0xFF
    buf[18] = fmt.border_left & 0xFF
    buf[19] = fmt.border_top & 0xFF
    buf[20] = fmt.border_right & 0xFF
    buf[21] = fmt.border_bottom & 0xFF
    buf[22] = fmt.pattern_color & 0xFF
    buf[23] = fmt.border_color & 0xFF
    buf[24] = fmt.font_color & 0xFF
    buf[25] = fmt.background & 0xFF
    buf[26] = fmt.control_content & 0xFF
    buf[27] = fmt.content_type & 0xFF
    buf[28] = 1 if fmt.allow_edit else 0
    buf[29] = fmt.reserved & 0xFF
    return bytes(buf)


def _data_cell(cell: DataCell, version: int) -> bytes:
    flags = cell.format.flags
    if cell.text is not None:
        flags |= FLAG_TEXT
    if cell.value is not None:
        flags |= FLAG_VALUE
    if cell.data is not None:
        flags |= FLAG_DATA
    fmt = dataclasses.replace(cell.format, flags=flags) if flags != cell.format.flags else cell.format

    out = bytearray()
    out += _cell_format(fmt)
    if version == 7:
        out += struct.pack("<h", cell.text_orientation)
    if fmt.flags & FLAG_TEXT:
        out += _cstring(cell.text or "")
    if fmt.flags & FLAG_VALUE:
        out += _cstring(cell.value or "")
    if fmt.flags & FLAG_DATA:
        data = cell.data or b""
        out += _count(len(data)) + data
    return bytes(out)


def _font(f: Font) -> bytes:
    buf = bytearray(LOGFONT_SIZE)
    struct.pack_into("<iiiii", buf, 0, f.height, 0, 0, 0, f.weight)
    buf[20] = 1 if f.italic else 0
    buf[21] = 1 if f.underline else 0
    buf[22] = 0  # strikeout
    buf[23] = f.charset & 0xFF
    face = f.face_name.encode("cp1251", errors="replace")[:31]
    buf[28 : 28 + len(face)] = face
    return bytes(buf)


def _dict_of(items: dict[int, object], item_writer) -> bytes:
    keys = list(items.keys())
    out = _int_array(keys)
    out += _count(len(keys))  # redundant length, mirrors the reader's format
    for k in keys:
        out += item_writer(items[k])
    return out


def _list_of(items: list, item_writer) -> bytes:
    out = _count(len(items))
    for item in items:
        out += item_writer(item)
    return out


def _cells_union(u: CellsUnion) -> bytes:
    return struct.pack("<iiii", u.left, u.top, u.right, u.bottom)


def _section(s: MoxelSection) -> bytes:
    return struct.pack("<iii", s.begin, s.end, s.level) + _cstring(s.name)


def _area(a: MoxelArea) -> bytes:
    return _cstring(a.name) + struct.pack(
        "<iiiiiii", 1, 0, a.area_type, a.col_begin, a.row_begin, a.col_end, a.row_end
    )


def write_moxel(sheet: MoxelSheet) -> bytes:
    """Serialize a `MoxelSheet` into raw `Page.1` bytes.

    Refuses (raises MoxelWriteError) if the sheet has embedded objects —
    writing those is not implemented (see module docstring).
    """
    if sheet.objects:
        raise MoxelWriteError(
            "Запись встроенных объектов (картинок/OLE/линий) MOXCEL не поддерживается; "
            "лист может содержать только текстовые ячейки."
        )

    version = sheet.version
    out = bytearray(_HEADER_PREFIX)
    out += struct.pack("<h", version)
    out += struct.pack("<i", sheet.n_columns)
    out += struct.pack("<i", sheet.n_rows)
    out += struct.pack("<i", 0)  # nAllObjectsCount

    out += _data_cell(DataCell(format=sheet.def_format), version)
    out += _dict_of(sheet.fonts, _font)

    str_keys = list(sheet.strings.keys())
    out += _int_array(str_keys)
    out += _count(len(str_keys))
    for k in str_keys:
        out += _cstring(sheet.strings[k])

    out += _data_cell(sheet.header, version)
    out += _data_cell(sheet.footer, version)

    out += _dict_of(sheet.columns, lambda c: _data_cell(c, version))
    out += _dict_of(
        sheet.rows,
        lambda row: _data_cell(DataCell(format=row.format), version)
        + _dict_of(row.cells, lambda c: _data_cell(c, version)),
    )

    out += _count(0)  # objects (always empty, see guard above)

    out += _list_of(sheet.unions, _cells_union)
    out += _list_of(sheet.vertical_sections, _section)
    out += _list_of(sheet.horizontal_sections, _section)
    out += _int_array(sheet.vertical_page_breaks)
    out += _int_array(sheet.horizontal_page_breaks)
    out += _list_of(sheet.areas, _area)

    out += _TRAILER
    return bytes(out)


_DEFAULT_COLUMN_WIDTH = 40
_DEFAULT_ROW_HEIGHT = 45


def simple_table(
    rows: list[list[str]], column_widths: list[int] | None = None
) -> MoxelSheet:
    """Build a MoxelSheet from a plain 2D grid of cell text (no formatting).

    `rows[i][j]` becomes the text of cell (row i, column j); empty strings
    are skipped (no cell is stored, matching how 1C omits blank cells).
    `column_widths[j]`, if given, sets an explicit width for column j.
    """
    n_rows = len(rows)
    n_cols = max((len(r) for r in rows), default=0)

    columns: dict[int, DataCell] = {}
    if column_widths:
        for j, w in enumerate(column_widths):
            if w:
                columns[j] = DataCell(format=CellFormat(flags=FLAG_COLUMN_WIDTH, w2=w))

    sheet_rows: dict[int, MoxelRow] = {}
    for i, row_values in enumerate(rows):
        cells: dict[int, DataCell] = {}
        for j, text in enumerate(row_values):
            if text:
                cells[j] = DataCell(format=CellFormat(flags=FLAG_TEXT), text=text)
        if cells:
            sheet_rows[i] = MoxelRow(format=CellFormat(), cells=cells)

    return MoxelSheet(
        version=6,
        n_columns=n_cols,
        n_rows=n_rows,
        def_format=CellFormat(flags=FLAG_COLUMN_WIDTH, w2=_DEFAULT_COLUMN_WIDTH),
        columns=columns,
        rows=sheet_rows,
    )
