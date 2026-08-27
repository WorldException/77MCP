"""Tests for basepath (read-only) vs MCP_DATA_DIR (upload) separation in web.py."""

import importlib
import os

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def clean_env():
    saved = {
        k: os.environ.pop(k, None) for k in ("MCP_BASEPATH", "MCP_DATA_DIR", "MCP_EXT_DIRS")
    }
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _load_web():
    from mcp_1c77 import web as web_module

    return importlib.reload(web_module)


def test_upload_disabled_when_basepath_set(tmp_path, clean_env):
    os.environ["MCP_BASEPATH"] = str(tmp_path)
    web = _load_web()

    with TestClient(web.app) as client:
        resp = client.post("/upload", files={"file": ("1cv7.md", b"data")})
        assert resp.json()["ok"] is False

        status = client.get("/api/status").json()
        assert status["server"]["readonly"] is True
        assert status["server"]["base_dir"] == str(tmp_path.resolve())

    assert not (tmp_path / "1cv7.md").exists()


def test_upload_enabled_without_basepath(tmp_path, clean_env):
    os.environ["MCP_DATA_DIR"] = str(tmp_path)
    web = _load_web()

    with TestClient(web.app) as client:
        status = client.get("/api/status").json()
        assert status["server"]["readonly"] is False
        assert status["server"]["base_dir"] == str(tmp_path.resolve())
