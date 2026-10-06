# Changelog

All notable changes are documented here using Keep a Changelog categories.

## [Unreleased]

## [2.0.6] - 2026-10-07

### Fixed

- Repeat complete animated WebP frames after generic loop rewinds and fractional
  seeks, preserving embedded finite/infinite loops and bounded output. Rebuild
  Linux x64, Windows x64, ARM64 and ARMv7 packages with the same correction.
- Backport FFmpeg's ICC/EXIF exact-read safety fix so truncated animated WebP
  metadata is removed instead of exposing incomplete side data.

- Publish the Docker `9.0` tag as a literal version instead of rejecting it as
  incomplete semver. Allow a tested image digest to be published manually
  without rebuilding any architecture, verifying the resulting manifest.

- Fix the Linux AMD64 container build for FFmpeg 9 by using the installed
  `glslc` shader compiler instead of the removed `--enable-libshaderc` option.
  Update libplacebo to FFmpeg 9's minimum version, 7.351.0, build it after
  shaderc with shader compilation required, and require Vulkan scaling and
  libplacebo filters in the resulting image.

- Pace media reading from active audio/video streams when sparse subtitle or
  data streams are present, preserving sparse-only input fallback. Apply the
  correction to Linux and Windows packages and every Linux container architecture.

### Added

- Verify checksum-pinned prepared packages on Linux, native Windows and emulated
  ARM before publication, including source/patch provenance, decoded graphics,
  animation, sparse subtitles and alternate audio. Reuse those package bytes
  without a second release build; hardware acceptance debt remains unverified.

### Changed

- Support native Windows pipe progress and file paths in sparse-playback checks,
  retaining bounded execution and owned-process cleanup.

## [2.0.5] - 2026-10-01

### Added

- Add pinned ARM64 and ARMv7 static-codec package build recipes, with source,
  dependency image and checksum provenance. ARM package acceptance uses clean
  Bookworm execution and decoded software playback; native ARM hardware and
  application acceptance remain unverified.

### Changed

- Keep the accepted v2.0.4 Linux x64 and Windows archives unchanged when adding
  ARM packages. Package and executable checksums identify the reused artifacts.
- Support OpenAPV 1.1's metadata API in new dependency builds while retaining
  compatibility with the older API used by existing x64 packages.

## [2.0.4] - 2026-09-30

### Fixed

- Preserve fixed QSV decoder frame pools across compatible stream-parameter
  changes, avoiding downstream legacy Media SDK encoder failures.
- Initialize D3D11 QSV texture indices and transfer frames through the D3D11
  child context, preserving VAAPI/D3D9 single-handle safety.
- Patch the statically linked oneVPL dispatcher to find legacy Windows Intel
  runtimes on non-primary adapters and recover missing device IDs.
  Intel QSV hardware validation remains explicitly unverified.

## [2.0.3] - 2026-09-28

### Added

- Decode SVG images in the Linux x64 and Windows x64 packages with static
  librsvg, including transparency and text rendering.
- Add QSV hardware padding and AMF MPEG-2/VC-1 decoder wrappers from the
  ErsatzTV-ffmpeg 8.1.2-1 patch set, rebased onto FFmpeg 9. Device support still
  depends on the installed GPU and driver; QSV and AMF hardware playback have
  not been validated on the candidate build machine.

### Changed

- Build the pinned rav1e encoder with its existing no-LTO profile so its Rust
  runtime can link statically alongside librsvg. Encoding/decoding checks pass.

### Fixed

- Apply the existing Vulkan export image-flags correction to Linux as well as
  Windows; the affected Vulkan capability query is shared across platforms.

- Mark SVG decoder output as premultiplied alpha so automatic overlays preserve
  translucent colours instead of darkening them.

- Preserve requested hardware-frame dimensions and QSV composition timestamps.
  Honour padding colour range and chroma alignment, rejecting incompatible
  combined VPP operations. Restore the Windows D3D11 render-target texture and
  pool allocation behaviour required by the upstream QSV pipeline.

[Unreleased]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/compare/v2.0.6...HEAD
[2.0.6]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/compare/v2.0.5...v2.0.6
[2.0.3]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/releases/tag/v2.0.3
[2.0.4]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/compare/v2.0.3...v2.0.4

[2.0.5]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/bartdeijkers/ErsatzRS-ffmpeg/releases/tag/v2.0.4
