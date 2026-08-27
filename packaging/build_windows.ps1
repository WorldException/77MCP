# Build a standalone mcp-1c77.exe on Windows.
# Requires: uv (https://docs.astral.sh/uv/) and Python 3.11+ available to it.
# Run from the repository root:
#   .\packaging\build_windows.ps1

$ErrorActionPreference = "Stop"

uv sync --extra build
uv run pyinstaller packaging/mcp_1c77.spec --clean --noconfirm

Write-Host "Built: dist/mcp-1c77.exe"
