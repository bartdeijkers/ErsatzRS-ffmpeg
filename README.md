# ErsatzRS FFmpeg

This repo contains the first-party FFmpeg 9.0 build for [ErsatzRS](https://github.com/bartdeijkers/ErsatzRS),
a from-scratch Rust reimplementation of [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV).

It is a fork of [ErsatzTV-ffmpeg](https://github.com/ErsatzTV/ErsatzTV-ffmpeg), whose images are modified
versions of those found at [jrottenberg/ffmpeg](https://github.com/jrottenberg/ffmpeg) and
[linuxserver/docker-ffmpeg](https://github.com/linuxserver/docker-ffmpeg).

ErsatzRS uses the `drawvg` filter (rendered via Cairo) and the `drawtext` filter for reloadable dynamic text.
These FFmpeg 9.0 images are built with `--enable-cairo`, `--enable-libharfbuzz`,
`--enable-libfontconfig`, `--enable-libfreetype`, `--enable-libfribidi`, `--enable-libass`,
`--enable-libzimg` (for `zscale`) and the `libsvtav1` encoder, in addition to the codecs inherited from upstream.
Release and container builds fail unless both graphics filters, the complete text-shaping stack, and a real
file-backed `drawtext` render are available.

## Downloadable ARM packages

See [ARM package build and acceptance](images/ffmpeg-builds/ARM-PACKAGES.md)
for pinned dependency inputs, bounded host Docker builds, archive provenance,
and the required software runtime checks. Native hardware acceptance is tracked
separately from emulated software execution.

## Downloadable v2.0.7 packages

[Version 2.0.7](https://github.com/bartdeijkers/ErsatzRS-ffmpeg/releases/tag/v2.0.7)
retains the pinned FFmpeg 9.0 source and adds monotonic
subtitle-heartbeat and VideoToolbox caption corrections. Linux ARM64 alone adds
the RKMPP/RGA hardware pipeline; the other RIDs keep their pixel-format ABI.
The ARM64 dependency extension lives in `images/ffmpeg-builds/rockchip/` and
pins both source revisions and archive checksums. It builds static libraries
for FFmpeg and a separate shared MPP companion for the private Next package.

Linux x64, Linux ARM64, Linux ARMv7 and Windows x64 archives pass all four
existing-package CI checks at verification commit
`aa14713ef37dc8276cfbc7b2cdabf00a5251486c`
([run 40117309596](https://github.com/bartdeijkers/ErsatzRS-ffmpeg/actions/runs/40117309596)).
Publication reuses those exact archive bytes. Verify each archive with its
`.sha256` sidecar; `candidate-manifest.json` retains the complete pinned inventory.
macOS builds are deferred until maintainer resume and no macOS package is shipped.
Final ErsatzRS application integration remains separate.
Rockchip RKMPP/RGA,
Intel QSV HDR, AMD VAAPI and native macOS VideoToolbox captions remain explicitly
approved, unverified hardware acceptance debt. Existing v2.0.6 packages retain
their immutable bytes. This package release does not rebuild or publish Docker images.

Remove each local fix when the selected upstream source supplies equivalent
behavior and its original regression passes. The unchanged heartbeat and
VideoToolbox regressions are retained under `scripts/upstream-regressions/`.

## Version 2.0.6 package verification

Version 2.0.6 rebuilds all four downloadable RIDs with animated WebP loop/seek
and truncated ICC/EXIF metadata corrections. Pin the exact release and verify
its archive SHA-256 before use. Existing Docker tags identify separately built
images; they are not evidence for these downloadable packages.

The package source remains FFmpeg 9.0 commit
`d32b387f2b0a484599d4587d651891f0c63c4238`. Each archive includes source pins,
applied patch hashes, dependency identity, build input hashes and executable
checksums under `build-info/`. The verification checkout is recorded separately
from the binary build origin. The existing-package verification workflow runs
the staged, manifest-pinned bytes without rebuilding or publishing them.

Common patch 0015 corrects the WebP ANMF header position and resets the frame
counter when generic looping seeks back to the first frame. Patch 0016 backports
upstream FFmpeg commit `cfaaf0062c085433ccb500689f137849794aeb63` for exact ICC/EXIF
reads and removal of incomplete side data. Check both patches independently
when updating FFmpeg: remove each local correction once the selected upstream
source supplies equivalent behavior and the corresponding regression passes.

`scripts/verify-webp.py` exercises finite/infinite loops, complete frame order,
fractional seeking and bounded output. Its optional actual-library metadata
harness uses `scripts/verify-webp-metadata.c` and the exact built source/static
prefix to prove preservation of complete ICC/EXIF and cleanup of short reads.
Clean Bookworm and native Windows execution cover graphics, animation, sparse
subtitles and alternate audio. ARM emulation establishes software execution;
Intel QSV, AMD AMF and native Linux NVIDIA interop remain explicitly unverified.

## Phase 9 teletext runtime work

[Teletext package checks](scripts/TELETEXT.md) cover exact-page functional
decoding and source/license inventories. The four v2.0.6 packages retain their
immutable bytes; v2.0.7 supplies the new verified notice/source inventories.
[Native macOS recipes](recipes/macos/README.md) and existing artifacts/evidence
are retained. Both macOS architectures are **Deferred by maintainer decision**
(2026-10-26), not accepted, during the private-repository period. Their workflow
is disabled: no builds, crossbuilds, packages, toolchain installations,
acceptance/runtime trials or paid runners/services may start. Resumption requires
explicit maintainer permission even after a visibility change. The required
matrix remains Linux x64, ARM64, ARMv7 and Windows x64; all functional teletext,
license/provenance and required-platform gates remain. No release is implied.
