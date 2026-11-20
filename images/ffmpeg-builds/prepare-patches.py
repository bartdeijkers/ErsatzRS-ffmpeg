#!/usr/bin/env python3
"""Wire reviewed FFmpeg patches into the pinned BtbN build script."""
import shutil
import sys
from pathlib import Path

FFMPEG_REVISION = "74e4393595cf2b5857f0da925c4e0dd74ea306e5"
PLATFORMS = ("linux64", "linuxarm64", "linuxarmv7", "win64")

# These changes are present in n9.1. Keep the historical common inputs for
# the separately pinned macOS recipe.
UPSTREAMED = (
    "0014-openapv-api.patch",
    "0016-webp-animation-metadata-read.patch",
    "0017-revert-decoder-output-throttling.patch",
    "0023-avcodec-qsvdec-fix-av1-duplicate-hdr-side-data.patch",
)


def stage_patches(destination: Path, platform: str) -> None:
    patches = Path(__file__).parent / "patches"
    shutil.copytree(patches / "common", destination)
    for name in UPSTREAMED:
        (destination / name).unlink()
    for patch in (patches / "9.1" / "common").glob("*.patch"):
        if not (destination / patch.name).is_file():
            raise SystemExit(f"Unexpected n9.1 patch replacement: {patch.name}")
        shutil.copy2(patch, destination)
    if platform == "win64":
        for patch in (patches / "windows").glob("*.patch"):
            shutil.copy2(patch, destination)
    elif platform == "linuxarm64":
        # The Rockchip pipeline extends the pixel-format ABI for this RID.
        for patch in (patches / "linuxarm64").glob("*.patch"):
            shutil.copy2(patch, destination)


args = sys.argv[1:]
stage_only = args[:1] == ["--stage"]
if stage_only:
    args = args[1:]
targets = (*PLATFORMS, "common") if stage_only else PLATFORMS
if len(args) != 2 or args[1] not in targets:
    raise SystemExit(
        "usage: prepare-patches.py [--stage] DIRECTORY PLATFORM (or common for --stage)"
    )
work = Path(args[0]).resolve()
platform = args[1]
if stage_only:
    stage_patches(work, platform)
    raise SystemExit(0)

script = work / "build.sh"
text = script.read_text()
vars_anchor = 'source util/vars.sh\n'
if text.count(vars_anchor) != 1:
    raise SystemExit("Pinned BtbN variable setup changed; review image override")
text = text.replace(vars_anchor, vars_anchor + 'IMAGE="${FFBUILD_IMAGE_OVERRIDE:-$IMAGE}"\n')
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
verify_revision = rf'    test "\$(git rev-parse HEAD)" = {FFMPEG_REVISION}' + "\n"
text = text.replace(anchor, anchor + verify_revision + apply)
text = text.replace(mount, mount + ' -v "$PWD/ersatzrs-patches":/ersatzrs-patches:ro')
stage_patches(work / "ersatzrs-patches", platform)
script.write_text(text)
