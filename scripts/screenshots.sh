#!/usr/bin/env bash
# Take the user documentation's screenshots of the launcher, docs/assets/screenshots/*.png,
# from the real app: built for Linux in a scratch workspace (scripts/linux-app-workspace.sh),
# run on a virtual X display with the repository's own plugins, and typed into with xdotool.
#
# These are Linux renderings. On macOS the window is translucent with a blur behind it and
# uses the system font. Here a software Vulkan driver (lavapipe) draws it and no compositor
# blends it, so the translucent tint comes out as the flat grey the X server makes of it,
# and the text is in whichever sans-serif font fontconfig picks. Each image is the window
# alone, cut to its rounded shape, at twice its size in points as a Retina display draws it.
#
#   scripts/screenshots.sh [WORKSPACE]    WORKSPACE as for scripts/linux-app-workspace.sh
#
# Needs Linux, cargo, uv, python3 and
#   apt-get install xvfb xdotool x11-apps imagemagick mesa-vulkan-drivers
# The first build in a new workspace takes minutes and several gigabytes of disk; after
# that a run takes under a minute.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
workspace="${1:-${TMPDIR:-/tmp}/cmd-linux-app}"
out="$repo/docs/assets/screenshots"
# Twice the window's size in points, so the images stay sharp at the width the
# documentation shows them.
scale=2

step() { printf '\n== %s\n' "$*"; }

if [[ "$(uname)" != "Linux" ]]; then
  echo "screenshots.sh runs the app under Xvfb, so it runs on Linux only" >&2
  exit 1
