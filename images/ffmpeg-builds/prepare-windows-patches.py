#!/usr/bin/env python3
"""Wire reviewed FFmpeg patches into the pinned BtbN Windows build script."""
import shutil
import sys
from pathlib import Path

work = Path(sys.argv[1]).resolve()
script = work / "build.sh"
text = script.read_text()
anchor = "    cd ffmpeg\n"
mount = '-v "$BUILD_SCRIPT":/build.sh'
if text.count(anchor) != 1 or text.count(mount) != 1:
    raise SystemExit("Pinned BtbN build.sh changed; review patch integration")
# The generated build script is an expanding heredoc. Preserve its loop variable.
apply = r'''    for patch in /ersatzrs-patches/*.patch; do
        git apply --check "\$patch"
        git apply "\$patch"
    done
'''
text = text.replace(anchor, anchor + apply)
text = text.replace(mount, mount + ' -v "$PWD/ersatzrs-patches":/ersatzrs-patches:ro')
shutil.copytree(Path(__file__).parent / "patches", work / "ersatzrs-patches")
script.write_text(text)
