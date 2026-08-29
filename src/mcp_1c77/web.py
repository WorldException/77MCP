"""Unified Starlette application: web UI + MCP SSE transport."""

from __future__ import annotations

import os
import tempfile
import traceback

from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from . import tools
from .server import mcp

# MCP_BASEPATH: explicit, existing, read-only configuration directory.
# MCP_DATA_DIR: writable staging directory for uploads, used only when
# MCP_BASEPATH is not set (defaults to a temp folder, never a config dir).
BASEPATH = os.environ.get("MCP_BASEPATH")
DATA_DIR = os.environ.get("MCP_DATA_DIR", os.path.join(tempfile.gettempdir(), "mcp_1c77"))
CONFIG_DIR = BASEPATH if BASEPATH else DATA_DIR
READONLY = bool(BASEPATH)
MD_FILENAME = "1cv7.md"
_EXTRA_EXT_DIRS = [d for d in os.environ.get("MCP_EXT_DIRS", "").split(os.pathsep) if d]

# MCP_EDIT_PATH: optional writable directory where new .ert files can be
# created/edited via MCP tools. When unset, those tools stay disabled.
EDIT_PATH = os.environ.get("MCP_EDIT_PATH")


def _resolve_ext_dirs() -> list[str]:
    """Resolve directories to scan for external processing (.ert) files.

    Always includes "<CONFIG_DIR>/ExtForms"; values from MCP_EXT_DIRS are
    appended (resolved relative to CONFIG_DIR unless absolute). EDIT_PATH,
    if set, is also appended so newly created/edited files are immediately
    visible to the read-only .ert tools.
    """
    base = Path(CONFIG_DIR)
    dirs = [str(base / "ExtForms")]
    for d in _EXTRA_EXT_DIRS:
        p = Path(d)
        resolved = str(p if p.is_absolute() else base / p)
        if resolved not in dirs:
            dirs.append(resolved)
    if EDIT_PATH and EDIT_PATH not in dirs:
        dirs.append(EDIT_PATH)
    return dirs

_HTML_PAGE_PATH = Path(__file__).parent / "static" / "index.html"
HTML_PAGE = _HTML_PAGE_PATH.read_text(encoding="utf-8")



async def upload_page(request: Request) -> HTMLResponse:
    """Serve the upload page."""
    return HTMLResponse(HTML_PAGE)


async def handle_upload(request: Request) -> JSONResponse:
    """Handle file upload or reload of existing file."""
    if READONLY:
        return JSONResponse({
            "ok": False,
            "error": "Upload отключён: сервер запущен с явным --basepath (доступно только чтение).",
        })

    os.makedirs(DATA_DIR, exist_ok=True)
    md_path = os.path.join(DATA_DIR, MD_FILENAME)

    form = await request.form()
    uploaded = form.get("file")

    if uploaded is not None and hasattr(uploaded, "read"):
        contents = await uploaded.read()
        if not contents:
            # Empty file in form — try reloading existing
            if not os.path.exists(md_path):
                return JSONResponse({"ok": False, "error": "No file uploaded and no existing file to reload."})
        else:
            with open(md_path, "wb") as f:
                f.write(contents)
    else:
        # No file in request — reload existing
        if not os.path.exists(md_path):
            return JSONResponse({"ok": False, "error": "No file uploaded and no existing file to reload."})

    try:
        tools.init(md_path)
        config = tools.get_loader().config
        return JSONResponse({
            "ok": True,
            "name": config.name,
            "version": config.version,
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Parse error: {e}\n{traceback.format_exc()}"})


async def api_status(request: Request) -> JSONResponse:
    """Return current configuration status as JSON."""
    server_info = {
        "base_dir": str(Path(CONFIG_DIR).resolve()),
        "ext_dirs": [str(Path(d).resolve()) for d in _resolve_ext_dirs()],
        "ert_count": len(tools.get_ert_loader().list_files()),
        "readonly": READONLY,
        "edit_path": str(Path(EDIT_PATH).resolve()) if EDIT_PATH else None,
    }

    loader = tools.get_loader()
    if not loader.is_loaded:
        return JSONResponse({"loaded": False, "server": server_info})

    config = loader.config
    coa_count = 1 if config.chart_of_accounts and config.chart_of_accounts.id else 0
    return JSONResponse({
        "loaded": True,
        "name": config.name,
        "version": config.version,
        "file_path": config.file_path,
        "counts": {
            "constants": len(config.constants),
            "catalogs": len(config.catalogs),
            "documents": len(config.documents),
            "registers": len(config.registers),
            "enums": len(config.enums),
            "reports": len(config.reports),
            "journals": len(config.journals),
            "calc_vars": len(config.calc_vars),
            "chart_of_accounts": coa_count,
        },
        "server": server_info,
    })


async def startup() -> None:
    """Try to load existing configuration on startup."""
    if READONLY:
        if not os.path.isdir(CONFIG_DIR):
            print(f"MCP_BASEPATH '{CONFIG_DIR}' does not exist or is not a directory.")
    else:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    tools.set_data_dir(CONFIG_DIR)
    if EDIT_PATH:
        os.makedirs(EDIT_PATH, exist_ok=True)
        tools.init_edit_path(EDIT_PATH)
    tools.init_ert_dirs(_resolve_ext_dirs())
    md_path = os.path.join(CONFIG_DIR, MD_FILENAME)
    if os.path.exists(md_path):
        try:
            tools.init(md_path)
            print(f"Auto-loaded configuration from {md_path}")
        except Exception as e:
            print(f"Failed to auto-load {md_path}: {e}")


# Build the unified ASGI app
mcp_sse_app = mcp.sse_app()


@asynccontextmanager
async def lifespan(app):
    await startup()
    yield


app = Starlette(
    routes=[
        Route("/", upload_page),
        Route("/upload", handle_upload, methods=["POST"]),
        Route("/api/status", api_status),
        Mount("/", app=mcp_sse_app),
    ],
    lifespan=lifespan,
)
