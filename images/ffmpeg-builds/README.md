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
3. run `./makeimage.sh <target> gpl 9.0`, extend that image with the SVG
   dependency layer below, then use its exact image ID for
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

## Vulkan/CUDA export patch

Both packages apply `patches/common/0001-vulkan-cuda-export.patch` after
cloning FFmpeg and before configure. `prepare-patches.py` adds a
read-only patch mount to the pinned BtbN build; unexpected script structure
or a patch that does not apply fails the build.

This adapts ErsatzTV-ffmpeg's `patches/0002-vulkan-cuda-export-fix.patch`
for FFmpeg n9.0. Export queries use the actual image creation flags and check
every backing image format. FFmpeg 9's DRM modifier logging and dedicated
allocation requirements are retained; a dedicated requirement from any image
is preserved. The image-flags query is shared across platforms; applying the
correction only on Windows left Linux dependent on driver tolerance. Native
Linux NVIDIA export remains unverified on the WSL build machine; software
Vulkan checks do not replace that hardware gate. The patch is needed even though n9.0 is newer than the upstream
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

## Sparse-stream readrate patch

All release packages and Linux container architectures apply
`patches/common/0002-sparse-readrate.patch` before configure. This is
ErsatzTV-ffmpeg commit `32bf88a39655c34767abcdde59526fa3973c90a9`, adapted
without semantic changes to FFmpeg n9.0 (three-line offsets only). Audio/video
streams set the readrate pace; subtitles and other sparse streams are fallback
clocks only when no active audio/video remains. The earlier slowest-stream fix
is already in n9.0 and is insufficient by itself.

`prepare-patches.py BUILD_TREE linux64` installs common patches; `win64` also
installs the Windows D3D11 patches. Container builds apply the same common files
with zero fuzz. Unexpected source or recipe structure fails the build.

Run the deterministic source regression against the patched build tree:

```sh
python3 scripts/verify-readrate-source.py <ffmpeg-source>/fftools/ffmpeg_demux.c
```

It compiles the actual `readrate_sleep` function with a controlled clock and
checks audio/video pacing beside frozen subtitles, the slowest continuous
stream, sparse-only fallback, and finished/discarded/unstarted exclusions.
Unpatched n9.0 fails the two continuous-stream cases. This source check does
not replace decoded playback and package verification.

Run the decoded pacing regression on a Linux host (Windows packages use WSL
interop and `wslpath`):

```sh
python3 scripts/verify-sparse-playback.py <package>/ffmpeg
python3 scripts/verify-sparse-playback.py <package>/ffmpeg.exe
```

The temporary fixture has 16 seconds of video, two audio tracks, and PGS
packets at 0/2/10/14 seconds. It requires progress gaps below two seconds and
media lead below one second, all 400 decoded frames, both bitmap positions,
the selected 880 Hz alternate audio and error-free decoding. Each subprocess
has a deadline. No user library is read or changed.

## Expanded FFmpeg 9 patch set

The additional patches are rebased from ErsatzTV-ffmpeg `8.1.2-1`, tree
`5bdca62b3d8b129d7ddec66647e8a36c7d680678`:

| Local patch | Upstream patch | Purpose |
| --- | --- | --- |
| common/0003 | 0001 | Requested hardware-frame dimensions; n9.0 already handles software frames |
| common/0004 | 0008 | Seed QSV composition output timestamps |
| common/0005 | 0009 | QSV padding through a single-input composite |
| common/0006 | 0010 | Padding colour/range, chroma alignment and incompatible-operation guards |
| common/0007 | 0011 | AMF MPEG-2 and VC-1 decoder wrappers |
| windows/0008 | 0003 | D3D11 render-target texture allocation |
| windows/0009 | 0004 | Clamp only array-texture pools |
| common/0010 | Local FFmpeg 9 correction | Mark librsvg Cairo output as premultiplied alpha |

Upstream's slowest-stream readrate correction already exists in n9.0; the
sparse-stream correction remains necessary. The pinned libva API already
passes the alignment-query version guard. The pinned OpenAPV API predates the
1.1 change, so its compatibility patch is not applied. These decisions must be
reviewed if those dependencies are bumped.

Decoder/filter availability is not hardware acceptance. This candidate is
built on a machine with NVIDIA hardware: Intel QSV and AMD AMF playback remain
unverified. Registering `vc1_amf` must not cause ErsatzRS/Next to select it for
MKV playback while upstream's timestamp restriction remains. The D3D11 texture
change also retains upstream's tradeoff for consumers expecting texture arrays.

## SVG dependency layer

`svg/Dockerfile` extends a previously built BtbN dependency image. It builds
static Libffi, PCRE2, GLib, Cairo, Pango and librsvg, rebuilds the same pinned
rav1e using its `release-no-lto` profile to avoid Rust runtime symbol collisions,
and enables `--enable-librsvg`.
Recipes derive from ErsatzTV/FFmpeg-Builds commit
`80c8a385fe18296798fae24133cde6a5595a40e9`; Cairo stays at 1.18.4, and Libffi uses
the checksum-verified 3.5.2 release archive because its newer git bootstrap
requires an Autotools macro absent from the pinned toolchain. Rust dependencies
are vendored using librsvg's committed Cargo.lock before the offline build.
Resolved source revisions and available licence files are retained in
`/opt/ersatzrs-svg-sources` inside the toolchain image.

To reuse a local dependency cache, give it a separate local tag, then build this
layer directly with host Docker. Do not mount the Docker socket. Select the
resulting image explicitly for the prepared BtbN build:

```sh
docker build --build-arg BASE_IMAGE=<local-base-tag> \
  --build-arg FFBUILD_JOBS=8 -t ersatzrs-ffmpeg-svg:<target> \
  images/ffmpeg-builds/svg
python3 images/ffmpeg-builds/prepare-patches.py <fresh-build-tree> <target>
# Run in the prepared BtbN tree; target is linux64 or win64.
FFBUILD_IMAGE_OVERRIDE=ersatzrs-ffmpeg-svg:<target> \
  GIT_BRANCH_OVERRIDE=n9.0 ./build.sh <target> gpl 9.0
```

Record exact image IDs, source revisions, patch hashes and resulting package
checksums with the candidate. A mutable image tag does not identify a released
package. This layer builds downloadable packages; it does not republish the
existing multi-platform Docker runtime.

FFmpeg 9's librsvg decoder omitted alpha-mode metadata. The local 0010 patch
sets the existing `AVCodecContext` field to premultiplied alpha, matching Cairo's
pixel storage. Without it, automatic overlay of 50% blue on white decodes as
127/127/191 instead of 127/127/255. The regression checks the default overlay
path without an explicit alpha-mode override.

Verify decoded SVG dimensions, scaling, colour, transparency, automatic overlay
and visible text:

```sh
python3 scripts/verify-svg.py <package>/ffmpeg
python3 scripts/verify-svg.py <package>/ffmpeg.exe
```

Retain the existing drawvg/drawtext, sparse-subtitle playback, Linux baseline
and native Windows Vulkan/CUDA checks. SVG support does not replace those gates.
