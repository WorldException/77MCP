"""Tests for the pure-Python CFBF (OLE2) writer."""

import os

import olefile
import pytest

from mcp_1c77 import ole_writer

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample.ert")


def _round_trip(streams: dict[str, bytes], path) -> olefile.OleFileIO:
    ole_writer.write_compound_file(path, streams)
    return olefile.OleFileIO(str(path))


def test_write_and_read_back_all_streams(tmp_path):
    streams = {
        "Tiny": b"x" * 5,
        "AtMiniCutoff": b"y" * 4095,
        "JustOverCutoff": b"z" * 4097,
        "Large": b"w" * 60000,
    }
    path = tmp_path / "test.ert"
    ole = _round_trip(streams, path)
    try:
        names = {"/".join(e) for e in ole.listdir()}
        assert names == set(streams.keys())
        for name, data in streams.items():
            assert ole.openstream(name).read() == data
    finally:
        ole.close()


def test_write_single_stream(tmp_path):
    path = tmp_path / "single.ert"
    ole = _round_trip({"Only": b"hello"}, path)
    try:
        assert ole.openstream("Only").read() == b"hello"
    finally:
        ole.close()


def test_write_empty_stream(tmp_path):
    path = tmp_path / "empty.ert"
    ole = _round_trip({"A": b"", "B": b"data"}, path)
    try:
        assert ole.openstream("A").read() == b""
        assert ole.openstream("B").read() == b"data"
    finally:
        ole.close()


@pytest.mark.skipif(not os.path.exists(FIXTURE), reason="fixture .ert not found")
def test_directory_order_matches_real_sample(tmp_path):
    real = olefile.OleFileIO(FIXTURE)
    try:
        streams = {
            "/".join(e): real.openstream("/".join(e)).read() for e in real.listdir()
        }
    finally:
        real.close()

    out_path = tmp_path / "rewritten.ert"
    ole = _round_trip(streams, out_path)
    try:
        names = {"/".join(e) for e in ole.listdir()}
        assert names == set(streams.keys())
        for name, data in streams.items():
            assert ole.openstream(name).read() == data
    finally:
        ole.close()


def test_rejects_more_than_109_fat_sectors(tmp_path):
    # A single stream large enough to need > 109 FAT sectors (> ~7 MB of
    # sector-covering data) must raise rather than silently truncate.
    streams = {"Huge": b"a" * (110 * 128 * 512)}
    with pytest.raises(NotImplementedError):
        ole_writer.write_compound_file(tmp_path / "huge.ert", streams)
