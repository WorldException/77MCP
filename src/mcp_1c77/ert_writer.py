"""Build/mutate standalone external processing (.ert) files.

An .ert is a 7-stream OLE2/CFBF container (see docs/external-ert.md). Three
of those streams have content this project can meaningfully generate or
edit: `MD Programm text` (BSL module), `Dialog Stream` (form), and
`Container.Profile` (just needs a fresh UUID on creation). The remaining
four (`Container.Contents`, `Inplace description`, `Main MetaData Stream`,
`Page.1`) are always copied byte-for-byte from a bundled real sample —
they're either pure boilerplate or (for `Main MetaData Stream`/`Page.1`)
grammars this project doesn't attempt to synthesize or validate; see
docs/external-ert.md for the rationale.

Every write here goes through `ole_writer.write_compound_file`, rebuilding
the whole container from scratch — .ert files are small (tens to a couple
hundred KB) so there's no benefit to in-place patching, and rewriting whole
avoids ever landing a half-updated container on disk.
"""

from __future__ import annotations

import re
import uuid
import zlib
from pathlib import Path

from . import ole_reader, ole_writer
from .dialog_model import Dialog
from .dialog_parser import default_dialog, parse_dialog, serialize_dialog

_TEMPLATES_DIR = Path(__file__).parent / "templates"

PAGE1_TEMPLATE = (_TEMPLATES_DIR / "page1_empty.bin").read_bytes()
MAIN_METADATA_TEMPLATE = (_TEMPLATES_DIR / "main_metadata_minimal.bin").read_bytes()
INPLACE_DESCRIPTION_TEMPLATE = b"\x03\x00"

CONTAINER_CONTENTS_TEMPLATE = (
    b'{"Container.Contents",'
    b'{"MetaDataHolderContainer","Main MetaData Stream","Main MetaData Stream",""},'
    b'{"DialogEditor","Dialog Stream","Dialog Form",""},'
    b'{"TextDocument","MD Programm text","Module text",""},'
    b'{"MetaDataDescription","Inplace description","\xce\xef\xe8\xf1\xe0\xed\xe8\xe5",""},'
    b'{"Moxcel.Worksheet","Page.1","Moxel WorkPlace",""}}\n'
)

_CONTAINER_PROFILE_UUID_PLACEHOLDER = b"D41D8CD98F00B204E9800998ECF8427E"
_CONTAINER_PROFILE_TEMPLATE = (
    b'{\n'
    b'{"MoxelName","",""},\n'
    b'{"MoxelPos","0",""},\n'
    b'{"UUID","' + _CONTAINER_PROFILE_UUID_PLACEHOLDER + b'",""},\n'
    b'{"Entry","1",""},\n'
    b'{"MoxelNextMode","1",""}}'
)

_VALID_NAME_RE = re.compile(r"^[^/\\]+$")


class ErtNameError(ValueError):
    """Raised when a processing name is invalid or unsafe to use as a filename."""


def _validate_name(name: str) -> None:
    if not name or ".." in name or not _VALID_NAME_RE.match(name):
        raise ErtNameError(
            f"Недопустимое имя обработки: '{name}'. "
            "Имя не должно быть пустым и не должно содержать '/', '\\' или '..'."
        )


def _make_container_profile() -> bytes:
    new_uuid = uuid.uuid4().hex.upper().encode("ascii")
    return _CONTAINER_PROFILE_TEMPLATE.replace(_CONTAINER_PROFILE_UUID_PLACEHOLDER, new_uuid)


def _encode_module(text: str) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    data = compressor.compress(text.encode("windows-1251", errors="replace"))
    data += compressor.flush()
    return data


def _encode_text_with_header(text: str) -> bytes:
    body = text.encode("windows-1251", errors="replace")
    if len(body) > 0xFFFF:
        raise ValueError(
            f"Текст слишком велик ({len(body)} байт) для однобайтового "
            "0xFF-заголовка потока; такие большие Dialog Stream не поддерживаются."
        )
    return b"\xff" + len(body).to_bytes(2, "little") + body


def build_new_ert_streams(module_text: str, dialog: Dialog) -> dict[str, bytes]:
    """Assemble the full 7-stream set for a brand-new .ert file."""
    return {
        "Container.Contents": CONTAINER_CONTENTS_TEMPLATE,
        "Container.Profile": _make_container_profile(),
        "Dialog Stream": _encode_text_with_header(serialize_dialog(dialog)),
        "Inplace description": INPLACE_DESCRIPTION_TEMPLATE,
        "MD Programm text": _encode_module(module_text),
        "Main MetaData Stream": MAIN_METADATA_TEMPLATE,
        "Page.1": PAGE1_TEMPLATE,
    }


_STREAM_NAMES = (
    "Container.Contents",
    "Container.Profile",
    "Dialog Stream",
    "Inplace description",
    "MD Programm text",
    "Main MetaData Stream",
    "Page.1",
)


def load_editable_streams(path: Path) -> dict[str, bytes]:
    """Read all 7 raw streams of an existing .ert, unmodified."""
    ole = ole_reader.open_md_file(path)
    try:
        return {name: ole_reader.read_stream_raw(ole, name) for name in _STREAM_NAMES}
    finally:
        ole.close()


def create_ert_file(
    edit_path: Path, name: str, module_text: str = "", dialog: Dialog | None = None
) -> Path:
    """Create a brand-new `<edit_path>/<name>.ert`. Refuses to overwrite."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if target.exists():
        raise FileExistsError(f"Обработка '{name}' уже существует в {edit_path}.")
    streams = build_new_ert_streams(module_text, dialog if dialog is not None else default_dialog())
    ole_writer.write_compound_file(target, streams)
    return target


def update_ert_module(edit_path: Path, name: str, new_module_text: str) -> None:
    """Replace only the `MD Programm text` stream of an existing edit-path .ert."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    streams["MD Programm text"] = _encode_module(new_module_text)
    ole_writer.write_compound_file(target, streams)


def update_ert_dialog(edit_path: Path, name: str, dialog: Dialog) -> None:
    """Replace only the `Dialog Stream` stream of an existing edit-path .ert."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    streams["Dialog Stream"] = _encode_text_with_header(serialize_dialog(dialog))
    ole_writer.write_compound_file(target, streams)


def get_editable_dialog(edit_path: Path, name: str) -> Dialog:
    """Load and parse the Dialog Stream of an existing edit-path .ert."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    ole = ole_reader.open_md_file(target)
    try:
        streams = ole_reader.get_root_object_streams(ole)
        text = ole_reader.read_stream_text(ole, streams["dialog"])
    finally:
        ole.close()
    return parse_dialog(text)
