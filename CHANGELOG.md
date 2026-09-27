# Changelog

All notable changes are documented here using Keep a Changelog categories.

## [Unreleased]

### Fixed

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
