#!/usr/bin/env python3
"""Stage exact libzvbi source/notices without claiming a binary rebuild.

Use the dependency recipe and source checkout actually used by a fresh build.
For existing packages, create an unpublished candidate copy; never rewrite an
immutable published archive. This inventory does not prove compiler linkage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPOSITORY = "https://github.com/zapping-vbi/zvbi"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stage(recipe, source, package):
    text = recipe.read_text(encoding="utf-8")
    repository = re.findall(r'^SCRIPT_REPO="([^"]+)"$', text, re.MULTILINE)
    revision = re.findall(r'^SCRIPT_COMMIT="([0-9a-f]{40})"$', text, re.MULTILINE)
    require(repository == [REPOSITORY] and len(revision) == 1,
            "expected an exact libzvbi Git recipe")
    revision = revision[0]
    require(package.is_dir() and not package.is_symlink(), "package directory is missing or a symlink")
    require((package / "ffmpeg").is_file() or (package / "ffmpeg.exe").is_file(), "package FFmpeg is missing")
    require((package / "ffprobe").is_file() or (package / "ffprobe.exe").is_file(), "package FFprobe is missing")
    destination = package / "build-info/teletext"
    require(not destination.exists(), "teletext inventory already exists")
    require(not (package / "build-info").is_symlink(), "build-info must not be a symlink")

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(source), *arguments], timeout=60)

    require(git("rev-parse", f"{revision}^{{commit}}").decode().strip() == revision,
            "source revision differs")
    files = {name: git("show", f"{revision}:{name}") for name in ("COPYING.md", "AUTHORS", "README.md")}
    files["dependency-recipe.sh"] = recipe.read_bytes()
    # Git archive excludes untracked/local edits and .git; retain exact source.
    with tempfile.TemporaryDirectory(prefix="ersatzrs-zvbi-source-") as directory:
        archive = Path(directory) / "libzvbi-source.tar.gz"
        subprocess.run(["git", "-C", str(source), "archive", "--format=tar.gz",
                        f"--prefix=libzvbi-{revision}/", f"--output={archive}", revision],
                       check=True, timeout=60)
        require(archive.stat().st_size <= 64 * 1024 * 1024, "source archive is unexpectedly large")
        files["libzvbi-source.tar.gz"] = archive.read_bytes()
    record = {"schema_version": 1, "repository": REPOSITORY, "revision": revision,
              "scope": "exact source and notices; compiler linkage requires build provenance",
              "files": {name: digest(data) for name, data in files.items()}}
    destination.mkdir(parents=True)
    try:
        for name, data in files.items():
            (destination / name).write_bytes(data)
        (destination / "manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    except BaseException:
        # This directory is created and wholly owned by this invocation.
        import shutil
        shutil.rmtree(destination)
        raise
    return {"teletext_source_inventory": "staged", "revision": revision,
            "manifest_sha256": digest((destination / "manifest.json").read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.recipe.resolve(), args.source.resolve(), args.package.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
