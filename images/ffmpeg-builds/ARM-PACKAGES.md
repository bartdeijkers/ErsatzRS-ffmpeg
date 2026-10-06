# ARM package build recipes

The ARM package work uses static codec libraries and the host's glibc. Do not
copy a container's shared-library closure into a downloadable package. These
recipes run Docker from the host and never mount its socket into a container.
Use separate build directories and preserve other builders, containers and caches.

## ARM64 dependency provenance

The reviewed dependency image is:

```text
ghcr.io/btbn/ffmpeg-builds/linuxarm64-gpl-9.0@sha256:baabcc5e87f0f1e5bc7ee8bdeb6e1548e46734810621603fc411fabc2f5a3975
```

Its source revision is BtbN/FFmpeg-Builds
`e88e49f624457c455700b058f0a84ca87d499cc2`. Upstream
[run 36797641674, job 110166072467](https://github.com/BtbN/FFmpeg-Builds/actions/runs/36797641674/job/110166072467)
records that exact exported digest. The image contains static Cairo, librsvg and
the subtitle/text shaping dependencies; it does not need a second SVG build.
The n9.0 build below uses the earlier, separately pinned build-script revision.
Do not describe that script revision as the dependency image's source revision.

## Prepare and build FFmpeg

Clone BtbN/FFmpeg-Builds into a new directory and check out
`d04d5526084bb699ca2b400c32bbab7eb3ebcb4e`. Then run from this repository:

```sh
python3 images/ffmpeg-builds/prepare-arm-build.py <build-tree> linuxarm64
```

In the prepared tree, select the dependency image above:

```sh
FFBUILD_IMAGE_OVERRIDE=<exact-image-digest> GIT_BRANCH_OVERRIDE=n9.0 \
  ./build.sh linuxarm64 gpl 9.0
```

The preparation script requires the pinned build-script revision, verifies
FFmpeg commit `d32b387f2b0a484599d4587d651891f0c63c4238`, applies the common
patches with `git apply --check`, enables Cairo and limits compilation to four
jobs. ARMv7 explicitly passes its hard-float FPU flags through FFmpeg's
compiler/assembler probes and places libm after static codec libraries during
linking. FFmpeg 9 excludes ARM32 from its NVIDIA codec backend, so that target
disables ffnvcodec and CUDA LLVM; ARM64 and x64 settings are unchanged.
Patch 0014 adapts FFmpeg 9 to OpenAPV 1.1's metadata API while retaining
compatibility with the older API used by the existing x64 packages. Its source
is ErsatzTV/ErsatzTV-ffmpeg commit
`5bdca62b3d8b129d7ddec66647e8a36c7d680678`.

## ARMv7 dependency preparation

BtbN has no ARMv7 target. `armv7-toolchain/` supplies the hard-float ARMv7
cross compiler and CMake/Meson definitions. Build it with an explicitly selected
base image built from the pinned BtbN `images/base` recipe. Record that base
image's exact ID. The compiler stage uses an immutable Debian Bookworm image
and its packaged ARM hard-float GCC toolchain; installed package versions are
retained in `/opt/ersatzrs-armv7-toolchain-packages.txt`. Its glibc 2.36 sysroot
matches the Bookworm runtime gate. The import-library generator is pinned to an
exact source revision. Record the completed toolchain image ID before using it
as a dependency build input.

Use another fresh BtbN checkout at the same build-script revision:

```sh
python3 images/ffmpeg-builds/prepare-armv7-dependencies.py \
  <build-tree> <exact-local-base-image-id>
```

This creates the ARMv7 static variant, installs Cairo recipes, adds explicit
OpenSSL/libvpx/OpenH264 target settings, and generates the dependency graph.
The source-download helper uses only that graph and the supplied image ID.
The X11 configure checks follow the existing cross-compiled ARM64 behavior;
the x86-only VAAPI driver import recipe remains excluded on ARM. ARMv7 keeps
the portable AVS2 codec implementations because their pinned sources omit
the ARM assembly files referenced by their builds. VVenC and AOM use portable implementations without an unconditional NEON
requirement. libass retains its subtitle renderer and shaping dependencies
without requesting the unavailable ARM32 assembly backend. The rav1e build is limited to four
Cargo jobs. The Docker context excludes local image exports and layer caches.

Run `download.sh` in the prepared tree, then build its generated Dockerfile
with a dedicated builder and bounded concurrency. Supply the completed ARMv7
toolchain as its base build context. Do not use upstream `makeimage.sh` here:
it owns the generic `ffbuilder` name and may remove someone else's builder.
Extend the completed codec image with `svg/Dockerfile`, selecting the completed
image by verified ID and setting `FFBUILD_JOBS=4`. Finally prepare the FFmpeg
source with `prepare-arm-build.py <build-tree> linuxarmv7` and build against
that exact dependency image as for ARM64.

## Runtime baseline

The ARMv7 package requires glibc 2.36 (Debian Bookworm or a compatible newer
system) and the system GCC runtime. Its codec libraries are statically linked;
it does not bundle glibc or the ELF loader. The ARM64 candidate's highest
required GLIBC symbol version is 2.28; software execution is verified on
Bookworm. These ELF requirements do not imply native hardware acceptance.

## Package acceptance

Before publication, repackage the tools and license into the documented
ErsatzRS archive layout and record source revisions, patch checksums, image
identity and executable/archive SHA-256 checksums. Require clean Bookworm
execution, required encoders/filters, decoded drawvg/drawtext and SVG output,
and sparse-subtitle audio/video pacing. Emulation proves software execution;
it does not prove native hardware acceleration or application-level acceptance.
Version 2.0.5 reused the accepted x64 and Windows package bytes. Version 2.0.6
rebuilds all four RIDs because its animated WebP fixes affect every package.
Retain the immutable older releases for existing explicit pins.
