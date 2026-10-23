#!/usr/bin/env python3
"""Validate the staged libzvbi source/notice inventory, not compiler linkage."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

REPOSITORY = "https://github.com/zapping-vbi/zvbi"
FILES = {"COPYING.md", "AUTHORS", "README.md", "dependency-recipe.sh", "libzvbi-source.tar.gz"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify(package, revision):
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "expected source revision must be exact")
    folder = package / "build-info/teletext"
    require(folder.is_dir() and not folder.is_symlink(), "teletext source inventory is missing")
    manifest_path = folder / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink() and
            manifest_path.stat().st_size <= 16384, "invalid source inventory manifest")
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("schema_version") == 1 and manifest.get("repository") == REPOSITORY,
            "unexpected source inventory schema/repository")
    require(manifest.get("revision") == revision, "libzvbi source revision differs")
    require(set(manifest.get("files", {})) == FILES, "source/notice inventory is incomplete")
    for name, digest in manifest["files"].items():
        path = folder / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 * 1024 * 1024,
                "invalid source inventory file")
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid inventory checksum")
        require(sha256(path) == digest, f"libzvbi inventory checksum differs: {name}")
    recipe = (folder / "dependency-recipe.sh").read_text()
    require(re.findall(r'^SCRIPT_REPO="([^"]+)"$', recipe, re.MULTILINE) == [REPOSITORY] and
            re.findall(r'^SCRIPT_COMMIT="([0-9a-f]{40})"$', recipe, re.MULTILINE) == [revision],
            "dependency recipe does not match the inventoried source")
    found = set()
    total = 0
    notices = {}
    with tarfile.open(folder / "libzvbi-source.tar.gz", "r:gz") as archive:
        require(archive.pax_headers.get("comment") == revision, "source archive Git revision differs")
        for index, member in enumerate(archive):
            require(index < 20000, "source archive has too many members")
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts and path.parts and
                    path.parts[0] == f"libzvbi-{revision}", "source archive path differs")
            require(member.name not in found, "duplicate source archive member")
            require(member.isfile() or member.isdir(), "source archive contains a link/special file")
            found.add(member.name)
            total += member.size
            require(total <= 128 * 1024 * 1024, "source archive expanded size exceeds its bound")
            if len(path.parts) == 2 and path.name in {"COPYING.md", "AUTHORS", "README.md"}:
                require(member.isfile() and member.size <= 1024 * 1024, "invalid archived notice")
                notices[path.name] = archive.extractfile(member).read()
    require(set(notices) == {"COPYING.md", "AUTHORS", "README.md"}, "archived notices are incomplete")
    for name, data in notices.items():
        require(data == (folder / name).read_bytes(), "notice differs from exact source archive")
    require("GNU" in notices["COPYING.md"].decode("utf-8"), "full license text is missing")
    return {"teletext_source_inventory": "passed", "revision": revision,
            "manifest_sha256": sha256(manifest_path), "compiler_linkage": "not_checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.package.resolve(), args.expected_revision), sort_keys=True))


if __name__ == "__main__":
    main()
