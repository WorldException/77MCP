"""Loader/index for standalone external processing files (*.ert)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ole_reader
from .bsl_parser import parse_module_structure
from .models import ModuleStructure


@dataclass
class ErtEntry:
    """A discovered external processing (.ert) file."""

    name: str  # filename without extension — the object's identity
    path: str  # absolute path to the .ert file


class ErtLoader:
    """Discovers and caches content of .ert (external processing) files
    across one or more directories."""

    def __init__(self) -> None:
        self._dirs: list[Path] = []
        self._index: dict[str, ErtEntry] | None = None
        self._module_cache: dict[str, str] = {}
        self._structure_cache: dict[str, ModuleStructure] = {}
        self._dialog_cache: dict[str, str] = {}

    def set_dirs(self, dirs: list[str]) -> None:
        """(Re)configure the scanned directories and clear all caches."""
        self._dirs = [Path(d) for d in dirs]
        self._clear_caches()

    def rescan(self) -> list[ErtEntry]:
        """Force a re-scan of configured directories for *.ert files."""
        self._clear_caches()
        return self.list_files()

    def _clear_caches(self) -> None:
        self._index = None
        self._module_cache.clear()
        self._structure_cache.clear()
        self._dialog_cache.clear()

    def list_files(self) -> list[ErtEntry]:
        """List all discovered .ert files (recursive scan of configured dirs)."""
        if self._index is not None:
            return list(self._index.values())
        index: dict[str, ErtEntry] = {}
        for d in self._dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.rglob("*.ert")):
                index[p.stem] = ErtEntry(name=p.stem, path=str(p.resolve()))
        self._index = index
        return list(index.values())

    def find(self, name: str) -> ErtEntry | None:
        """Find an entry by name (case-insensitive)."""
        self.list_files()
        assert self._index is not None
        name_lower = name.lower()
        for entry in self._index.values():
            if entry.name.lower() == name_lower:
                return entry
        return None

    def get_module(self, name: str) -> str | None:
        """Get the module source text of a .ert file by name."""
        if name in self._module_cache:
            return self._module_cache[name]
        entry = self.find(name)
        if entry is None:
            return None
        ole = ole_reader.open_md_file(entry.path)
        try:
            streams = ole_reader.get_root_object_streams(ole)
            if "module" not in streams:
                return None
            text = ole_reader.read_module_text(ole, streams["module"])
            self._module_cache[name] = text
            return text
        finally:
            ole.close()

    def get_module_structure(self, name: str) -> ModuleStructure | None:
        """Get the parsed module structure of a .ert file by name."""
        if name in self._structure_cache:
            return self._structure_cache[name]
        text = self.get_module(name)
        if text is None:
            return None
        structure = parse_module_structure(text)
        self._structure_cache[name] = structure
        return structure

    def get_dialog(self, name: str) -> str | None:
        """Get the raw Dialog Stream text (form definition) of a .ert file by name."""
        if name in self._dialog_cache:
            return self._dialog_cache[name]
        entry = self.find(name)
        if entry is None:
            return None
        ole = ole_reader.open_md_file(entry.path)
        try:
            streams = ole_reader.get_root_object_streams(ole)
            if "dialog" not in streams:
                return None
            text = ole_reader.read_stream_text(ole, streams["dialog"])
            self._dialog_cache[name] = text
            return text
        finally:
            ole.close()

    def iter_module_entries(self) -> list[tuple[str, str]]:
        """[(label, text), ...] for all discovered .ert modules, for text search."""
        out: list[tuple[str, str]] = []
        for entry in self.list_files():
            text = self.get_module(entry.name)
            if text is not None:
                out.append((f"Обработка.{entry.name}", text))
        return out
