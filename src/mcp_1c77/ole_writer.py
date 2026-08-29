"""Pure-Python writer for MS-CFB (OLE2 Compound File Binary Format) v3 files.

Writes a minimal but spec-valid compound file containing an arbitrary set of
named streams, all as direct children of the Root Entry (no substorages).
This is sufficient to build/round-trip standalone 1C 7.7 external processing
(.ert) files, which use exactly this shape.

Only what's needed for that use case is implemented:
  - sector size 512 / mini sector size 64 / mini stream cutoff 4096 (the
    fixed v3 defaults 1C 7.7 itself uses)
  - directory entries sorted by (name length, case-insensitive name), per
    the MS-CFB `CompareDirectoryEntryName` rule, arranged as a plain binary
    search tree (no red-black balancing/coloring — olefile does not validate
    either, and the file is small enough it can't matter for lookup speed)
  - no DIFAT sector chain: raises if more than 109 FAT sectors would be
    needed (~7 MB of stream data), which .ert files never approach

See docs/external-ert.md for the full format writeup and stated limitations.
"""

from __future__ import annotations

import struct
from pathlib import Path

SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 4096
DIR_ENTRY_SIZE = 128
DIR_ENTRIES_PER_SECTOR = SECTOR_SIZE // DIR_ENTRY_SIZE  # 4
FAT_ENTRIES_PER_SECTOR = SECTOR_SIZE // 4  # 128
MAX_DIFAT_ENTRIES = 109

FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF

STGTY_INVALID = 0
STGTY_STREAM = 2
STGTY_ROOT = 5

BLACK = 1


def _pad(data: bytes, size: int) -> bytes:
    if len(data) % size == 0:
        return data
    return data + b"\x00" * (size - len(data) % size)


def _sector_count(size: int, sector_size: int) -> int:
    return (size + sector_size - 1) // sector_size if size else 0


def _build_bst(
    sorted_names: list[str],
) -> tuple[list[tuple[int | None, int | None]], int | None]:
    """Build a binary search tree over `sorted_names` (already sorted).

    Returns (children, root_index) where children[i] = (left_index,
    right_index) (indices into sorted_names, or None).
    """
    n = len(sorted_names)
    children: list[tuple[int | None, int | None]] = [(None, None)] * n

    def build(lo: int, hi: int) -> int | None:
        if lo > hi:
            return None
        mid = (lo + hi) // 2
        left = build(lo, mid - 1)
        right = build(mid + 1, hi)
        children[mid] = (left, right)
        return mid

    root = build(0, n - 1)
    return children, root


def _pack_dir_entry(
    name: str,
    entry_type: int,
    color: int,
    left: int,
    right: int,
    child: int,
    start_sector: int,
    size: int,
) -> bytes:
    name_utf16 = name.encode("utf-16-le")
    if len(name_utf16) + 2 > 64:
        raise ValueError(f"stream name too long for CFBF directory entry: {name!r}")
    name_len = len(name_utf16) + 2  # incl. null terminator, in bytes
    name_field = _pad(name_utf16 + b"\x00\x00", 64)
    return struct.pack(
        "<64sHBBIII16sIQQIQ",
        name_field,
        name_len,
        entry_type,
        color,
        left,
        right,
        child,
        b"\x00" * 16,  # CLSID
        0,  # state bits
        0,  # creation time
        0,  # modified time
        start_sector,
        size,
    )