fi
missing=()
for tool in Xvfb xdotool xwd convert identify python3 cargo uv; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
icd="$(compgen -G '/usr/share/vulkan/icd.d/lvp_icd*.json' | head -n 1 || true)"
[[ -n "$icd" ]] || missing+=("lavapipe")
if ((${#missing[@]})); then
  echo "missing: ${missing[*]}" >&2
  echo "apt-get install xvfb xdotool x11-apps imagemagick mesa-vulkan-drivers" >&2
  exit 1
fi

step "the app, built in the scratch workspace"
"$repo/scripts/linux-app-workspace.sh" "$workspace"
workspace="$(realpath "$workspace")"
# Debug, sharing its dependencies' builds with `cargo test` there: a release build would
# add gigabytes of disk for a window that looks the same.
(cd "$workspace" && cargo build -p cmd-app)
app="$workspace/target/debug/cmd"

work="$(mktemp -d "${TMPDIR:-/tmp}/cmd-screenshots.XXXXXX")"
xvfb_pid=""
app_pid=""
# Stop what this started. On failure the app's output and its last frame stay behind.
cleanup() {
  local status=$?
  if [[ -n "$app_pid" ]]; then
    # The plugins go with it: they exit when their stdin closes.
    kill "$app_pid" 2>/dev/null || true
    wait "$app_pid" 2>/dev/null || true
  fi
  if [[ -n "$xvfb_pid" ]]; then
    kill "$xvfb_pid" 2>/dev/null || true
    wait "$xvfb_pid" 2>/dev/null || true
  fi
  if ((status == 0)); then
    rm -rf "$work"
  else
    if [[ -s "$work/frame.xwd" ]]; then
      convert "xwd:$work/frame.xwd" "$work/last-frame.png" 2>/dev/null || true
    fi
    echo "failed; the app's output (app.log) and its last frame (last-frame.png) are in $work" >&2
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Frames are read from xwd dumps because xwd keeps the window's alpha channel, which
# ImageMagick's own capture drops.
cat >"$work/frame.py" <<'PY'
"""Reads an xwd dump of the launcher window.

look DUMP SCALE  prints "drawn status row digest":
    drawn   1 once the window has been drawn
    status  0 when the line under the input is empty, 1 when it says something in the
            muted colour (starting, waiting), 2 when in the warning colour (an error)
    row     1 when there is a first result row
    digest  of every pixel, to tell when the window has stopped changing
cut DUMP RAW     writes the window as straight RGBA to RAW and prints WIDTHxHEIGHT
"""

import hashlib
import struct
import sys
from collections import Counter
from pathlib import Path

# INPUT_HEIGHT, STATUS_HEIGHT and ROW_HEIGHT in crates/cmd-app/src/main.rs, in points.
INPUT, STATUS, ROW = 56, 24, 48
# GPUI gives a translucent window a 32-bit visual: blue, green, red, then alpha.
BGRA = (32, 32, 0, (0xFF0000, 0xFF00, 0xFF))
# The warning colours are orange, with far more red than blue; the muted grey has as much
# blue as red. More than a few orange pixels make the line a warning.
ORANGE = 64
ORANGE_PIXELS = 20


def load(path: str) -> tuple[int, int, list[bytes]]:
    """Read the dump's width, height and rows of BGRA pixels."""
    data = Path(path).read_bytes()
    header = struct.unpack(">25I", data[:100])
    size, depth, width, height = header[0], header[3], header[4], header[5]
    byte_order, bits_per_pixel, stride, ncolors = header[7], header[11], header[12], header[19]
    if (depth, bits_per_pixel, byte_order, header[14:17]) != BGRA:
        sys.exit(f"{path}: not the 32-bit BGRA window this reads")
    start = size + ncolors * 12
    rows = [data[start + y * stride : start + y * stride + width * 4] for y in range(height)]
    return width, height, rows


def look(path: str, scale: int) -> None:
    """Print what the window shows, as the module's docstring says."""
    width, height, rows = load(path)
    # Nothing is drawn in the outer 8 points of the window's sides: this pixel is the tint.
    x = (width - 4 * scale) * 4
    tint = rows[height // 2][x : x + 4]
    # Before the first frame the window is empty, or shows the swapchain's first image,
    # opaque black; a frame of the launcher has a tint and transparent rounded corners.
    if tint[3] == 0 or rows[0][3] != 0:
        sys.stdout.write("0 0 0 -\n")
        return

    def strip(top: int, bottom: int) -> bytes:
        return b"".join(rows[top * scale : bottom * scale])

    def blank(pixels: bytes) -> bool:
        return pixels == tint * (len(pixels) // 4)

    line = strip(INPUT, INPUT + STATUS)
    if blank(line):
        said = 0
    else:
        orange = sum(1 for i in range(0, len(line), 4) if line[i + 2] - line[i] > ORANGE)
        said = 2 if orange > ORANGE_PIXELS else 1
    row = 0 if blank(strip(INPUT + STATUS, INPUT + STATUS + ROW)) else 1
    digest = hashlib.sha256(b"".join(rows)).hexdigest()
    sys.stdout.write(f"1 {said} {row} {digest}\n")


def cut(path: str, raw: str) -> None:
    """Write the window to RAW as straight RGBA, cut to its shape, and print its size."""
    width, height, rows = load(path)
    pixels = b"".join(rows)
    # Without a compositor the X server shows a window's pixels with the alpha ignored, so
    # the tint, stored premultiplied, shows as itself over black. That is kept inside the
    # window's shape and the outside made transparent: a pixel's alpha becomes its
    # coverage, its alpha over the tint's, and its colour is divided by that coverage so
    # the antialiased corners keep the tint's colour rather than darken towards black.
    tint_alpha = Counter(pixels[3::4]).most_common(1)[0][0]
    straight = bytearray(len(pixels))
    for i in range(0, len(pixels), 4):
        blue, green, red, alpha = pixels[i : i + 4]
        if alpha:
            coverage = min(1.0, alpha / tint_alpha)
            straight[i : i + 4] = bytes((
                min(255, round(red / coverage)),
                min(255, round(green / coverage)),
                min(255, round(blue / coverage)),
                round(coverage * 255),
            ))
    Path(raw).write_bytes(straight)
    sys.stdout.write(f"{width}x{height}\n")


if sys.argv[1] == "look":
    look(sys.argv[2], int(sys.argv[3]))
else:
    cut(sys.argv[2], sys.argv[3])
PY

step "a virtual display, drawn by lavapipe"
# -displayfd: Xvfb takes a free display number and writes it once it accepts clients.
# 2400x1600 is 1200x800 points at scale 2, room for the 680x420 window.
Xvfb -displayfd 3 -screen 0 2400x1600x24 -nolisten tcp 3>"$work/display" 2>"$work/xvfb.log" &
xvfb_pid=$!
for _ in $(seq 100); do
  [[ -s "$work/display" ]] && break
  sleep 0.1
done
if [[ ! -s "$work/display" ]]; then
  echo "Xvfb did not start:" >&2
  cat "$work/xvfb.log" >&2
  exit 1
fi
DISPLAY=":$(cat "$work/display")"
export DISPLAY
echo "display $DISPLAY, Vulkan driver $icd"

step "the app, with the repository's plugins"
# WAYLAND_DISPLAY: GPUI would choose Wayland over X11.
# DBUS_SESSION_BUS_ADDRESS: GPUI asks the desktop portal on the session bus whether the
#   desktop is light or dark. Pointed at no bus, it draws the light palette on any machine.
# UV_LOCKED: every plugin starts through `uv run`, which would rewrite a stale uv.lock;
#   this way it stops with an error instead, so a run changes no tracked file but the
#   screenshots.
env -u WAYLAND_DISPLAY \
  DBUS_SESSION_BUS_ADDRESS="unix:path=$work/no-bus" \
  VK_ICD_FILENAMES="$icd" \
  GPUI_X11_SCALE_FACTOR="$scale" \
  CMD_PLUGINS="$repo/plugins" \
  UV_LOCKED=1 \
  "$app" >"$work/app.log" 2>&1 </dev/null &
app_pid=$!

# The launcher has no title bar, so no title to search for; GPUI marks it with the pid.
window=""
deadline=$((SECONDS + 60))
until window="$(xdotool search --onlyvisible --pid "$app_pid" 2>/dev/null | head -n 1)" && [[ -n "$window" ]]; do
  if ! kill -0 "$app_pid" 2>/dev/null || ((SECONDS >= deadline)); then
    echo "the launcher window did not appear" >&2
    exit 1
  fi
  sleep 0.05
done
# Focusing the window does two jobs. GPUI 0.2.2 reads X events when its connection has new
# data, and the events of the window's first map arrive while it waits for the reply to a
# request sent just after it, so they sit unread and nothing is drawn until some other
# event comes. A window manager would always send one; here the FocusIn is that event. And
# with no window manager, nothing else would give the window the keyboard.
timeout 20 xdotool windowfocus --sync "$window"
echo "window $window, focused"

# Dump the window as it is now and print what the helper sees in it.
look() {
  if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "the app exited:" >&2
    cat "$work/app.log" >&2
    exit 1
  fi
  xwd -id "$window" -silent >"$work/frame.xwd"
  python3 -I "$work/frame.py" look "$work/frame.xwd" "$scale"
}

# Wait until the window has been drawn, the line under the input is empty, there is a
# first result row or not as $1 says, and four dumps in a row are the same: by then every
# plugin has answered. A minute allows for a plugin's first `uv run` building its
# environment.
settle() {
  local rows="$1" what="$2" last="" same=0 frame drawn status row digest
  local deadline=$((SECONDS + 60))
  while ((SECONDS < deadline)); do
    frame="$(look)"
    read -r drawn status row digest <<<"$frame"
    if [[ "$status" == 2 ]]; then
      echo "the launcher shows an error while waiting for $what" >&2
      exit 1
    fi
    if [[ "$drawn$status$row" == "10$rows" && "$digest" == "$last" ]]; then
      ((++same < 3)) || return 0
    else
      same=0
    fi
    last="$digest"
    sleep 0.3
  done
  echo "timed out waiting for $what" >&2
  exit 1
}

# Write the frame last dumped as $1.png, cut to the window's shape, without metadata.
shoot() {
  local file="$out/$1.png" size
  size="$(python3 -I "$work/frame.py" cut "$work/frame.xwd" "$work/frame.rgba")"
  convert -size "$size" -depth 8 "rgba:$work/frame.rgba" -strip "$file"
  if (($(stat -c %s "$file") > 300 * 1024)); then
    # Kept small for the documentation; half the size is the window's size in points.
    convert "$file" -resize 50% -strip "$file"
  fi
  printf '  %-22s %s, %s KB\n' "$1.png" "$(identify -format '%wx%h' "$file")" "$(($(stat -c %s "$file") / 1024))"
}

# Clear the query, then type one and wait for its answers. On Linux GPUI cannot hide a
# window, so Escape empties the launcher and leaves it on screen with the keyboard.
ask() {
  xdotool key Escape
  settle 0 "the query to clear"
  xdotool type --delay 50 -- "$1"
  settle 1 "the answers to '$1'"
}

step "the screenshots, into ${out#"$repo/"}"
mkdir -p "$out"
# The first frame, taken as soon as there is one: once uv has their environment the
# plugins are all up within a second of launch, so only the first few frames show the
# starting line, and on a fast enough machine perhaps none.
deadline=$((SECONDS + 30))
while :; do
  frame="$(look)"
  read -r drawn status _ _ <<<"$frame"
  [[ "$drawn" == 1 ]] && break
  if ((SECONDS >= deadline)); then
    echo "the window was never drawn" >&2
    exit 1
  fi
done
case "$status" in
  1) shoot launcher-starting ;;
  0) echo "  launcher-starting.png  not taken: the plugins were up before the first frame" ;;
  *)
    echo "the launcher's first frame shows an error" >&2
    exit 1
    ;;
esac

settle 0 "the plugins to start"
shoot launcher-empty
ask "2 + 2 * 3"
shoot calculator
ask "web rust gpui"
shoot websearch
ask "dark"
shoot system

echo "done"
