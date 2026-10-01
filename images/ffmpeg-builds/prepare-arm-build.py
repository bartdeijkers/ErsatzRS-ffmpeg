#!/usr/bin/env python3
"""Prepare the pinned BtbN source for the reviewed ARM FFmpeg package build."""
import subprocess
import sys
from pathlib import Path

BUILDS_REVISION = "d04d5526084bb699ca2b400c32bbab7eb3ebcb4e"
FFMPEG_REVISION = "d32b387f2b0a484599d4587d651891f0c63c4238"

if len(sys.argv) != 3 or sys.argv[2] not in ("linuxarm64", "linuxarmv7"):
    raise SystemExit("usage: prepare-arm-build.py BUILD_TREE {linuxarm64|linuxarmv7}")
work = Path(sys.argv[1]).resolve()
target = sys.argv[2]
revision = subprocess.check_output(
    ["git", "-C", str(work), "rev-parse", "HEAD"], text=True
).strip()
if revision != BUILDS_REVISION:
    raise SystemExit("Unexpected FFmpeg-Builds revision; review the recipe first")
subprocess.run(
    [sys.executable, str(Path(__file__).with_name("prepare-patches.py")), str(work), target],
    check=True,
)
script = work / "build.sh"
text = script.read_text()
replacements = {
    "git clone --filter=blob:none --branch=": "git clone --depth=1 --branch=",
    "    cd ffmpeg\n": (
        "    cd ffmpeg\n"
        f'    test "\\$(git rev-parse HEAD)" = {FFMPEG_REVISION}\n'
    ),
    "./configure --prefix=": "./configure --enable-cairo --prefix=",
    "make -j\\$(nproc) V=1": "make -j4 V=1",
    "xz -T0": "xz -T2",
}
# The dependency image exports codec flags separately from compiler defaults.
# FFmpeg also applies extra C flags to its assembler probes on ARM.
if target == "linuxarmv7":
    # FFmpeg 9 explicitly excludes ARM32 from NVIDIA's codec backend.
    replacements['--cc="\\$CC"'] = (
        '--disable-ffnvcodec --disable-cuda-llvm --cc="\\$CC"'
    )
    # Static codec probes need libm after their archives, not only in LDFLAGS.
    replacements['--extra-libs="\\$FF_LIBS"'] = '--extra-libs="\\$FF_LIBS -lm"'
    for option, variable in (
        ("cflags", "FF_CFLAGS"),
        ("cxxflags", "FF_CXXFLAGS"),
        ("ldflags", "FF_LDFLAGS"),
    ):
        old = f'--extra-{option}="\\${variable}"'
        replacements[old] = (
            f'--extra-{option}="\\${variable} -mfpu=vfpv3-d16 -mfloat-abi=hard"'
        )
for old, new in replacements.items():
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected build script anchor: {old!r}")
    text = text.replace(old, new)
script.write_text(text)
