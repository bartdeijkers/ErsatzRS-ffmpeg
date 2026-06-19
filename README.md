# ErsatzRS FFmpeg

This repo contains the first-party FFmpeg 8.1 build for [ErsatzRS](https://github.com/bartdeijkers/ErsatzRS),
a from-scratch Rust reimplementation of [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV).

It is a fork of [ErsatzTV-ffmpeg](https://github.com/ErsatzTV/ErsatzTV-ffmpeg), whose images are modified
versions of those found at [jrottenberg/ffmpeg](https://github.com/jrottenberg/ffmpeg) and
[linuxserver/docker-ffmpeg](https://github.com/linuxserver/docker-ffmpeg).

ErsatzRS requires FFmpeg 8.1 for the `drawvg` filter (rendered via Cairo), so these images are built with
`--enable-cairo`, `--enable-libharfbuzz`, `--enable-libfontconfig`, `--enable-libfreetype`, `--enable-libass`,
`--enable-libzimg` (for `zscale`) and the `libsvtav1` encoder, in addition to the codecs inherited from upstream.
