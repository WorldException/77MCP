"""Tests for the MOXCEL (Page.1 print form) reader/writer."""

import os

import pytest

from mcp_1c77 import ole_reader
from mcp_1c77.moxel_model import CellFormat, FLAG_COLUMN_WIDTH, MoxelSheet
from mcp_1c77.moxel_reader import parse_moxel
from mcp_1c77.moxel_writer import MoxelWriteError, simple_table, write_moxel

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.ert")

pytestmark = pytest.mark.skipif(
    not os.path.exists(FIXTURE), reason="fixture .ert not found"
)


def _sample_page1() -> bytes:
    ole = ole_reader.open_md_file(FIXTURE)
    try:
        return ole_reader.read_stream_raw(ole, "Page.1")
    finally:
        ole.close()


def test_parse_sample_page1():
    sheet = parse_moxel(_sample_page1())
    assert sheet.version == 6
    assert sheet.n_columns == 0
    assert sheet.n_rows == 0
    assert sheet.rows == {}
    assert sheet.objects == []


def test_write_empty_sheet_matches_real_sample_byte_exact():
    real = _sample_page1()
    empty = MoxelSheet(version=6, def_format=CellFormat(flags=FLAG_COLUMN_WIDTH, w2=72))
    assert write_moxel(empty) == real


def test_simple_table_round_trip():
    rows = [
        ["Наименование", "Кол-во", "Цена"],
        ["Товар1", "5", "100"],
        ["", "", ""],
        ["Товар2", "3", "200"],
    ]
    sheet = simple_table(rows, column_widths=[150, 50, 80])
    data = write_moxel(sheet)

    back = parse_moxel(data)
    assert back.n_columns == 3
    assert back.n_rows == 4
    assert back.cell_text(0, 0) == "Наименование"
    assert back.cell_text(1, 1) == "5"
    assert back.cell_text(3, 2) == "200"
    assert back.cell_text(2, 0) is None  # blank row has no stored cells
    assert {k: v.format.w2 for k, v in back.columns.items()} == {0: 150, 1: 50, 2: 80}


def test_write_moxel_refuses_objects():
    sheet = simple_table([["x"]])
    sheet.objects = [object()]  # sentinel: writer must reject non-empty objects
    with pytest.raises(MoxelWriteError):
        write_moxel(sheet)


def test_full_corpus_parses_and_round_trips(tmp_path):
    import glob

    ert_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "work", "ExtForms")
    if not os.path.isdir(ert_dir):
        pytest.skip("work/ExtForms not present")

    tested = 0
    for path in sorted(glob.glob(os.path.join(ert_dir, "*.ert"))):
        ole = ole_reader.open_md_file(path)
        try:
            names = {"/".join(e) for e in ole.listdir()}
            if "Page.1" not in names:
                continue
            data = ole_reader.read_stream_raw(ole, "Page.1")
        finally:
            ole.close()

        sheet = parse_moxel(data)  # must not raise, for every real sample
        tested += 1
        if sheet.objects:
            continue
        out = write_moxel(sheet)
        reparsed = parse_moxel(out)
        assert reparsed.n_columns == sheet.n_columns
        assert reparsed.n_rows == sheet.n_rows
        for row_idx, row in sheet.rows.items():
            for col_idx in row.cells:
                assert reparsed.cell_text(row_idx, col_idx) == sheet.cell_text(row_idx, col_idx)

    assert tested > 300
