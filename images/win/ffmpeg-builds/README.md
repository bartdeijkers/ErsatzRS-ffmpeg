# win-x64 static build (BtbN/FFmpeg-Builds overrides)

The `win-x64` release package is produced by cross-compiling a **fully static**
FFmpeg with [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) on the
Linux self-hosted runner (Docker), instead of dynamic linking inside MSYS2.
The result is two self-contained executables (`ffmpeg.exe`, `ffprobe.exe`) with
no accompanying DLLs — matching the layout of the upstream BtbN win64 builds.

`.github/workflows/release.yml` (`win-x64` job):

1. clones FFmpeg-Builds at a pinned commit,
2. copies `scripts.d/*.sh` from here into the cloned tree,
3. runs `./makeimage.sh win64 gpl 8.1` then
   `GIT_BRANCH_OVERRIDE=n<FFMPEG_VERSION> ./build.sh win64 gpl 8.1`
   (the `8.1` addin sets the version gating; `GIT_BRANCH_OVERRIDE` pins the
   exact FFmpeg release tag),
4. repackages the resulting zip into the ErsatzRS layout
   (`ersatzrs-ffmpeg-<version>-win-x64/ffmpeg.exe` + `ffprobe.exe`).

## Why these overrides exist

BtbN's `win64-gpl` variant builds a superset of our codec set **except cairo**,
which ErsatzRS needs (FFmpeg's `--enable-cairo`, parity with the linux-x64
Dockerfile). Cairo and its `pixman` dependency are not in upstream
`scripts.d/`, so they are added here:

- `47-pixman.sh` — static pixman (cairo dependency; no FFmpeg flag).
- `50-cairo.sh` — minimal static cairo; emits `--enable-cairo`. `--enable-cairo`
  gates only FFmpeg's `drawvg` filter, which uses core cairo (image surface +
  paths/patterns) and no text/PNG/SVG, so all optional cairo backends are
  disabled and cairo depends only on pixman.

Pinned versions are bumped here when upstream FFmpeg-Builds or these libraries
are updated.
