#!/usr/bin/env python3
"""Targeted process-bound and exact-source rejection regressions."""
import asyncio
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def load(name):
    specification = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


probe = load("verify-teletext")
source = load("verify-teletext-source")


class ProcessBounds(unittest.IsolatedAsyncioTestCase):
    async def test_stdout_overflow_terminates_process_before_outer_deadline(self):
        command = [sys.executable, "-c", "import sys,time; sys.stdout.buffer.write(b'x'*1000000); sys.stdout.flush(); time.sleep(60)"]
        with self.assertRaisesRegex(ValueError, "output exceeded"):
            await asyncio.wait_for(probe.run(command, [], limit=16), 3)

    async def test_stderr_overflow_is_not_hidden_by_successful_stdout(self):
        command = [sys.executable, "-c", "import sys,time; sys.stderr.buffer.write(b'x'*1000000); sys.stderr.flush(); time.sleep(60)"]
        with self.assertRaisesRegex(ValueError, "output exceeded"):
            await asyncio.wait_for(probe.run(command, []), 3)

    async def test_deadline_terminates_stalled_decoder(self):
        with patch.object(probe, "PROBE_TIMEOUT", 0.05):
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(probe.run([sys.executable, "-c", "import time; time.sleep(60)"], []), 3)

    async def test_foreign_executable_digest_is_rejected_before_execution(self):
        with self.assertRaisesRegex(ValueError, "executable digest differs"):
            await probe.verify(Path(sys.executable), ROOT / "fixtures/teletext.ts", "0" * 64)

    async def test_changed_fixture_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "changed.ts"
            fixture.write_bytes(b"not the independent fixture")
            with self.assertRaisesRegex(ValueError, "fixture digest differs"):
                await probe.verify(Path(sys.executable), fixture)


class SourceBounds(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name)
        self.folder = self.package / "build-info/teletext"
        self.folder.mkdir(parents=True)
        self.revision = "a" * 40
        self.notice = b"GNU synthetic test license - not a production license\n"
        files = {"COPYING.md": self.notice, "AUTHORS": b"Synthetic fixture author\n",
                 "README.md": b"Synthetic test source\n",
                 "dependency-recipe.sh": f'SCRIPT_REPO="{source.REPOSITORY}"\nSCRIPT_COMMIT="{self.revision}"\n'.encode()}
        with tarfile.open(self.folder / "libzvbi-source.tar.gz", "w:gz", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": self.revision}) as archive:
            for name in ("COPYING.md", "AUTHORS", "README.md"):
                entry = tarfile.TarInfo(f"libzvbi-{self.revision}/{name}")
                entry.size = len(files[name])
                archive.addfile(entry, io.BytesIO(files[name]))
        for name, data in files.items():
            (self.folder / name).write_bytes(data)
        self.update_manifest()

    def update_manifest(self):
        manifest = {"schema_version": 1, "repository": source.REPOSITORY, "revision": self.revision,
                    "files": {name: source.sha256(self.folder / name) for name in source.FILES}}
        (self.folder / "manifest.json").write_text(json.dumps(manifest))

    def test_complete_inventory_is_distinct_from_compiler_proof(self):
        self.assertEqual(source.verify(self.package, self.revision)["compiler_linkage"], "not_checked")

    def test_other_source_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "source revision differs"):
            source.verify(self.package, "b" * 40)

    def test_missing_license_is_rejected(self):
        (self.folder / "COPYING.md").unlink()
        with self.assertRaisesRegex(ValueError, "invalid source inventory file"):
            source.verify(self.package, self.revision)

    def test_changed_license_is_rejected(self):
        (self.folder / "COPYING.md").write_bytes(b"altered")
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            source.verify(self.package, self.revision)

    def test_self_consistent_replacement_notice_must_match_archive(self):
        (self.folder / "COPYING.md").write_bytes(b"GNU replacement")
        self.update_manifest()
        with self.assertRaisesRegex(ValueError, "notice differs"):
            source.verify(self.package, self.revision)

    def test_self_consistent_recipe_cannot_change_source_pin(self):
        recipe = self.folder / "dependency-recipe.sh"
        recipe.write_text(recipe.read_text().replace(self.revision, "b" * 40))
        self.update_manifest()
        with self.assertRaisesRegex(ValueError, "recipe does not match"):
            source.verify(self.package, self.revision)

    def test_rehashed_archive_with_foreign_git_revision_is_rejected(self):
        archive_path = self.folder / "libzvbi-source.tar.gz"
        with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": "b" * 40}) as archive:
            entry = tarfile.TarInfo(f"libzvbi-{self.revision}/COPYING.md")
            entry.size = len(self.notice)
            archive.addfile(entry, io.BytesIO(self.notice))
        self.update_manifest()
        with self.assertRaisesRegex(ValueError, "archive Git revision differs"):
            source.verify(self.package, self.revision)

    def test_traversal_archive_is_rejected_without_extraction(self):
        archive_path = self.folder / "libzvbi-source.tar.gz"
        with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": self.revision}) as archive:
            entry = tarfile.TarInfo(f"libzvbi-{self.revision}/../outside")
            entry.size = 1
            archive.addfile(entry, io.BytesIO(b"x"))
        self.update_manifest()
        with self.assertRaisesRegex(ValueError, "archive path differs"):
            source.verify(self.package, self.revision)


