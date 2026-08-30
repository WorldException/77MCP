"""Parser for the MOXCEL binary spreadsheet format (`Page.1` in .ert files).

See moxel_model.py for format background/sources. Verified against all 311
`Page.1` streams found in work/ExtForms/*.ert: every one parses without
error (see docs/external-ert.md §10 for the verification write-up and the
two small unmodeled trailer regions found during that check).
"""

from __future__ import annotations

import struct

from .moxel_model import (
    CELL_FORMAT_SIZE,
    FLAG_DATA,
    FLAG_TEXT,
    FLAG_VALUE,
    LOGFONT_SIZE,
    MAGIC,
    PICTURE_SIZE,
    CellFormat,
    CellsUnion,
    DataCell,
    Font,
    MoxelArea,
    MoxelObject,
    MoxelRow,
    MoxelSection,
    MoxelSheet,
)

HEADER_OFFSET = 0x0B  # where version:int16 starts, after "MOXCEL" + 5 reserved bytes

_OBJECT_TYPE_PICTURE = 5
_OBJECT_TYPE_OLE = 4


class MoxelParseError(ValueError):
    pass


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def bytes(self, n: int) -> bytes:
        b = self.data[self.pos : self.pos + n]
        if len(b) != n:
            raise MoxelParseError(f"unexpected end of data at offset {self.pos} (wanted {n} bytes)")
        self.pos += n
        return b

    def u8(self) -> int:
        return self.bytes(1)[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.bytes(2))[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.bytes(2))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.bytes(4))[0]

    def cstring(self) -> str:
        length = self.u8()
        if length == 0xFF:
            length = self.u16()
        if length == 0xFFFF:
            length = self.i32()
        return self.bytes(length).decode("cp1251", errors="replace")

    def count(self) -> int:
        c = self.u16()
        if c > 65534:
            c = self.i32()
        return c

    def int_array(self) -> list[int]:
        n = self.count()
        return [self.i32() for _ in range(n)]

    def cell_format(self) -> CellFormat:
        raw = self.bytes(CELL_FORMAT_SIZE)
        (flags,) = struct.unpack_from("<I", raw, 0)
        w1, w2 = struct.unpack_from("<hh", raw, 4)
        font_number, font_size = struct.unpack_from("<hh", raw, 8)
        return CellFormat(
            flags=flags, w1=w1, w2=w2,
            font_number=font_number, font_size=font_size,
            font_bold=raw[12], font_italic=bool(raw[13]), font_underline=bool(raw[14]),
            align_h=raw[15], align_v=raw[16], pattern_type=raw[17],
            border_left=raw[18], border_top=raw[19], border_right=raw[20], border_bottom=raw[21],
            pattern_color=raw[22], border_color=raw[23], font_color=raw[24], background=raw[25],
            control_content=raw[26], content_type=raw[27], allow_edit=bool(raw[28]), reserved=raw[29],
        )

    def data_cell(self, version: int) -> DataCell:
        fmt = self.cell_format()
        text_orientation = self.i16() if version == 7 else 0
        text = self.cstring() if fmt.flags & FLAG_TEXT else None
        value = self.cstring() if fmt.flags & FLAG_VALUE else None
        data = self.bytes(self.count()) if fmt.flags & FLAG_DATA else None
        return DataCell(format=fmt, text_orientation=text_orientation, text=text, value=value, data=data)

    def font(self) -> Font:
        raw = self.bytes(LOGFONT_SIZE)
        height, _width, _esc, _orient, weight = struct.unpack_from("<iiiii", raw, 0)
        italic, underline = bool(raw[20]), bool(raw[21])
        charset = raw[23]
        face = raw[28:60].split(b"\x00", 1)[0].decode("cp1251", errors="replace")
        return Font(height=height, weight=weight, italic=italic, underline=underline,
                    charset=charset, face_name=face)

    def dict_of(self, item_reader):
        keys = self.int_array()
        self.count()  # redundant MFC array length, discarded
        return {k: item_reader() for k in keys}

    def list_of(self, item_reader):
        n = self.count()
        return [item_reader() for _ in range(n)]

    def cells_union(self) -> CellsUnion:
        left, top, right, bottom = struct.unpack("<iiii", self.bytes(16))
        return CellsUnion(left=left, top=top, right=right, bottom=bottom)

    def section(self) -> MoxelSection:
        begin, end, level = self.i32(), self.i32(), self.i32()
        return MoxelSection(begin=begin, end=end, level=level, name=self.cstring())

    def area(self) -> MoxelArea:
        name = self.cstring()
        _u1, _u2, area_type, col_b, row_b, col_e, row_e = struct.unpack("<iiiiiii", self.bytes(28))
        return MoxelArea(name=name, area_type=area_type, col_begin=col_b, row_begin=row_b,
                          col_end=col_e, row_end=row_e)

    def object_(self, version: int) -> MoxelObject:
        cell = self.data_cell(version)
        raw = self.bytes(PICTURE_SIZE)
        (obj_type,) = struct.unpack_from("<i", raw, 0)
        col_s, row_s, off_l, off_t, col_e, row_e, off_r, off_b, z = struct.unpack_from("<iiiiiiiii", raw, 4)
        payload: bytes | None = None
        if obj_type == _OBJECT_TYPE_PICTURE:
            self.bytes(4)  # x:u8, y:u8, z:u16
            payload = self.bytes(self.i32())
        elif obj_type == _OBJECT_TYPE_OLE:
            class_name_flag = self.i16()
            if class_name_flag == -1:
                self.i16()
                self.bytes(self.u16())
            self.bytes(4 + 4 + 4 + 2 + 4)  # dwObjectType,dwItemNumber,dwAspect,wUseMoniker,dwAspect(again)
            payload = self.bytes(self.i32())
        return MoxelObject(
            cell=cell, object_type=obj_type,
            column_start=col_s, row_start=row_s, offset_left=off_l, offset_top=off_t,
            column_end=col_e, row_end=row_e, offset_right=off_r, offset_bottom=off_b,
            z_order=z, payload=payload,
        )


