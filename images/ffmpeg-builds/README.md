# FFmpeg builds (BtbN/FFmpeg-Builds overrides)

The `linux-x64` and `win-x64` release packages are built with
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) on the Linux
self-hosted runner (Docker):

- **win-x64** is **fully static** — two self-contained executables, no DLLs.
- **linux-x64** statically links every codec but links **glibc dynamically**
  (BtbN has no fully-static linux target). The package bundles **no** shared
  libraries; the binaries use the host's own glibc.

The key point is that **linux-x64 bundles nothing**. The package used to be
extracted from the runtime Docker image by copying ffmpeg's whole `ldd` closure
(including `libc.so.6`) into a `lib/` directory and relying on
`LD_LIBRARY_PATH`. That bundles the *build's* libc but runs it under the *host's*
dynamic loader; when a host glibc is older than the build's, the program aborts
with
`libc.so.6: undefined symbol: __tunable_is_initialized, version GLIBC_PRIVATE`
(libc and `ld-linux` must come from the same glibc, and the loader was never
bundled). Bundling nothing and using the host glibc removes that coupling. The
only remaining requirement — a recent-enough host glibc — is verified at build
time (see below).

`.github/workflows/release.yml` (`linux-x64` and `win-x64` jobs) each:

1. clone FFmpeg-Builds at a pinned commit (`FFBUILDS_REF`, kept in lock-step
   across both jobs),
2. copy `scripts.d/*.sh` from here into the cloned tree, and register `cairo` in
   `scripts.d/zz-final.sh` — that entry stage hard-codes the list of
   dependencies the image builds, so without this our cairo/pixman scripts are
   present but never reached and `--enable-cairo` silently drops out (pixman is
   pulled in as cairo's dependency). The workflow fails loudly if the `sed`
   anchor moves on a pin bump,
3. run `./makeimage.sh <target> gpl 9.0` then
   `GIT_BRANCH_OVERRIDE=n<FFMPEG_VERSION> ./build.sh <target> gpl 9.0`
   (`<target>` is `linux64` / `win64`; the `9.0` addin sets the version gating;
   `GIT_BRANCH_OVERRIDE` pins the exact FFmpeg release tag),
4. repackage the resulting artifact into the ErsatzRS layout:
   - linux-x64: `ersatzrs-ffmpeg-<version>-linux-x64/ffmpeg` + `ffprobe`
     (tar.gz). The repackage step then runs both binaries inside a clean
     `debian:bookworm-slim` (glibc 2.36, the ErsatzRS runtime baseline); if the
     BtbN toolchain ever needs a newer glibc, the release fails loudly here
     instead of at user runtime as `GLIBC_2.xx not found`. The same gate checks
     that both tools report `FFMPEG_VERSION`, that FFmpeg exposes `drawvg` and
     `drawtext`, that Cairo plus the complete Fontconfig/FreeType/HarfBuzz/FriBidi
     shaping stack is enabled, and that file-backed reloadable text renders.
   - win-x64: `ersatzrs-ffmpeg-<version>-win-x64/ffmpeg.exe` + `ffprobe.exe`
     (zip). A separate Windows self-hosted job downloads that exact artifact and
     runs the same filter/build-configuration and file-backed render contract
     before a tagged release may publish.

## Why these overrides exist

BtbN's `linux64-gpl` / `win64-gpl` variants build a superset of our codec set
**except cairo**, which ErsatzRS needs (FFmpeg's `--enable-cairo`). Cairo and its
`pixman` dependency are not in upstream `scripts.d/`, so they are added here and
are written to work for both `win*` and `linux*` targets:

- `47-pixman.sh` — static pixman (cairo dependency; no FFmpeg flag).
- `50-cairo.sh` — minimal static cairo; emits `--enable-cairo`. `--enable-cairo`
  gates only FFmpeg's `drawvg` filter, which uses core cairo (image surface +
  paths/patterns) and no text/PNG/SVG, so all optional cairo backends are
  disabled and cairo depends only on pixman.

Pinned versions are bumped here when upstream FFmpeg-Builds or these libraries
are updated.

## Windows Vulkan/CUDA export patch

The Windows package applies `patches/0001-vulkan-cuda-export.patch` after
cloning FFmpeg and before configure. `prepare-windows-patches.py` adds a
read-only patch mount to the pinned BtbN build; unexpected script structure
or a patch that does not apply fails the build.

This adapts ErsatzTV-ffmpeg's `patches/0002-vulkan-cuda-export-fix.patch`
for FFmpeg n9.0. Export queries use the actual image creation flags and check
every backing image format. FFmpeg 9's DRM modifier logging and dedicated
allocation requirements are retained; a dedicated requirement from any image
is preserved. The patch is needed even though n9.0 is newer than the upstream
8.1.2 package. Native Windows CUDA control, Vulkan/libplacebo/CUDA/NVENC
execution and decoded output must pass before publishing a replacement.

Run the manual native gate on a Windows NVIDIA machine against the extracted
first-party package:

```powershell
pwsh -File scripts/verify-windows-vulkan-cuda.ps1 -Bundle <extracted-package-directory>
```

It records executable identity, checks the CUDA control and the existing
ErsatzRS capability graph, then encodes and decodes 25 synthetic HDR-tagged
frames through Vulkan/libplacebo/CUDA/NVENC. The output must be H.264 at
256x144 with BT.709 color metadata and exactly 25 decoded frames. Every
process has a 30-second bound; failures fail the gate. This proves interop
and output decoding, not subjective HDR tone-mapping quality.
