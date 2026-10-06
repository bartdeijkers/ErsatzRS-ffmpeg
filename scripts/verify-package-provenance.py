#!/usr/bin/env python3
"""Verify exact v2.0.6 candidate archives without rebuilding or publishing.

An external manifest digest pins the inventory before execution. Embedded
records identify source and patch inputs, not the later verification commit
as the binary build origin.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile

VERSION = "2.0.6"
SOURCE = "d32b387f2b0a484599d4587d651891f0c63c4238"
BUILDS_SOURCE = "d04d5526084bb699ca2b400c32bbab7eb3ebcb4e"
RUNTIME_BASE = "bf3db00fd5a879c15e0d065e2871d1a749be86da"
RIDS = {"linux-x64", "linux-arm64", "linux-arm", "win-x64"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def expected_patches(rid):
    folders = [ROOT / "images/ffmpeg-builds/patches/common"]
    if rid == "win-x64":
        folders.append(ROOT / "images/ffmpeg-builds/patches/windows")
    return {p.relative_to(ROOT).as_posix(): digest(p)
            for folder in folders for p in folder.glob("*.patch")}


def load_manifest(path, expected_hash):
    require(HEX.fullmatch(expected_hash), "manifest_sha256 must be 64 lowercase hex characters")
    require(digest(path) == expected_hash, "candidate manifest checksum mismatch")
    manifest = json.loads(path.read_text())
    require(manifest.get("schema_version") == 1, "unsupported manifest schema")
    require(manifest.get("version") == VERSION, "candidate version must be 2.0.6")
    require(manifest.get("ffmpeg_source") == SOURCE, "unexpected FFmpeg source revision")
    packages = manifest.get("packages")
    require(isinstance(packages, list) and len(packages) == len(RIDS), "four packages are required")
    require({p.get("rid") for p in packages} == RIDS, "package RID inventory mismatch")
    for package in packages:
        rid = package["rid"]
        suffix = ".zip" if rid == "win-x64" else ".tar.gz"
        require(package.get("archive") == f"ersatzrs-ffmpeg-{VERSION}-{rid}{suffix}", "unexpected archive name")
        require(isinstance(package.get("sha256"), str) and HEX.fullmatch(package["sha256"]), "invalid archive checksum")
        executables = package.get("executables", {})
        require(set(executables) == {"ffmpeg", "ffprobe"}, "executable checksums must cover both tools")
        require(all(isinstance(v, str) and HEX.fullmatch(v) for v in executables.values()), "invalid executable checksum")
        patches = package.get("patches")
        require(isinstance(patches, list), "missing patch input inventory")
        actual = {p["path"]: p["sha256"] for p in patches}
        require(len(actual) == len(patches), "duplicate patch input")
        require(actual == expected_patches(rid), f"{rid} patch inputs differ from the verification checkout")
    return manifest


def safe_member(name, package_root):
    require("\\" not in name and ":" not in name, "non-portable archive path")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe archive path")
    require(path.parts and path.parts[0] == package_root, "archive layout has an unexpected root")
    return path


def extract(archive, output, package_root):
    require(not output.exists(), "extraction directory already exists")
    output.mkdir(parents=True)
    names = set()

    def destination(name):
        path = safe_member(name, package_root)
        require(path.as_posix() not in names, "duplicate archive member")
        names.add(path.as_posix())
        return output.joinpath(*path.parts)

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                target = destination(member.filename)
                mode = member.external_attr >> 16
                require(mode & 0o170000 != 0o120000, "archive symlinks are forbidden")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(member) as data, target.open("wb") as dest:
                        shutil.copyfileobj(data, dest)
    else:
        with tarfile.open(archive, "r:gz") as source:
            for member in source:
                target = destination(member.name)
                require(member.isdir() or member.isfile(), "archive links or special files are forbidden")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as data, target.open("wb") as dest:
                        shutil.copyfileobj(data, dest)
                    target.chmod(member.mode & 0o777)
    return output / package_root


def verify_layout(root, package):
    suffix = ".exe" if package["rid"] == "win-x64" else ""
    for tool in ("ffmpeg", "ffprobe"):
        executable = root / (tool + suffix)
        require(executable.is_file(), f"missing top-level {tool}")
        require(digest(executable) == package["executables"][tool], f"{tool} checksum mismatch")
        with executable.open("rb") as binary:
            header = binary.read(64)
            if package["rid"] == "win-x64":
                require(header[:2] == b"MZ", f"{tool} is not a PE executable")
                binary.seek(struct.unpack_from("<I", header, 60)[0])
                pe = binary.read(6)
                require(pe[:4] == b"PE\0\0" and struct.unpack_from("<H", pe, 4)[0] == 0x8664,
                        f"{tool} is not Windows AMD64")
            else:
                require(header[:4] == b"\x7fELF" and header[5] == 1, f"{tool} is not little-endian ELF")
                machine, elf_class = {"linux-x64": (62, 2), "linux-arm64": (183, 2), "linux-arm": (40, 1)}[package["rid"]]
                require(header[4] == elf_class and struct.unpack_from("<H", header, 18)[0] == machine,
                        f"{tool} architecture does not match its RID")
    require(not any(p.name.lower().endswith(".dll") or ".so" in p.name.lower()
                    for p in root.rglob("*") if p.is_file()), "unexpected shared library in static package")
    source = json.loads((root / "build-info/source.json").read_text())
    require(source.get("ffmpeg_commit") == SOURCE, "embedded FFmpeg source pin differs")
    require(source.get("candidate_version") == VERSION, "embedded candidate version differs")
    require(source.get("rid") == package["rid"], "embedded package RID differs")
    require(source.get("ffmpeg_builds_commit") == BUILDS_SOURCE, "embedded FFmpeg-Builds source differs")
    require(source.get("runtime_repository_base") == RUNTIME_BASE, "embedded runtime repository base differs")
    build_inputs = root / "build-info/build-inputs.sha256"
    require(digest(build_inputs) == source.get("build_input_manifest_sha256"), "embedded build input manifest checksum differs")
    inputs = {}
    for line in build_inputs.read_text().splitlines():
        checksum, filename = line.split(maxsplit=1)
        filename = filename.lstrip("*")
        path = PurePosixPath(filename)
        require(HEX.fullmatch(checksum) and not path.is_absolute() and ".." not in path.parts
                and "\\" not in filename and ":" not in filename, "invalid build input record")
        require(filename not in inputs, "duplicate build input record")
        inputs[filename] = checksum
    expected_inputs = {p.relative_to(ROOT).as_posix(): digest(p)
                       for p in (ROOT / "images").rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    require(inputs == expected_inputs, "embedded build inputs differ from verification checkout")
    embedded = {}
    for line in (root / "build-info/patches.sha256").read_text().splitlines():
        checksum, filename = line.split(maxsplit=1)
        filename = filename.lstrip("*")
        require(HEX.fullmatch(checksum) and filename == Path(filename).name, "invalid embedded patch checksum")
        require(filename not in embedded, "duplicate embedded patch checksum")
        embedded[filename] = checksum
    expected = {Path(p["path"]).name: p["sha256"] for p in package["patches"]}
    require(embedded == expected, "embedded applied patch inventory differs")


def execute(tool, *arguments):
    result = subprocess.run([str(tool), *arguments], capture_output=True, timeout=60)
    require(result.returncode == 0, f"{tool.name} exited {result.returncode}: {result.stderr.decode(errors='replace')}")
    return result.stdout + result.stderr


def verify_runtime(root):
    suffix = ".exe" if os.name == "nt" else ""
    ffmpeg = root / ("ffmpeg" + suffix)
    for name in ("ffmpeg", "ffprobe"):
        output = execute(root / (name + suffix), "-version").decode(errors="replace")
        require(re.match(rf"{name} version n?9\.0(?:\D|$)", output), f"{name} is not FFmpeg 9.0")
    filters = execute(ffmpeg, "-hide_banner", "-filters").decode(errors="replace")
    for name in ("drawvg", "drawtext"):
        require(re.search(rf"\s{name}\s", filters), f"missing {name} filter")
    configuration = execute(ffmpeg, "-hide_banner", "-buildconf").decode(errors="replace")
    for flag in ("librsvg", "cairo", "fontconfig", "libfreetype", "libharfbuzz", "libfribidi"):
        require(f"--enable-{flag}" in configuration, f"missing --enable-{flag}")
    with tempfile.TemporaryDirectory(prefix="ersatzrs-drawtext-") as directory:
        work = Path(directory)

        def render(arguments):
            result = subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", *arguments],
                                    cwd=work, capture_output=True, timeout=60)
            require(result.returncode == 0, f"FFmpeg software graphics/codec proof failed: {result.stderr.decode(errors='replace')}")
            return result.stdout

        pixels = render(["-f", "lavfi", "-i", "color=black:s=64x48:d=1",
                         "-vf", "drawvg=rect 8 8 16 16 setcolor red fill",
                         "-frames:v", "1", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"])
        require(len(pixels) == 64 * 48 * 4, "drawvg decoded frame dimensions differ")
        red_offset = (12 * 64 + 12) * 4
        require(tuple(pixels[red_offset:red_offset + 4]) == (255, 0, 0, 255), "drawvg red square did not render")
        require(tuple(pixels[:4]) == (0, 0, 0, 255), "drawvg changed the untouched background")
        font = Path(os.environ["WINDIR"]) / "Fonts/arial.ttf" if os.name == "nt" else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        shutil.copyfile(font, work / "font.ttf")
        (work / "text.txt").write_text("ErsatzRS", encoding="utf-8")
        pixels = render(["-f", "lavfi", "-i", "color=c=black:s=256x64:d=0.1",
            "-vf", "drawtext=fontfile=font.ttf:textfile=text.txt:reload=1:fontcolor=white:fontsize=32:x=4:y=4,format=rgb24",
            "-frames:v", "1", "-f", "rawvideo", "pipe:1"])
        require(len(pixels) == 256 * 64 * 3 and sum(v > 30 for v in pixels) > 600, "drawtext glyphs are missing")
        for encoder, options in (("librav1e", ["-speed", "10"]),
                                 ("libsvtav1", ["-preset", "12", "-svtav1-params", "lp=1"])):
            clip = encoder + ".ivf"
            render(["-f", "lavfi", "-i", "testsrc2=s=64x64:r=2:d=1", "-frames:v", "2",
                    "-c:v", encoder, *options, "-threads", "2", clip])
            decoded = render(["-i", clip, "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
            require(len(decoded) == 64 * 64 * 3 * 2, f"{encoder} did not round-trip two AV1 frames")
    print(json.dumps({"runtime": "passed", "version": "9.0", "drawtext": "decoded file-backed glyphs",
                      "drawvg_red_square": "passed", "rav1e_decoded_frames": 2, "svtav1_decoded_frames": 2}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("download")
    download.add_argument("--candidate-tag", required=True)
    download.add_argument("--manifest-sha256", required=True)
    download.add_argument("--repo", required=True)
    download.add_argument("--rid", choices=sorted(RIDS), required=True)
    download.add_argument("--output", type=Path, required=True)
    runtime = sub.add_parser("runtime")
    runtime.add_argument("package_root", type=Path)
    args = parser.parse_args()
    if args.command == "runtime":
        verify_runtime(args.package_root.resolve())
        return
    require(re.fullmatch(r"runtime-candidate-2\.0\.6-[0-9a-f]{8,40}", args.candidate_tag), "unexpected candidate tag")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo), "invalid repository")
    output = args.output.resolve()
    require(not output.exists(), "candidate output directory already exists")
    output.mkdir(parents=True)

    def download_asset(name):
        subprocess.run(["gh", "release", "download", args.candidate_tag,
                        "--repo", args.repo, "--pattern", name, "--dir", str(output)],
                       check=True, timeout=300)
        return output / name

    manifest = load_manifest(download_asset("candidate-manifest.json"), args.manifest_sha256)
    package = next(p for p in manifest["packages"] if p["rid"] == args.rid)
    archive = download_asset(package["archive"])
    require(digest(archive) == package["sha256"], "archive checksum mismatch")
    package_root = f"ersatzrs-ffmpeg-{VERSION}-{args.rid}"
    root = extract(archive, output / "expanded", package_root)
    verify_layout(root, package)
    print(json.dumps({"rid": args.rid, "archive_sha256": package["sha256"],
                      "ffmpeg_source": SOURCE, "patch_inputs": "verified", "package_root": root.name}))


if __name__ == "__main__":
    main()
