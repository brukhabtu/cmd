# /// script
# requires-python = ">=3.12"
# ///
"""Check a cmd.app bundle: its Info.plist, its icon and its layout (task 1.23).

The plist must name the `cmd` executable and the `cmd.icns` icon and carry LSUIElement,
which hides the Dock icon and the menu bar. The icon must hold the sizes Finder and the
Dock read. Contents/MacOS holds the `cmd` executable and, beside it, the `uv` that runs
the plugins (decision 7). Standard library only, so it runs on the macOS runner's own
Python and on Linux against a bundle laid out there.

Usage: python scripts/check_bundle.py path/to/cmd.app [--without-uv]
  --without-uv skips the uv check, for a bundle laid out on Linux with no uv placed.
"""

import os
import plistlib
import struct
import sys
from pathlib import Path

USAGE = "usage: python scripts/check_bundle.py path/to/cmd.app [--without-uv]"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# The plist values a correct bundle carries, and why each matters.
EXPECTED: dict[str, tuple[object, str]] = {
    "CFBundleExecutable": ("cmd", "the binary in Contents/MacOS that launchd starts"),
    "CFBundlePackageType": ("APPL", "what makes the directory an application"),
    "CFBundleIconFile": ("cmd.icns", "the icon Finder and the Dock show"),
    "LSUIElement": (True, "no Dock icon and no menu bar, for a launcher"),
}

# A PNG's signature, IHDR length and type, then width and height: 24 bytes to the size.
PNG_HEADER = 24
# An ICNS file header, and each entry's: a four-byte type and a four-byte length.
ICNS_HEADER = 8

# ICNS entry types and the pixel size each must hold.
ICON_SIZES = {"ic10": 1024, "ic09": 512, "ic08": 256}


def plist_problems(plist: dict[str, object]) -> list[str]:
    """What is wrong with an Info.plist's values, one message each."""
    problems = []
    for key, (want, why) in EXPECTED.items():
        if key not in plist:
            problems.append(f"Info.plist: {key} is missing; want {want!r}, {why}")
        elif plist[key] != want or type(plist[key]) is not type(want):
            problems.append(f"Info.plist: {key} is {plist[key]!r}; want {want!r}, {why}")
    identifier = plist.get("CFBundleIdentifier")
    if not isinstance(identifier, str) or not identifier:
        problems.append("Info.plist: CFBundleIdentifier is missing; preferences key on it")
    return problems


def png_size(data: bytes) -> tuple[int, int] | None:
    """A PNG's width and height from its IHDR chunk, or None when it is not a PNG."""
    if len(data) < PNG_HEADER or not data.startswith(PNG_MAGIC) or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return (width, height)


def icns_entries(data: bytes) -> dict[str, tuple[int, int] | None]:
    """Each entry of an ICNS file by type, with its PNG size (None for a non-PNG entry).

    Raises:
        ValueError: the header or an entry's length is not what the format says.
    """
    if len(data) < ICNS_HEADER or data[:4] != b"icns":
        raise ValueError("not an ICNS file: the magic is not 'icns'")
    (total,) = struct.unpack(">I", data[4:8])
    if total != len(data):
        raise ValueError(f"ICNS header says {total} bytes, the file has {len(data)}")
    entries: dict[str, tuple[int, int] | None] = {}
    offset = 8
    while offset < total:
        if offset + 8 > total:
            raise ValueError(f"ICNS entry header at {offset} runs past the end")
        kind = data[offset : offset + 4].decode("latin-1")
        (length,) = struct.unpack(">I", data[offset + 4 : offset + 8])
        if length < ICNS_HEADER or offset + length > total:
            raise ValueError(f"ICNS entry {kind} at {offset} has a bad length {length}")
        entries[kind] = png_size(data[offset + 8 : offset + length])
        offset += length
    return entries


def icns_problems(data: bytes) -> list[str]:
    """What the icon lacks, one message per missing or wrong size."""
    try:
        entries = icns_entries(data)
    except ValueError as error:
        return [f"cmd.icns: {error}"]
    problems = []
    for kind, size in ICON_SIZES.items():
        if kind not in entries:
            problems.append(
                f"cmd.icns: no {kind} entry; want {size}x{size} for Finder and the Dock"
            )
        elif entries[kind] != (size, size):
            problems.append(f"cmd.icns: {kind} is {entries[kind]}; want {size}x{size}")
    return problems


def executable(path: Path) -> bool:
    """Whether `path` is a file this user may execute."""
    return path.is_file() and os.access(path, os.X_OK)


def layout_problems(app: Path, *, with_uv: bool) -> list[str]:
    """What is wrong with the bundle on disk: the plist, the executables and the icon."""
    contents = app / "Contents"
    problems = []
    info = contents / "Info.plist"
    try:
        with info.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as error:
        problems.append(f"Info.plist: cannot read {info}: {error}")
    else:
        problems.extend(plist_problems(plist))
    if not executable(contents / "MacOS" / "cmd"):
        problems.append("Contents/MacOS/cmd is not an executable file; it is the launcher")
    if with_uv and not executable(contents / "MacOS" / "uv"):
        problems.append("Contents/MacOS/uv is not an executable file; plugins run on it")
    icon = contents / "Resources" / "cmd.icns"
    if icon.is_file():
        problems.extend(icns_problems(icon.read_bytes()))
    else:
        problems.append("Contents/Resources/cmd.icns is missing; Finder shows a blank icon")
    return problems


def main(argv: list[str]) -> int:
    """Check the bundle at argv's one path; 0 when well formed, 1 on problems, 2 on usage."""
    paths = [arg for arg in argv if not arg.startswith("--")]
    flags = {arg for arg in argv if arg.startswith("--")}
    if len(paths) != 1 or not flags <= {"--without-uv"}:
        print(USAGE, file=sys.stderr)
        return 2
    problems = layout_problems(Path(paths[0]), with_uv="--without-uv" not in flags)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"{paths[0]}: the bundle is well formed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