def write_compound_file(path: str | Path, streams: dict[str, bytes]) -> None:
    """Write a minimal valid MS-CFB v3 compound file at `path`.

    `streams` maps root-level stream name -> raw bytes. No substorages are
    created. Raises NotImplementedError if the resulting file would need a
    DIFAT sector chain (more than 109 FAT sectors, i.e. roughly >7 MB).
    """
    names = list(streams.keys())
    sorted_names = sorted(names, key=lambda n: (len(n), n.lower()))

    mini_names = [n for n in sorted_names if len(streams[n]) < MINI_STREAM_CUTOFF]
    regular_names = [n for n in sorted_names if len(streams[n]) >= MINI_STREAM_CUTOFF]

    # --- Mini stream container + MiniFAT ---
    mini_start_sector: dict[str, int] = {}
    mini_sector_count: dict[str, int] = {}
    mini_chain: list[int] = []  # flat list of mini-sector -> next mini-sector (or ENDOFCHAIN)
    ministream_parts: list[bytes] = []
    next_mini_sector = 0
    for name in mini_names:
        data = streams[name]
        n_sectors = _sector_count(len(data), MINI_SECTOR_SIZE)
        if n_sectors == 0:
            mini_start_sector[name] = ENDOFCHAIN
            mini_sector_count[name] = 0
            continue
        mini_start_sector[name] = next_mini_sector
        mini_sector_count[name] = n_sectors
        ministream_parts.append(_pad(data, MINI_SECTOR_SIZE))
        for i in range(n_sectors - 1):
            mini_chain.append(next_mini_sector + i + 1)
        mini_chain.append(ENDOFCHAIN)
        next_mini_sector += n_sectors

    ministream_data = b"".join(ministream_parts)
    n_minifat_sectors = _sector_count(len(mini_chain) * 4, SECTOR_SIZE)

    # --- Regular (main-FAT) streams, incl. the mini stream container itself ---
    regular_sector_count: dict[str, int] = {
        name: _sector_count(len(streams[name]), SECTOR_SIZE) for name in regular_names
    }
    ministream_sector_count = _sector_count(len(ministream_data), SECTOR_SIZE)

    n_dir_entries = 1 + len(names)  # Root Entry + streams
    n_dir_slots = -(-n_dir_entries // DIR_ENTRIES_PER_SECTOR) * DIR_ENTRIES_PER_SECTOR
    n_dir_sectors = n_dir_slots // DIR_ENTRIES_PER_SECTOR

    non_fat_sectors = (
        sum(regular_sector_count.values())
        + ministream_sector_count
        + n_minifat_sectors
        + n_dir_sectors
    )

    n_fat_sectors = 1
    for _ in range(32):
        total = non_fat_sectors + n_fat_sectors
        needed = -(-total * 4 // SECTOR_SIZE)
        if needed == n_fat_sectors:
            break
        n_fat_sectors = needed
    else:  # pragma: no cover - defensive, unreachable at .ert scale
        raise NotImplementedError("FAT sector count did not converge")

    if n_fat_sectors > MAX_DIFAT_ENTRIES:
        raise NotImplementedError(
            f"compound file too large for header-only DIFAT "
            f"({n_fat_sectors} FAT sectors > {MAX_DIFAT_ENTRIES}); "
            f"DIFAT sector chain not implemented"
        )

    # --- Assign sector numbers to each region, in this fixed order ---
    sector_cursor = 0
    regular_start_sector: dict[str, int] = {}
    for name in regular_names:
        regular_start_sector[name] = sector_cursor
        sector_cursor += regular_sector_count[name]

    ministream_start_sector = sector_cursor if ministream_sector_count else ENDOFCHAIN
    sector_cursor += ministream_sector_count

    minifat_start_sector = sector_cursor if n_minifat_sectors else ENDOFCHAIN
    sector_cursor += n_minifat_sectors

    dir_start_sector = sector_cursor
    sector_cursor += n_dir_sectors

    fat_start_sector = sector_cursor
    sector_cursor += n_fat_sectors

    total_sectors = sector_cursor

    # --- Build the main FAT ---
    # The FAT array must fill whole sectors (n_fat_sectors * 128 entries),
    # even though only `total_sectors` of those entries describe real sectors.
    fat = [FREESECT] * (n_fat_sectors * FAT_ENTRIES_PER_SECTOR)

    def chain(start: int, count: int) -> None:
        for i in range(count - 1):
            fat[start + i] = start + i + 1
        if count:
            fat[start + count - 1] = ENDOFCHAIN

    for name in regular_names:
        chain(regular_start_sector[name], regular_sector_count[name])
    if ministream_sector_count:
        chain(ministream_start_sector, ministream_sector_count)
    if n_minifat_sectors:
        chain(minifat_start_sector, n_minifat_sectors)
    chain(dir_start_sector, n_dir_sectors)
    for i in range(n_fat_sectors):
        fat[fat_start_sector + i] = FATSECT

    # --- Directory entries ---
    bst_children, bst_root = _build_bst(sorted_names)
    # sid 0 = Root Entry, sid i+1 = sorted_names[i]
    entries: list[bytes] = [b""] * n_dir_slots

    for i, name in enumerate(sorted_names):
        left_idx, right_idx = bst_children[i]
        data = streams[name]
        if name in mini_names:
            start = mini_start_sector[name]
        else:
            start = regular_start_sector[name]
        entries[i + 1] = _pack_dir_entry(
            name=name,
            entry_type=STGTY_STREAM,
            color=BLACK,
            left=(left_idx + 1) if left_idx is not None else NOSTREAM,
            right=(right_idx + 1) if right_idx is not None else NOSTREAM,
            child=NOSTREAM,
            start_sector=start,
            size=len(data),
        )

    entries[0] = _pack_dir_entry(
        name="Root Entry",
        entry_type=STGTY_ROOT,
        color=BLACK,
        left=NOSTREAM,
        right=NOSTREAM,
        child=(bst_root + 1) if bst_root is not None else NOSTREAM,
        start_sector=ministream_start_sector,
        size=len(ministream_data),
    )

    for i in range(n_dir_entries, n_dir_slots):
        entries[i] = _pack_dir_entry(
            name="", entry_type=STGTY_INVALID, color=0,
            left=NOSTREAM, right=NOSTREAM, child=NOSTREAM,
            start_sector=0, size=0,
        )

    # --- Assemble sector-region byte blobs ---
    out: list[bytes] = []
    for name in regular_names:
        out.append(_pad(streams[name], SECTOR_SIZE))
    if ministream_sector_count:
        out.append(_pad(ministream_data, SECTOR_SIZE))

    minifat_bytes = b"".join(struct.pack("<I", v) for v in mini_chain)
    if n_minifat_sectors:
        minifat_bytes = _pad(minifat_bytes, SECTOR_SIZE)
        # pad any remaining slots in the last sector with FREESECT
        used = len(mini_chain) * 4
        total_minifat_bytes = n_minifat_sectors * SECTOR_SIZE
        if total_minifat_bytes > used:
            minifat_bytes = (
                minifat_bytes[:used]
                + struct.pack("<I", FREESECT) * ((total_minifat_bytes - used) // 4)
            )
        out.append(minifat_bytes)

    out.append(b"".join(entries))

    fat_bytes = b"".join(struct.pack("<I", v) for v in fat)
    out.append(fat_bytes)  # already exactly n_fat_sectors * SECTOR_SIZE

    body = b"".join(out)
    assert len(body) == total_sectors * SECTOR_SIZE

    # --- Header ---
    difat = [FREESECT] * MAX_DIFAT_ENTRIES
    for i in range(n_fat_sectors):
        difat[i] = fat_start_sector + i

    header = struct.pack(
        "<8s16sHHHHH6sIIIIIIII",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        b"\x00" * 16,  # CLSID
        0x003E,  # minor version
        0x0003,  # major version
        0xFFFE,  # byte order
        9,  # sector shift (512)
        6,  # mini sector shift (64)
        b"\x00" * 6,  # reserved
        0,  # number of directory sectors (must be 0 for v3)
        n_fat_sectors,
        dir_start_sector,
        0,  # transaction signature
        MINI_STREAM_CUTOFF,
        minifat_start_sector,
        n_minifat_sectors,
        ENDOFCHAIN,  # first DIFAT sector (none)
    )
    header += struct.pack("<I", 0)  # number of DIFAT sectors
    header += b"".join(struct.pack("<I", v) for v in difat)
    assert len(header) == SECTOR_SIZE

    Path(path).write_bytes(header + body)
