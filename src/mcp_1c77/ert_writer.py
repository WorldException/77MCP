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
import zlib
from pathlib import Path

from . import ole_reader, ole_writer
from .dialog_model import Dialog
from .dialog_parser import default_dialog, parse_dialog, serialize_dialog
from .moxel_model import MoxelSheet
from .moxel_reader import parse_moxel
from .moxel_writer import simple_table, write_moxel

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

_CONTAINER_PROFILE_TEMPLATE = (
    b'{\n'
    b'{"MoxelName","",""},\n'
    b'{"MoxelPos","0",""},\n'
    b'{"UUID","D41D8CD98F00B204E9800998ECF8427E",""},\n'
    b'{"Entry","1",""},\n'
    b'{"MoxelNextMode","1",""}}'
)

_VALID_NAME_RE = re.compile(r"^[^/\\]+$")


class ErtNameError(ValueError):
    """Raised when a processing name is invalid or unsafe to use as a filename."""


class ErtPatchError(ValueError):
    """Raised when a module patch edit can't be applied unambiguously."""


def _validate_name(name: str) -> None:
    if not name or ".." in name or not _VALID_NAME_RE.match(name):
        raise ErtNameError(
            f"Недопустимое имя обработки: '{name}'. "
            "Имя не должно быть пустым и не должно содержать '/', '\\' или '..'."
        )


def _make_container_profile() -> bytes:
    return _CONTAINER_PROFILE_TEMPLATE


def _encode_module(text: str) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    data = compressor.compress(text.encode("windows-1251", errors="replace"))
    data += compressor.flush()
    return data


def _decode_module(data: bytes) -> str:
    try:
        decompressed = zlib.decompress(data, -15)
        return decompressed.decode("windows-1251", errors="replace")
    except zlib.error:
        return data.decode("windows-1251", errors="replace")


def _encode_text_with_header(text: str) -> bytes:
    body = text.encode("windows-1251", errors="replace")
    if len(body) > 0xFFFF:
        raise ValueError(
            f"Текст слишком велик ({len(body)} байт) для однобайтового "
            "0xFF-заголовка потока; такие большие Dialog Stream не поддерживаются."
        )
    return b"\xff" + len(body).to_bytes(2, "little") + body


def build_new_ert_streams(
    module_text: str, dialog: Dialog, print_form: MoxelSheet | None = None
) -> dict[str, bytes]:
    """Assemble the full 7-stream set for a brand-new .ert file.

    `print_form`, if given, replaces the default empty `Page.1` template
    with a freshly built MOXCEL sheet (see moxel_writer.simple_table).
    """
    return {
        "Container.Contents": CONTAINER_CONTENTS_TEMPLATE,
        "Container.Profile": _make_container_profile(),
        "Dialog Stream": _encode_text_with_header(serialize_dialog(dialog)),
        "Inplace description": INPLACE_DESCRIPTION_TEMPLATE,
        "MD Programm text": _encode_module(module_text),
        "Main MetaData Stream": MAIN_METADATA_TEMPLATE,
        "Page.1": write_moxel(print_form) if print_form is not None else PAGE1_TEMPLATE,
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
    edit_path: Path,
    name: str,
    module_text: str = "",
    dialog: Dialog | None = None,
    print_form_rows: list[list[str]] | None = None,
) -> Path:
    """Create a brand-new `<edit_path>/<name>.ert`. Refuses to overwrite.

    `print_form_rows`, if given, builds the initial `Page.1` print form as a
    simple grid of cell text (see moxel_writer.simple_table); otherwise the
    print form is left empty (the same default 1C itself uses for a new
    processing with no print form configured).
    """
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if target.exists():
        raise FileExistsError(f"Обработка '{name}' уже существует в {edit_path}.")
    print_form = simple_table(print_form_rows) if print_form_rows else None
    streams = build_new_ert_streams(
        module_text, dialog if dialog is not None else default_dialog(), print_form
    )
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


