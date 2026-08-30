"""Tests for reading 1C 7.7's XOR-obfuscated 1Cv7.DBA connection file.

No real credentials are stored in this repo: the round-trip test below
encodes synthetic, obviously-fake values with the same (public, fixed)
1C XOR key that `read_dba_dict` decodes with. An optional test against a
real local 1Cv7.DBA file is available for manual verification, driven
entirely by environment variables so no secret ever needs to be committed.
"""

import os

import pytest

from mcp_1c77.mssql_dba import _XOR_KEY, find_dba_file, read_dba_dict


def _encode_dba_bytes(creds: dict) -> bytes:
    """Inverse of read_dba_dict's decoding, for building synthetic fixtures."""
    text = "{" + ",".join(f'{{"{k}","{v}"}}' for k, v in creds.items()) + "}"
    return bytes(ord(ch) ^ _XOR_KEY[i % len(_XOR_KEY)] for i, ch in enumerate(text))


def test_read_dba_dict_round_trip(tmp_path):
    fake_creds = {
        "Server": "test-server.example",
        "DB": "test-db",
        "UID": "test-user",
        "PWD": "test-pass",
        "Checksum": "deadbeef",
    }
    dba_path = tmp_path / "1cv7.dba"
    dba_path.write_bytes(_encode_dba_bytes(fake_creds))

    assert read_dba_dict(dba_path) == fake_creds


def test_find_dba_file_case_insensitive(tmp_path):
    (tmp_path / "1Cv7.DBA").write_bytes(b"\x00")
    found = find_dba_file(tmp_path)
    assert found is not None
    assert found.name == "1Cv7.DBA"


def test_find_dba_file_lowercase(tmp_path):
    (tmp_path / "1cv7.dba").write_bytes(b"\x00")
    found = find_dba_file(tmp_path)
    assert found is not None
    assert found.name == "1cv7.dba"


def test_find_dba_file_missing(tmp_path):
    assert find_dba_file(tmp_path) is None


def test_find_dba_file_nonexistent_dir(tmp_path):
    assert find_dba_file(tmp_path / "does-not-exist") is None


@pytest.mark.skipif(
    not os.environ.get("TEST_DBA_PATH"),
    reason="Set TEST_DBA_PATH (and TEST_DBA_SERVER/DB/UID/PWD) to verify against a real local 1Cv7.DBA",
)
def test_read_dba_dict_against_real_file():
    """Manual/local-only check against a real 1Cv7.DBA, never committed.

    Point TEST_DBA_PATH at a real file and set the matching TEST_DBA_SERVER/
    TEST_DBA_DB/TEST_DBA_UID/TEST_DBA_PWD env vars to compare against; none
    of these values are stored in the repo.
    """
    creds = read_dba_dict(os.environ["TEST_DBA_PATH"])
    assert creds["Server"] == os.environ["TEST_DBA_SERVER"]
    assert creds["DB"] == os.environ["TEST_DBA_DB"]
    assert creds["UID"] == os.environ["TEST_DBA_UID"]
    assert creds["PWD"] == os.environ["TEST_DBA_PWD"]
