"""Tests for the .ert (external processing) MCP tool functions."""

import os

import pytest

from mcp_1c77 import tools

ERT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "2.ert")
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

pytestmark = pytest.mark.skipif(
    not os.path.exists(ERT_FILE),
    reason="Test file 2.ert not found",
)


@pytest.fixture(autouse=True)
def ert_dirs():
    tools.init_ert_dirs([REPO_ROOT])
    yield
    tools.init_ert_dirs([])


def test_list_ert_files():
    result = tools.list_ert_files()
    assert "2" in result


def test_find_ert_file_found():
    result = tools.find_ert_file("2")
    assert "Найдена" in result


def test_find_ert_file_not_found():
    result = tools.find_ert_file("does_not_exist_xyz")
    assert "не найдена" in result


def test_list_ert_procedures():
    result = tools.list_ert_procedures("2")
    assert "процедуры" in result.lower() or "Процедура" in result


def test_get_ert_procedure_source_not_found():
    result = tools.get_ert_procedure_source("2", "NonExistentProc")
    assert "не найдена" in result


def test_get_ert_module_full():
    result = tools.get_ert_module("2")
    assert "Процедура" in result


def test_get_ert_module_line_range():
    result = tools.get_ert_module("2", start_line=1, end_line=1)
    assert "строки 1" in result or "строки" in result


def test_get_ert_module_missing():
    result = tools.get_ert_module("does_not_exist_xyz")
    assert "не найдена" in result


def test_search_in_ert_modules():
    result = tools.search_in_ert_modules("Процедура")
    assert "Обработка.2" in result


def test_get_ert_form():
    result = tools.get_ert_form("2")
    assert "Dialogs" in result


def test_reload_ert_files():
    result = tools.reload_ert_files()
    assert "Пересканировано" in result