class MacBundleRules(unittest.TestCase):
    def setUp(self):
        specification = importlib.util.spec_from_file_location("macos_build", ROOT.parent / "recipes/macos/build.py")
        self.mac = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.mac)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name)
        (self.package / "lib").mkdir()
        for name in ("ffmpeg", "ffprobe", "lib/test.dylib"):
            (self.package / name).write_bytes(b"synthetic Mach-O test double")

    def notice_record(self, name):
        keg = self.package / name
        (keg / ".brew").mkdir(parents=True)
        (keg / ".brew" / f"{name}.rb").write_text("synthetic pinned formula")
        return {"name": name, "keg": keg, "license": "LGPL-2.1-or-later"}

    def test_spdx_legacy_and_owned_symlink_notices_are_preserved(self):
        record = self.notice_record("glib")
        keg = record["keg"]
        (keg / "LICENSES").mkdir()
        text = b"synthetic complete source notice"
        (keg / "LICENSES/LGPL-2.1-or-later.txt").write_bytes(text)
        (keg / "COPYING").symlink_to("LICENSES/LGPL-2.1-or-later.txt")
        (keg / "COPYRIGHT").write_bytes(b"synthetic attribution")
        output = self.package / "notices"
        self.mac.collect_dependency_notices([record], output)
        self.assertEqual(set(record["notice_files"]),
                         {"COPYING", "COPYRIGHT", "LICENSES/LGPL-2.1-or-later.txt"})
        self.assertEqual((output / "glib/COPYING").read_bytes(), text)
        self.assertFalse((output / "glib/COPYING").is_symlink())
        for name, digest in record["notice_files"].items():
            self.assertEqual(self.mac.sha256(output / "glib" / name), digest)

    def test_notice_symlink_cannot_read_outside_its_dependency(self):
        record = self.notice_record("glib")
        outside = self.package / "outside-notice"
        outside.write_bytes(b"outside the selected dependency")
        (record["keg"] / "COPYING").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes pinned dependency"):
            self.mac.collect_dependency_notices([record], self.package / "notices")
        self.assertFalse((self.package / "notices/glib/COPYING").exists())

    def test_all_missing_notices_fail_together_before_inventory_acceptance(self):
        records = [self.notice_record(name) for name in ("first", "second")]
        output = self.package / "notices"
        with self.assertRaises(ValueError) as error:
            self.mac.collect_dependency_notices(records, output)
        self.assertIn("first", str(error.exception))
        self.assertIn("second", str(error.exception))
        self.assertFalse((output / "dependencies.json").exists())

    def run_rule(self, dependencies, architecture="arm64"):
        def command(arguments, **kwargs):
            if arguments[0] == "lipo":
                return architecture + "\n"
            return ""
        with patch.object(self.mac, "run", side_effect=command), patch.object(self.mac, "dependencies", return_value=dependencies):
            return self.mac.verify_bundle(self.package, "arm64")

    def test_relocated_closure_is_accepted_without_external_paths(self):
        identities = self.run_rule(["@executable_path/lib/test.dylib", "/usr/lib/libSystem.B.dylib"])
        self.assertEqual(set(identities), {"ffmpeg", "ffprobe", "lib/test.dylib"})

    def test_external_homebrew_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dependency escapes"):
            self.run_rule(["/opt/homebrew/opt/cairo/lib/libcairo.dylib"])

    def test_missing_relocated_library_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dependency is missing"):
            self.run_rule(["@executable_path/lib/missing.dylib"])

    def test_wrong_native_architecture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "architecture differs"):
            self.run_rule([], architecture="x86_64")

    def test_relative_dependency_cannot_escape_bundle(self):
        with self.assertRaisesRegex(ValueError, "dependency is missing"):
            self.run_rule(["@executable_path/lib/../ffmpeg"])


if __name__ == "__main__":
    unittest.main()
