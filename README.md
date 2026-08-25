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
