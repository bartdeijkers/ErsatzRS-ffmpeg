#!/usr/bin/env python3
"""Build a relocatable candidate on a native macOS runner, never publish it.

Homebrew supplies the recorded codec/graphics dependencies; libzvbi and FFmpeg
are built from exact Git revisions. dylibbundler owns dylib graph relocation.
Run on an ephemeral runner after installing the dependencies in README.md.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FFMPEG_REVISION = "d32b387f2b0a484599d4587d651891f0c63c4238"
ZVBI_REVISION = "d3a5ee9f2b047bf16cd1ee5ccf6ec05ee75409d0"
DEPENDENCIES = ("cairo", "librsvg", "fontconfig", "freetype", "harfbuzz", "fribidi",
                "libass", "zimg", "svt-av1", "jpeg-xl", "x264", "x265", "libvpx",
                "opus", "openssl@3", "rav1e", "dav1d", "zlib", "bzip2", "expat", "xorgproto")
TOOLS = ("pkgconf", "nasm", "autoconf", "automake", "libtool", "gettext", "dylibbundler")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(arguments, cwd=None, capture=False, timeout=3600, env=None):
    try:
        result = subprocess.run([str(value) for value in arguments], cwd=cwd, env=env,
                                capture_output=capture, check=True, timeout=timeout)
    except subprocess.CalledProcessError as error:
        if capture and error.stderr:
            sys.stderr.write(error.stderr.decode("utf-8", errors="replace"))
        raise
    return result.stdout.decode("utf-8") if capture else ""


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def checkout(repository, revision, destination):
    destination.mkdir()
    run(["git", "init", "-q"], destination)
    run(["git", "remote", "add", "origin", repository], destination)
    run(["git", "fetch", "--depth", "1", "origin", revision], destination)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], destination)
    require(run(["git", "rev-parse", "HEAD"], destination, True).strip() == revision,
            "source checkout differs")


def dependencies(path):
    """Only system paths or explicitly relocated package libraries are accepted."""
    output = run(["otool", "-L", path], capture=True, timeout=30)
    result = []
    for line in output.splitlines()[1:]:
        value, separator, _ = line.strip().partition(" (compatibility version ")
        require(separator, "unrecognized Mach-O dependency output")
        result.append(value)
    return result


def verify_bundle(package, architecture):
    objects = [package / "ffmpeg", package / "ffprobe", *sorted((package / "lib").glob("*.dylib"))]
    require(len(objects) > 2, "bundled dependency closure is missing")
    for path in objects:
        require(not path.is_symlink(), "bundled Mach-O objects must be regular files")
        require(architecture in run(["lipo", "-archs", path], capture=True, timeout=30).split(),
                "Mach-O architecture differs from the selected RID")
        for dependency in dependencies(path):
            if dependency.startswith(("/usr/lib/", "/System/Library/")):
                continue
            prefix = "@executable_path/lib/"
            require(dependency.startswith(prefix), "dependency escapes relocated package")
            name = dependency[len(prefix):]
            require(name == Path(name).name and (package / "lib" / name).is_file(),
                    "relocated dependency is missing")
        run(["codesign", "--verify", "--strict", path], timeout=30)
    return {path.relative_to(package).as_posix(): sha256(path) for path in objects}


def build(args):
    require(platform.system() == "Darwin", "this recipe requires a native macOS runner")
    architecture = {"osx-x64": "x86_64", "osx-arm64": "arm64"}[args.rid]
    require(platform.machine() == architecture, "native runner architecture does not match RID")
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", args.version), "invalid package version")
    require(re.fullmatch(r"[0-9a-f]{40}", args.homebrew_core_revision), "invalid Homebrew core revision")
    require(re.fullmatch(r"[0-9a-f]{40}", args.homebrew_brew_revision), "invalid Homebrew tool revision")
    require(re.fullmatch(r"[0-9a-f]{40}", args.homebrew_cask_revision), "invalid Homebrew cask revision")
    require(re.fullmatch(r"[0-9]+\.[0-9]+", args.deployment_target), "invalid deployment target")
    require(1 <= args.jobs <= 8, "build concurrency must be between one and eight")
    require(not args.work.exists(), "build directory already exists")
    args.work.mkdir(parents=True)
    prefix = args.work / "prefix"
    package = args.work / f"ersatzrs-ffmpeg-{args.version}-{args.rid}"
    brew = shutil.which("brew")
    require(brew, "Homebrew is required on the build runner")
    brew_repository = run([brew, "--repository"], capture=True).strip()
    require(run(["git", "-C", brew_repository, "rev-parse", "HEAD"], capture=True).strip() == args.homebrew_brew_revision,
            "Homebrew tool checkout differs from selected revision")
    core = run([brew, "--repository", "homebrew/core"], capture=True).strip()
    require(run(["git", "-C", core, "rev-parse", "HEAD"], capture=True).strip() == args.homebrew_core_revision,
            "Homebrew core checkout differs from selected dependency recipes")
    cask = run([brew, "--repository", "homebrew/cask"], capture=True).strip()
    require(run(["git", "-C", cask, "rev-parse", "HEAD"], capture=True).strip() == args.homebrew_cask_revision,
            "Homebrew cask checkout differs from selected migration data")
    brew_prefix = Path(run([brew, "--prefix"], capture=True).strip())
    closure = run([brew, "deps", "--installed", "--union", *DEPENDENCIES], capture=True).splitlines()
    formula_names = sorted(set(DEPENDENCIES) | set(closure))
    info = json.loads(run([brew, "info", "--json=v2", *formula_names], capture=True))
    inventory = []
    library_owners = {}
    pkg_config = [prefix / "lib/pkgconfig"]
    for formula in info["formulae"]:
        expected = formula["versions"]["stable"]
        expected += f'_{formula["revision"]}' if formula["revision"] else ""
        selected = [item for item in formula["installed"] if item["version"] == expected]
        require(len(selected) == 1, "installed dependency differs from selected formula")
        installed = selected[0]
        name = formula["name"]
        keg = Path(run([brew, "--prefix", name], capture=True).strip()).resolve()
        require(keg.name == expected, "active dependency keg differs from selected formula")
        for library in keg.rglob("*.dylib"):
            if library.is_file():
                library_owners.setdefault(library.name, set()).add(name)
        pkg_config.extend((keg / "lib/pkgconfig", keg / "share/pkgconfig"))
        inventory.append({"name": name, "version": installed["version"],
                          "license": formula["license"], "source": formula["urls"]["stable"],
                          "bottle": formula.get("bottle"), "keg": keg})
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join([str(brew_prefix / "opt/gettext/bin"), environment["PATH"]])
    environment["PKG_CONFIG_PATH"] = os.pathsep.join(map(str, pkg_config))
    environment["PKG_CONFIG_LIBDIR"] = environment["PKG_CONFIG_PATH"]
    environment["MACOSX_DEPLOYMENT_TARGET"] = args.deployment_target
    # Do not inherit arbitrary user flags or unrecorded library search paths.
    environment.pop("CFLAGS", None)
    environment.pop("CXXFLAGS", None)
    environment.pop("LDFLAGS", None)
    environment.pop("SDKROOT", None)
    environment.pop("CPATH", None)
    environment.pop("LIBRARY_PATH", None)
    zvbi = args.work / "zvbi"
    checkout("https://github.com/zapping-vbi/zvbi", ZVBI_REVISION, zvbi)
    run(["./autogen.sh"], zvbi, env=environment)
    run(["./configure", f"--prefix={prefix}", "--disable-shared", "--enable-static", "--with-pic",
         "--without-doxygen", "--without-x", "--disable-dvb", "--disable-bktr", "--disable-nls",
         "--disable-proxy"], zvbi, env=environment)
    run(["make", "-C", "src", f"-j{args.jobs}"], zvbi, env=environment)
    run(["make", "-C", "src", "install"], zvbi, env=environment)
    run(["make", "SUBDIRS=.", "install"], zvbi, env=environment)
    ffmpeg = args.work / "ffmpeg-source"
    checkout("https://github.com/FFmpeg/FFmpeg.git", FFMPEG_REVISION, ffmpeg)
    patches = sorted((ROOT / "images/ffmpeg-builds/patches/common").glob("*.patch"))
    require(patches, "reviewed FFmpeg patches are missing")
    for patch in patches:
        run(["git", "apply", "--check", patch], ffmpeg)
        run(["git", "apply", patch], ffmpeg)
    flags = ["--enable-gpl", "--enable-version3", "--disable-shared", "--enable-static",
             "--disable-ffplay", "--disable-doc", "--disable-autodetect", "--enable-pthreads",
             "--enable-zlib", "--enable-cairo",
             "--enable-librsvg", "--enable-fontconfig", "--enable-libfreetype",
             "--enable-libharfbuzz", "--enable-libfribidi", "--enable-libass", "--enable-libzimg",
             "--enable-libzvbi", "--enable-libsvtav1", "--enable-libjxl", "--enable-libx264",
             "--enable-libx265", "--enable-libvpx", "--enable-libopus", "--enable-openssl",
             "--enable-librav1e", "--enable-libdav1d", "--enable-videotoolbox", "--enable-audiotoolbox"]
    try:
        run(["./configure", f"--prefix={prefix}", f"--arch={architecture}", "--target-os=darwin", *flags],
            ffmpeg, env=environment)
    except subprocess.CalledProcessError:
        # Configure reports probe details only in this file, not its stderr.
        diagnostic = ffmpeg / "ffbuild/config.log"
        if diagnostic.is_file():
            sys.stderr.write(diagnostic.read_text(errors="replace")[-16000:])
        raise
    run(["make", f"-j{args.jobs}", "ffmpeg", "ffprobe"], ffmpeg, env=environment)
    package.mkdir()
    for tool in ("ffmpeg", "ffprobe"):
        shutil.copy2(ffmpeg / tool, package / tool)
    shutil.copy2(ffmpeg / "COPYING.GPLv3", package / "LICENSE.txt")
    (package / "lib").mkdir()
    run(["dylibbundler", "-b", "-x", package / "ffmpeg", "-x", package / "ffprobe",
         "-d", package / "lib", "-p", "@executable_path/lib/"], env=environment, timeout=600)
    for path in [*sorted((package / "lib").glob("*.dylib")), package / "ffmpeg", package / "ffprobe"]:
        run(["codesign", "--force", "--sign", "-", path], timeout=30)
    for library in (package / "lib").glob("*.dylib"):
        require(len(library_owners.get(library.name, set())) == 1,
                "bundled library has a missing or ambiguous dependency origin")
    notices = package / "build-info/homebrew"
    notices.mkdir(parents=True)
    for record in inventory:
        keg = record.pop("keg")
        dest = notices / record["name"]
        dest.mkdir()
        formula_file = keg / ".brew" / (record["name"] + ".rb")
        require(formula_file.is_file(), "installed dependency formula is missing")
        shutil.copy2(formula_file, dest / "formula.rb")
        record["formula_sha256"] = sha256(dest / "formula.rb")
        files = {}
        for path in keg.rglob("*"):
            if path.is_file() and not path.is_symlink() and re.search(r"^(COPYING|LICENSE|LICENCE|COPYRIGHT)", path.name, re.IGNORECASE):
                relative = path.relative_to(keg)
                output = dest / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
                files[relative.as_posix()] = sha256(output)
        require(files, f'license notices missing for {record["name"]}')
        record["notice_files"] = files
    (notices / "dependencies.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    tools = json.loads(run([brew, "info", "--json=v2", *TOOLS], capture=True))
    tool_versions = {f["name"]: [i["version"] for i in f["installed"]] for f in tools["formulae"]}
    (notices / "build-tools.json").write_text(json.dumps(tool_versions, indent=2, sort_keys=True) + "\n")
    recipe = args.work / "zvbi-recipe.sh"
    recipe.write_text(f'SCRIPT_REPO="https://github.com/zapping-vbi/zvbi"\nSCRIPT_COMMIT="{ZVBI_REVISION}"\n')
    run([sys.executable, ROOT / "scripts/stage-teletext-source.py", "--recipe", recipe,
         "--source", zvbi, "--package", package])
    run([sys.executable, ROOT / "scripts/verify-teletext-source.py", package,
         "--expected-revision", ZVBI_REVISION])
    build_info = package / "build-info"
    shutil.copy2(Path(__file__), build_info / "macos-build.py")
    shutil.copy2(ROOT / "scripts/stage-teletext-source.py", build_info / "stage-teletext-source.py")
    patch_folder = build_info / "ffmpeg-patches"
    patch_folder.mkdir()
    for patch in patches:
        shutil.copy2(patch, patch_folder / patch.name)
    run(["git", "archive", "--format=tar.gz", f"--prefix=ffmpeg-{FFMPEG_REVISION}/",
         f"--output={build_info / 'ffmpeg-source.tar.gz'}", FFMPEG_REVISION], ffmpeg)
    identities = verify_bundle(package, architecture)
    record = {"schema_version": 1, "rid": args.rid, "candidate_version": args.version,
              "ffmpeg_commit": FFMPEG_REVISION, "zvbi_commit": ZVBI_REVISION,
              "configure_flags": flags, "deployment_target": args.deployment_target,
              "macos_version": platform.mac_ver()[0], "xcode": run(["xcodebuild", "-version"], capture=True).strip(),
              "patches": {p.name: sha256(p) for p in patches}, "mach_o_sha256": identities,
              "recipe_sha256": sha256(Path(__file__)), "homebrew_core_revision": args.homebrew_core_revision,
              "homebrew_brew_revision": args.homebrew_brew_revision,
              "homebrew_cask_revision": args.homebrew_cask_revision,
              "library_owners": {p.name: next(iter(library_owners[p.name])) for p in (package / "lib").glob("*.dylib")},
              "acceptance": "candidate recipe; Phase 9 platform acceptance remains separate"}
    (package / "build-info/source.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    # Probe from a moved copy. PATH contains no Homebrew; DYLD overrides are absent.
    moved = args.work / "relocated-proof" / package.name
    moved.parent.mkdir()
    shutil.copytree(package, moved)
    clean_environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(args.work / "proof-home")}
    Path(clean_environment["HOME"]).mkdir()
    for script, values in (("verify-package-provenance.py", ["runtime", moved]),
                           ("verify-teletext.py", [moved / "ffmpeg", "--expected-sha256", identities["ffmpeg"]]),
                           ("verify-svg.py", [moved / "ffmpeg"]), ("verify-webp.py", [moved / "ffmpeg"]),
                           ("verify-sparse-playback.py", [moved / "ffmpeg"])):
        run([sys.executable, ROOT / "scripts" / script, *values], env=clean_environment, timeout=600)
    archive_base = args.work / package.name
    archive = Path(shutil.make_archive(str(archive_base), "gztar", args.work, package.name))
    (archive.with_name(archive.name + ".sha256")).write_text(f"{sha256(archive)}  {archive.name}\n")
    print(json.dumps({"candidate_archive": archive.name, "archive_sha256": sha256(archive),
                      "rid": args.rid, "publication": "not_performed"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rid", choices=("osx-x64", "osx-arm64"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--homebrew-core-revision", required=True)
    parser.add_argument("--homebrew-brew-revision", required=True)
    parser.add_argument("--homebrew-cask-revision", required=True)
    parser.add_argument("--deployment-target", default="15.0")
    args = parser.parse_args()
    args.work = args.work.resolve()
    build(args)


if __name__ == "__main__":
    main()