def patch_ert_module(
    edit_path: Path, name: str, edits: list[tuple[str, str, bool]]
) -> str:
    """Apply a sequence of exact string replacements to the `MD Programm
    text` stream of an existing edit-path .ert, then write the whole file
    back once.

    Each edit is `(old_string, new_string, replace_all)`. `old_string` must
    occur exactly once in the module text at the time it's applied, unless
    `replace_all` is set. Edits are applied in order against the running
    result of the previous ones, and only the final text is written — so a
    failure partway through leaves the file untouched.

    Returns the new module text (so callers can confirm the result without
    a separate read).
    """
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    text = _decode_module(streams["MD Programm text"])

    for i, (old, new, replace_all) in enumerate(edits, start=1):
        if old == "":
            raise ErtPatchError(f"Правка #{i}: old_string не может быть пустой строкой.")
        count = text.count(old)
        if count == 0:
            raise ErtPatchError(f"Правка #{i}: old_string не найден в модуле.")
        if count > 1 and not replace_all:
            raise ErtPatchError(
                f"Правка #{i}: old_string встречается {count} раз(а) в модуле; "
                "уточните контекст вокруг фрагмента или укажите replace_all=true."
            )
        text = text.replace(old, new) if replace_all else text.replace(old, new, 1)

    streams["MD Programm text"] = _encode_module(text)
    ole_writer.write_compound_file(target, streams)
    return text


def append_ert_module_text(edit_path: Path, name: str, text: str) -> str:
    """Append `text` to the end of the `MD Programm text` stream of an
    existing edit-path .ert (e.g. adding a whole new procedure), without
    resending the existing module text or needing to know its current
    length. A separating newline is inserted if the current text doesn't
    already end with one.

    Returns the new module text.
    """
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    current = _decode_module(streams["MD Programm text"])
    if current and not current.endswith("\n"):
        current += "\n"
    text = current + text
    streams["MD Programm text"] = _encode_module(text)
    ole_writer.write_compound_file(target, streams)
    return text


def replace_ert_module_lines(
    edit_path: Path, name: str, start_line: int, end_line: int, new_text: str
) -> str:
    """Replace the 1-based inclusive line range [start_line, end_line] of the
    `MD Programm text` stream of an existing edit-path .ert with `new_text`,
    then write the whole file back once.

    Returns the new module text.
    """
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    text = _decode_module(streams["MD Programm text"])
    lines = text.splitlines()
    total = len(lines)
    if start_line < 1 or start_line > total:
        raise ErtPatchError(f"Строка начала {start_line} вне диапазона 1..{total}.")
    if end_line < start_line or end_line > total:
        raise ErtPatchError(
            f"Строка конца {end_line} вне диапазона {start_line}..{total}."
        )
    new_lines = lines[: start_line - 1] + new_text.splitlines() + lines[end_line:]
    text = "\n".join(new_lines)
    streams["MD Programm text"] = _encode_module(text)
    ole_writer.write_compound_file(target, streams)
    return text


def update_ert_dialog(edit_path: Path, name: str, dialog: Dialog) -> None:
    """Replace only the `Dialog Stream` stream of an existing edit-path .ert."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    streams["Dialog Stream"] = _encode_text_with_header(serialize_dialog(dialog))
    ole_writer.write_compound_file(target, streams)


def update_ert_print_form(edit_path: Path, name: str, rows: list[list[str]]) -> None:
    """Replace only the `Page.1` (MOXCEL print form) stream of an existing
    edit-path .ert with a freshly built simple grid of cell text."""
    _validate_name(name)
    target = edit_path / f"{name}.ert"
    if not target.exists():
        raise FileNotFoundError(f"Обработка '{name}' не найдена в {edit_path}.")
    streams = load_editable_streams(target)
    streams["Page.1"] = write_moxel(simple_table(rows))
    ole_writer.write_compound_file(target, streams)


def get_print_form(path: Path) -> MoxelSheet:
    """Load and parse the Page.1 (MOXCEL print form) of any .ert file."""
    ole = ole_reader.open_md_file(path)
    try:
        data = ole_reader.read_stream_raw(ole, "Page.1")
    finally:
        ole.close()
    return parse_moxel(data)


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
