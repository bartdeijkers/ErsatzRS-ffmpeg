#!/bin/bash
# Source and build contract: ErsatzTV/FFmpeg-Builds bbd45671594a3c1e3ea8fc0007bd9d2bb00ccd8b.
SCRIPT_REPO="https://github.com/nyanmisaka/rk-mirrors.git"
SCRIPT_COMMIT="1d330cc28551943bed3380261a5a9c6fbd58ff53"
SOURCE_ARCHIVE="https://codeload.github.com/nyanmisaka/rk-mirrors/tar.gz/$SCRIPT_COMMIT"
SOURCE_SHA256="30bd712507fcc6be075cd4aaa2622d46fde203fa6f3418b85d0fc1e2136b8ec4"

ffbuild_dockerbuild() {
    # The pinned Meson file hard-codes shared_library; retain upstream's static
    # adaptation while refusing silent source drift.
    test "$(grep -c '^librga = shared_library(' meson.build)" = 1
    sed -i 's/^librga = shared_library(/librga = library(/' meson.build
    meson setup rkrga_build --prefix="$FFBUILD_PREFIX" --buildtype=release \
        --default-library=static --cross-file=/cross.meson \
        -Dcpp_args=-fpermissive -Dlibdrm=false -Dlibrga_demo=false
    meson compile -C rkrga_build -j "${FFBUILD_JOBS:-4}"
    DESTDIR="$FFBUILD_DESTDIR" meson install -C rkrga_build
    echo 'Libs.private: -lstdc++' >> "$FFBUILD_DESTPREFIX/lib/pkgconfig/librga.pc"
    notices="$FFBUILD_DESTDIR/opt/ersatzrs-svg-sources/rkrga-notices"
    mkdir -p "$notices"
    cp COPYING README.md include/RgaApi.h im2d_api/im2d.h "$notices/"
}
