# Native macOS teletext candidates

This recipe prepares the two missing Phase 9 runtime candidates. It has not yet
been executed on macOS. The manual `teletext-macos-candidate.yml` workflow builds
`osx-x64` on `macos-15-intel` and `osx-arm64` on `macos-15`; it has read-only
repository permissions and uploads artifacts without publishing a release.

Use an ephemeral native runner. Dependency provisioning deliberately changes
that runner's Homebrew checkout and installed formulae. It is not a maintenance
command for a personal Mac. The workflow pins Homebrew/core to an explicit Git
revision and pins the compatible Homebrew tool independently, disabling automatic
update/API formula replacement. The reviewed recipes use Homebrew 7's
`resource ..., :test` syntax; hosted Homebrew 6 images cannot load them. Cask migration data is pinned to the compatible core snapshot too: old hosted
Cask data otherwise sends Azure CLI back to core, creating a resolution cycle.
No cask is installed. All three
checkout identities are checked before building and recorded in source provenance. Installed
versions must match those recipes; unexpected dependencies or missing notices
fail candidate construction. Both native architectures remain required.

The requested build baseline is macOS 15.0. This is a candidate test baseline,
not approval to drop older operating systems, nor proof that copied Homebrew
libraries support a lower deployment target. Inspect actual Mach-O deployment
requirements and the project's supported OS baseline before accepting or
publishing packages. Existing six-RID acceptance remains open.

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
  --jobs 3 --homebrew-core-revision <exact-40-character-core-revision> \
  --homebrew-brew-revision <exact-40-character-brew-revision> \
  --homebrew-cask-revision <exact-40-character-cask-revision>
```

Do not modify v2.0.6 assets or change ErsatzRS's managed pin before exact candidate
acceptance and authorized publication. Reuse the accepted archive bytes rather
than rebuilding at release time.
