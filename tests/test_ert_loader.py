"""Tests for the ErtLoader (standalone external processing .ert files)."""

import os
import shutil

import pytest

from mcp_1c77.ert_loader import ErtLoader

ERT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "2.ert")
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

pytestmark = pytest.mark.skipif(
    not os.path.exists(ERT_FILE),
    reason="Test file 2.ert not found",
)


@pytest.fixture
def loader() -> ErtLoader:
    ld = ErtLoader()
    ld.set_dirs([REPO_ROOT])
    return ld


def test_list_files_finds_ert(loader):
    entries = loader.list_files()
    names = [e.name for e in entries]
    assert "2" in names


def test_find_by_name_case_insensitive(tmp_path):
    named = tmp_path / "MyProc.ert"
    shutil.copy(ERT_FILE, named)
    ld = ErtLoader()
    ld.set_dirs([str(tmp_path)])

    assert ld.find("myproc") is not None
    assert ld.find("MYPROC") is not None
    assert ld.find("MyProc").name == "MyProc"


def test_find_missing_returns_none(loader):
    assert loader.find("does_not_exist_xyz") is None


def test_get_module_returns_text(loader):
    text = loader.get_module("2")
    assert text is not None
    assert "Процедура" in text


def test_get_module_structure_has_procedures(loader):
    structure = loader.get_module_structure("2")
    assert structure is not None
    assert len(structure.procedures) > 0


def test_get_dialog_returns_bracket_text(loader):
    dialog = loader.get_dialog("2")
    assert dialog is not None
    assert "Dialogs" in dialog


def test_rescan_reflects_new_files(tmp_path):
    ld = ErtLoader()
    ld.set_dirs([str(tmp_path)])
    assert ld.list_files() == []

    nested = tmp_path / "subdir"
    nested.mkdir()
    shutil.copy(ERT_FILE, nested / "copy.ert")

    # Cached index doesn't pick up the new file until rescanned
    assert ld.list_files() == []

    entries = ld.rescan()
    names = [e.name for e in entries]
    assert "copy" in names