def parse_moxel(data: bytes) -> MoxelSheet:
    """Parse a raw `Page.1` stream into a `MoxelSheet`."""
    if data[:6] != MAGIC:
        raise MoxelParseError(f"not a MOXCEL stream (bad magic: {data[:6]!r})")

    r = _Reader(data)
    r.pos = HEADER_OFFSET
    version = r.i16()
    n_columns = r.i32()
    n_rows = r.i32()
    r.i32()  # nAllObjectsCount — redundant, len(objects) is authoritative after parsing
    def_cell = r.data_cell(version)

    fonts = r.dict_of(r.font)

    strnums = r.int_array()
    r.count()  # redundant, discarded
    strings = {n: r.cstring() for n in strnums}

    header = r.data_cell(version)
    footer = r.data_cell(version)

    columns = r.dict_of(lambda: r.data_cell(version))
    rows = r.dict_of(lambda: MoxelRow(
        format=r.data_cell(version).format,
        cells=r.dict_of(lambda: r.data_cell(version)),
    ))

    n_obj = r.count()
    objects = [r.object_(version) for _ in range(n_obj)]

    unions = r.list_of(r.cells_union)
    vsections = r.list_of(r.section)
    hsections = r.list_of(r.section)
    vbreaks = r.int_array()
    hbreaks = r.int_array()
    areas = r.list_of(r.area)

    return MoxelSheet(
        version=version, n_columns=n_columns, n_rows=n_rows,
        def_format=def_cell.format, fonts=fonts, strings=strings,
        header=header, footer=footer, columns=columns, rows=rows,
        objects=objects, unions=unions,
        vertical_sections=vsections, horizontal_sections=hsections,
        vertical_page_breaks=vbreaks, horizontal_page_breaks=hbreaks,
        areas=areas,
    )
