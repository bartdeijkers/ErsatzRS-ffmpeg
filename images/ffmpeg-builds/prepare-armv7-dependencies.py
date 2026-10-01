#!/usr/bin/env python3
"""Add static ARMv7 recipes to the pinned BtbN dependency tree."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: prepare-armv7-dependencies.py BUILD_TREE BASE_IMAGE_ID")
work = Path(sys.argv[1]).resolve()
image = sys.argv[2]
if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
    raise SystemExit("Pass the exact local base image SHA-256 ID")
revision = subprocess.check_output(
    ["git", "-C", str(work), "rev-parse", "HEAD"], text=True
).strip()
if revision != "d04d5526084bb699ca2b400c32bbab7eb3ebcb4e":
    raise SystemExit("Unexpected FFmpeg-Builds revision")
source = Path(__file__).parent
shutil.copy2(work / "variants/linuxarm64-gpl.sh", work / "variants/linuxarmv7-gpl.sh")
shutil.copytree(source / "armv7-toolchain", work / "images/base-linuxarmv7")
for recipe in (source / "scripts.d").glob("*.sh"):
    shutil.copy2(recipe, work / "scripts.d" / recipe.name)
final = work / "scripts.d/zz-final.sh"
text = final.read_text()
if text.count("    echo rpath\n") != 1:
    raise SystemExit("Unexpected final dependency list")
final.write_text(text.replace("    echo rpath\n", "    echo cairo\n    echo rpath\n"))
for recipe in (work / "scripts.d").rglob("*.sh"):
    recipe.write_text(recipe.read_text().replace("$(nproc)", "4"))

# These upstream recipes enumerate architectures instead of using the compiler
# target. Preserve the ARM64 behavior and add the corresponding ARMv7 settings.
for name, old, new in (
    ("25-openssl.sh", "linux-aarch64", "linux-armv4"),
    ("50-libvpx.sh", "arm64-linux-gcc", "armv7-linux-gcc"),
    ("50-openh264.sh", "ARCH=aarch64", "ARCH=arm"),
):
    recipe = work / "scripts.d" / name
    text = recipe.read_text()
    start = text.index("    elif [[ $TARGET == linuxarm64 ]]; then\n")
    end = text.index("    else\n", start)
    armv7 = text[start:end].replace("linuxarm64", "linuxarmv7").replace(old, new)
    recipe.write_text(text[:end] + armv7 + text[end:])
for recipe in (work / "scripts.d/45-x11").glob("*.sh"):
    recipe.write_text(recipe.read_text().replace("$TARGET == linuxarm64", "$TARGET == linuxarm*"))
# Match the existing ARM64 exclusion: this import-library recipe targets the
# x86 Linux VAAPI driver installation, not a portable ARM driver stack.
recipe = work / "scripts.d/50-vaapi/50-libva.sh"
recipe.write_text(recipe.read_text().replace("$TARGET == linuxarm64", "$TARGET == linuxarm*"))
# Generalize existing x86-only optimizations/driver exclusions to both ARM
# widths; upstream only had an ARM64 target when these predicates were written.
for name in ("25-fftw3.sh", "50-vidstab.sh", "50-onevpl.sh"):
    recipe = work / "scripts.d" / name
    recipe.write_text(recipe.read_text().replace("*arm64", "*arm*"))
# ARMv7 uses the hard-float baseline without requiring NEON. Keep vvenc's
# portable implementations rather than selecting its unconditional NEON path.
recipe = work / "scripts.d/50-vvenc.sh"
recipe.write_text(recipe.read_text().replace(
    '    cmake -DCMAKE_TOOLCHAIN_FILE=',
    '    [[ $TARGET == linuxarmv7 ]] && armsimd+=( -DVVENC_ENABLE_ARM_SIMD=OFF )\n'
    '    cmake -DCMAKE_TOOLCHAIN_FILE=',
))
# libass has no ARM32 assembly backend. Keep its portable renderer enabled.
recipe = work / "scripts.d/50-libass.sh"
recipe.write_text(recipe.read_text().replace(
    '    meson setup "${myconf[@]}"',
    '    [[ $TARGET == linuxarmv7 ]] && myconf+=( -Dasm=disabled )\n'
    '    meson setup "${myconf[@]}"',
))
# AOM's ARM32 NEON objects do not override the hard-float baseline flags.
# Preserve the encoder/decoder without requiring optional NEON instructions.
recipe = work / "scripts.d/50-aom.sh"
recipe.write_text(recipe.read_text().replace(
    '    cmake -DCMAKE_TOOLCHAIN_FILE=',
    '    local armsimd=()\n'
    '    [[ $TARGET == linuxarmv7 ]] && armsimd+=( -DENABLE_NEON=OFF )\n'
    '    cmake "${armsimd[@]}" -DCMAKE_TOOLCHAIN_FILE=',
))
# The AVS2 recipes advertise ARM assembly objects absent from their pinned
# sources. Retain both codecs using their portable C implementations on ARMv7.
for name in ("50-xavs2.sh", "50-davs2.sh"):
    recipe = work / "scripts.d" / name
    recipe.write_text(recipe.read_text().replace(
        '    ./configure "${myconf[@]}"',
        '    [[ $TARGET == linuxarmv7 ]] && myconf+=(--disable-asm)\n'
        '    ./configure "${myconf[@]}"',
    ))
recipe = work / "scripts.d/50-rav1e.sh"
recipe.write_text(recipe.read_text().replace(
    '    cargo cinstall', '    CARGO_BUILD_JOBS=4 cargo cinstall',
))
(work / ".dockerignore").write_text(
    ".git\nffbuild\nartifacts\n.cache/images\n.cache/layers\n"
)
download = work / "download.sh"
text = download.read_text()
anchor = "for STAGE in scripts.d/*.sh scripts.d/*/*.sh; do\n"
image_anchor = '"${REGISTRY}/${REPO}/base:latest${DOCKER_TAG_SUFFIX:-}"'
if text.count(anchor) != 1 or text.count(image_anchor) != 1:
    raise SystemExit("Unexpected download recipe")
text = text.replace(
    anchor,
    'test -s Dockerfile\n' + anchor + '\tgrep -Fq "SELF=\\"$STAGE\\"" Dockerfile || continue\n',
).replace(image_anchor, f'"{image}"').replace("xz -T0", "xz -T2")
download.write_text(text)
subprocess.run(["bash", "./generate.sh", "linuxarmv7", "gpl", "9.0"], cwd=work, check=True)
