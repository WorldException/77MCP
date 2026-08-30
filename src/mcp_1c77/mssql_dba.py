"""Reader for 1C 7.7's `1Cv7.DBA` file (MSSQL connection parameters).

The file is a simple XOR-obfuscated (not encrypted — the key is fixed and
public) text blob written by 1C 7.7 itself, sitting next to `1Cv7.MD` in a
real base directory. Format ported from the reference reader in
`v7client/dba.py`, with `eval()` replaced by `json.loads()`: after the
XOR-decode and the bracket-to-JSON substitutions below, the result is valid
JSON, so there is no need to evaluate it as Python code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

_XOR_KEY = "19465912879oiuxc ensdfaiuo3i73798kjl".encode("us-ascii")


class DbaCredentials(TypedDict):
    Server: str
    DB: str
    UID: str
    PWD: str
    Checksum: str


def read_dba_dict(path: str | Path) -> DbaCredentials:
    """Decode a `1Cv7.DBA` file into its connection parameters."""
    with open(path, "rb") as f:
        buf = f.read()

    decoded = "".join(chr(b ^ _XOR_KEY[i % len(_XOR_KEY)]) for i, b in enumerate(buf))
    # 1C serializes this as nested `{"Key","Value"}` pairs, e.g.
    # `{{"Server","host"},{"DB","db"},...}` — rewrite into plain JSON.
    as_json = (
        decoded.replace('","', '":"')
        .replace("{{", "{")
        .replace("}}", "}")
        .replace("},{", ",")
    )
    return json.loads(as_json)


def find_dba_file(directory: str | Path) -> Path | None:
    """Case-insensitively find a `1cv7.dba` file directly inside `directory`."""
    directory = Path(directory)
    if not directory.is_dir():
        return None
    for entry in directory.iterdir():
        if entry.is_file() and entry.name.lower() == "1cv7.dba":
            return entry
    return None
