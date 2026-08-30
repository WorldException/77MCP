"""Tests for CLI argument parsing in __main__.py."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clean_env():
    saved = {
        k: os.environ.pop(k, None)
        for k in ("MCP_BASEPATH", "MCP_DATA_DIR", "MCP_EXT_DIRS", "MCP_EDIT_PATH")
    }
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _run_main(argv):
    from mcp_1c77 import __main__ as entry

    with patch("sys.argv", ["mcp_1c77", *argv]), patch("uvicorn.run") as mock_run:
        entry.main()
        mock_run.assert_called_once()


def test_basepath_sets_env():
    _run_main(["--basepath", "/some/dir"])
    assert os.environ["MCP_BASEPATH"] == "/some/dir"
    assert "MCP_DATA_DIR" not in os.environ


def test_exts_sets_env():
    _run_main(["--exts", "foo", "bar"])
    assert os.environ["MCP_EXT_DIRS"] == os.pathsep.join(["foo", "bar"])


def test_edit_path_sets_env():
    _run_main(["--edit-path", "/some/edit/dir"])
    assert os.environ["MCP_EDIT_PATH"] == "/some/edit/dir"


def test_no_args_leaves_env_unset():
    _run_main([])
    assert "MCP_BASEPATH" not in os.environ
    assert "MCP_DATA_DIR" not in os.environ
    assert "MCP_EXT_DIRS" not in os.environ
    assert "MCP_EDIT_PATH" not in os.environ


def test_basepath_and_exts_together():
    _run_main(["--basepath", "/data2", "--exts", "ExtForms2"])
    assert os.environ["MCP_BASEPATH"] == "/data2"
    assert os.environ["MCP_EXT_DIRS"] == "ExtForms2"
