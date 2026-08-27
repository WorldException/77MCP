"""Entry point for running the server as `python -m mcp_1c77`."""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp_1c77")
    parser.add_argument(
        "--basepath",
        default=None,
        help="Каталог с уже готовым 1cv7.md (только чтение; upload отключается)",
    )
    parser.add_argument(
        "--exts",
        nargs="*",
        default=None,
        help="Доп. каталоги с внешними обработками (*.ert), добавляются к каталогу ExtForms",
    )
    args = parser.parse_args()

    if args.basepath:
        os.environ["MCP_BASEPATH"] = args.basepath
    if args.exts:
        os.environ["MCP_EXT_DIRS"] = os.pathsep.join(args.exts)

    import uvicorn

    from .web import app

    uvicorn.run(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()
