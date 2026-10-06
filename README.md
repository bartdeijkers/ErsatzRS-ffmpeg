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
