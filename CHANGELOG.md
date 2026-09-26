# Changelog

All notable changes are documented here using Keep a Changelog categories.

## [Unreleased]

### Fixed

- Pace media reading from active audio/video streams when sparse subtitle or
  data streams are present, preserving sparse-only input fallback. Apply the
  correction to Linux and Windows packages and every Linux container architecture.
