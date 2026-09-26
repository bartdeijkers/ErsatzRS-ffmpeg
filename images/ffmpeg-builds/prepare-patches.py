#!/usr/bin/env python3
"""Wire reviewed FFmpeg patches into the pinned BtbN build script."""
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 3 or sys.argv[2] not in ("linux64", "win64"):
    raise SystemExit("usage: prepare-patches.py BUILD_TREE {linux64|win64}")
work = Path(sys.argv[1]).resolve()
platform = sys.argv[2]
script = work / "build.sh"
text = script.read_text()
anchor = "    cd ffmpeg\n"
mount = '-v "$BUILD_SCRIPT":/build.sh'
if text.count(anchor) != 1 or text.count(mount) != 1:
    raise SystemExit("Pinned BtbN build.sh changed; review patch integration")
# The generated build script is an expanding heredoc. Preserve its loop variable.
apply = r"""    for patch in /ersatzrs-patches/*.patch; do
        git apply --check "\$patch"
        git apply "\$patch"
    done
"""
text = text.replace(anchor, anchor + apply)
text = text.replace(mount, mount + ' -v "$PWD/ersatzrs-patches":/ersatzrs-patches:ro')
patches = Path(__file__).parent / "patches"
shutil.copytree(patches / "common", work / "ersatzrs-patches")
if platform == "win64":
    shutil.copy2(patches / "0001-vulkan-cuda-export.patch", work / "ersatzrs-patches")
script.write_text(text)
