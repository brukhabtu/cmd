"""The bundle check: the plist values, the ICNS walk, and a bundle laid out on disk."""

import plistlib
import struct
import zlib
from pathlib import Path

import pytest
from check_bundle import icns_entries, icns_problems, layout_problems, main, plist_problems

GOOD_PLIST: dict[str, object] = {
    "CFBundleExecutable": "cmd",
    "CFBundlePackageType": "APPL",
    "CFBundleIconFile": "cmd.icns",
    "CFBundleIdentifier": "com.brukhabtu.cmd",
    "LSUIElement": True,
}


def png(size: int) -> bytes:
    """A real PNG header and IHDR of `size` square; only the IHDR is read."""
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    crc = struct.pack(">I", zlib.crc32(chunk))
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + chunk + crc


def icns(entries: dict[str, bytes]) -> bytes:
    body = b"".join(
        kind.encode() + struct.pack(">I", len(data) + 8) + data for kind, data in entries.items()
    )
    return b"icns" + struct.pack(">I", len(body) + 8) + body


GOOD_ICNS = icns({"ic08": png(256), "ic09": png(512), "ic10": png(1024)})


def test_a_good_plist_has_no_problems() -> None:
    assert plist_problems(GOOD_PLIST) == []


def test_a_missing_or_false_lsuielement_is_named() -> None:
    missing = {k: v for k, v in GOOD_PLIST.items() if k != "LSUIElement"}
    assert plist_problems(missing) == [
        "Info.plist: LSUIElement is missing; want True, no Dock icon and no menu bar, for a launcher"
    ]
    assert plist_problems(GOOD_PLIST | {"LSUIElement": False}) == [
        "Info.plist: LSUIElement is False; want True, no Dock icon and no menu bar, for a launcher"
    ]
    # The integer 1 is not the boolean the key needs.
    assert len(plist_problems(GOOD_PLIST | {"LSUIElement": 1})) == 1


def test_a_wrong_executable_and_a_missing_identifier_are_named() -> None:
    plist = {k: v for k, v in GOOD_PLIST.items() if k != "CFBundleIdentifier"}
    assert plist_problems(plist | {"CFBundleExecutable": "cmd-app"}) == [
        (
            "Info.plist: CFBundleExecutable is 'cmd-app'; want 'cmd', "
            "the binary in Contents/MacOS that launchd starts"
        ),
        "Info.plist: CFBundleIdentifier is missing; preferences key on it",
    ]


def test_icns_entries_reads_each_png_size() -> None:
    assert icns_entries(GOOD_ICNS) == {"ic08": (256, 256), "ic09": (512, 512), "ic10": (1024, 1024)}
    assert icns_entries(icns({"is32": b"\x00" * 10})) == {"is32": None}


def test_icns_entries_refuses_a_bad_magic_or_length() -> None:
    with pytest.raises(ValueError, match="magic"):
        icns_entries(b"icnx" + GOOD_ICNS[4:])
    with pytest.raises(ValueError, match="header says"):
        icns_entries(GOOD_ICNS + b"\x00")
    broken = bytearray(GOOD_ICNS)
    broken[12:16] = struct.pack(">I", 4)
    with pytest.raises(ValueError, match="bad length"):
        icns_entries(bytes(broken))


def test_icns_problems_names_a_missing_or_wrong_size() -> None:
    assert icns_problems(GOOD_ICNS) == []
    assert icns_problems(icns({"ic08": png(256), "ic09": png(512)})) == [
        "cmd.icns: no ic10 entry; want 1024x1024 for Finder and the Dock"
    ]
    assert icns_problems(icns({"ic08": png(256), "ic09": png(512), "ic10": png(512)})) == [
        "cmd.icns: ic10 is (512, 512); want 1024x1024"
    ]
    assert icns_problems(b"nope") == ["cmd.icns: not an ICNS file: the magic is not 'icns'"]


def lay_out(app: Path, *, uv: bool) -> None:
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir()
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(GOOD_PLIST))
    (app / "Contents" / "Resources" / "cmd.icns").write_bytes(GOOD_ICNS)
    names = ["cmd", "uv"] if uv else ["cmd"]
    for name in names:
        (macos / name).write_text("#!/bin/sh\n")
        (macos / name).chmod(0o755)


def test_a_laid_out_bundle_passes_and_each_gap_is_named(tmp_path: Path) -> None:
    app = tmp_path / "cmd.app"
    lay_out(app, uv=True)
    assert layout_problems(app, with_uv=True) == []
    assert main([str(app)]) == 0

    (app / "Contents" / "MacOS" / "uv").chmod(0o644)
    assert layout_problems(app, with_uv=True) == [
        "Contents/MacOS/uv is not an executable file; plugins run on it"
    ]
    assert layout_problems(app, with_uv=False) == []
    assert main([str(app)]) == 1
    assert main([str(app), "--without-uv"]) == 0

    (app / "Contents" / "Resources" / "cmd.icns").unlink()
    (app / "Contents" / "Info.plist").write_text("not a plist")
    problems = layout_problems(app, with_uv=False)
    assert problems[0].startswith("Info.plist: cannot read")
    assert problems[1] == "Contents/Resources/cmd.icns is missing; Finder shows a blank icon"


def test_main_refuses_a_bad_command_line(tmp_path: Path) -> None:
    assert main([]) == 2
    assert main([str(tmp_path), "--colour"]) == 2
