# Native macOS teletext candidates

**Deferred by maintainer decision (2026-10-26), not accepted.** During the
private-repository period, do not run macOS builds, crossbuilds, packages,
toolchain installations, acceptance/runtime trials or paid runners/services.
The workflow is disabled. Preserve code, guards, artifacts and evidence without
deliberate incompatibility; additional macOS repairs are deferred. All recipes
below require explicit permission to resume, even after a visibility change.
The current required matrix is Linux x64, ARM64, ARMv7 and Windows x64; full
functional Phase 9A requirements remain unchanged.

This recipe prepares the two missing Phase 9 runtime candidates. It has not yet
been executed on macOS. The retained, disabled `teletext-macos-candidate.yml` workflow describes builds of
`osx-x64` on `macos-15-intel` and `osx-arm64` on `macos-15`; it has read-only
repository permissions and uploads artifacts without publishing a release.

Use an ephemeral native runner. Dependency provisioning deliberately changes
that runner's Homebrew checkout and installed formulae. It is not a maintenance
command for a personal Mac. The workflow pins Homebrew/core to an explicit Git
revision and disables automatic update/API formula replacement. Installed
versions must match those recipes; unexpected dependencies or missing notices
fail candidate construction. Both architectures retain their future proof obligations after authorized resumption.

The requested build baseline is macOS 15.0. This is a candidate test baseline,
not approval to drop older operating systems, nor proof that copied Homebrew
libraries support a lower deployment target. Inspect actual Mach-O deployment
requirements and the project's supported OS baseline before accepting or
publishing packages. No native macOS or six-platform acceptance is claimed.

FFmpeg uses the same pinned 9.0 source and common patches as v2.0.6. libzvbi is
built statically from `d3a5ee9f2b047bf16cd1ee5ccf6ec05ee75409d0` (0.2.45). The
codec/graphics stack retains required software codecs, JPEG XL animation,
drawvg/drawtext and text shaping, plus native VideoToolbox/AudioToolbox. Explicit
configure flags and disabled autodetection prevent accidental ambient codecs.

`dylibbundler` relocates the Homebrew library closure to `lib/`. The gate checks
Mach-O architecture, rejects external non-system dependency paths, checks every
library has one recorded formula owner and verifies ad-hoc signatures. Do not
substitute an unbundled Homebrew executable: the installed application must run
without Homebrew or DYLD overrides.

Each archive includes FFmpeg/libzvbi source snapshots, common patches, build
recipes, dependency versions/source URLs/bottle metadata, formulae, license
notices and executable/library checksums. The libzvbi inventory checker verifies
that notices equal the corresponding Git archive; its result remains distinct
from compiler/linkage provenance. Review complete corresponding-source and
redistribution obligations before publication; an SPDX label alone is
insufficient.

After relocation, the recipe runs existing decoded drawvg/drawtext, SVG, WebP,
sparse-subtitle/alternate-audio and new exact-page teletext checks from a moved
copy with a clean PATH and no DYLD overrides. This proves candidate software
execution only when the native jobs actually pass. It does not prove installed
ErsatzRS behavior, hardware acceleration, the authored-page engine or Phase 9
completion. Keep native VideoToolbox and broader application acceptance separate.

Example on a provisioned ephemeral runner:

```sh
python3 recipes/macos/build.py --rid osx-arm64 \
  --version 2.0.7-teletext-candidate --work "$RUNNER_TEMP/teletext-macos-osx-arm64" \
  --jobs 3 --homebrew-core-revision <exact-40-character-revision>
```

Do not modify v2.0.6 assets or change ErsatzRS's managed pin before exact candidate
acceptance and authorized publication. Reuse the accepted archive bytes rather
than rebuilding at release time.
