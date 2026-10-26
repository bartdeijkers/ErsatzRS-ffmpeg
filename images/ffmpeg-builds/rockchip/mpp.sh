#!/bin/bash
# Source and build contract: ErsatzTV/FFmpeg-Builds bbd45671594a3c1e3ea8fc0007bd9d2bb00ccd8b.
SCRIPT_REPO="https://github.com/nyanmisaka/rk-mirrors.git"
SCRIPT_COMMIT="a9380ef333102ac318628f83b5f7a460d377749e"
SOURCE_ARCHIVE="https://codeload.github.com/nyanmisaka/rk-mirrors/tar.gz/$SCRIPT_COMMIT"
SOURCE_SHA256="68da788139ea4187c249001fa523a98d567e2caa6cfcdd3a5171e0c998c8202b"

ffbuild_dockerbuild() {
    cmake -S . -B rkmpp_static_build -GNinja \
        -DCMAKE_TOOLCHAIN_FILE="$FFBUILD_CMAKE_TOOLCHAIN" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$FFBUILD_PREFIX" \
        -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=OFF -DBUILD_TEST=OFF
    cmake --build rkmpp_static_build --parallel "${FFBUILD_JOBS:-4}"
    DESTDIR="$FFBUILD_DESTDIR" cmake --install rkmpp_static_build
    echo 'Libs.private: -lstdc++' >> "$FFBUILD_DESTPREFIX/lib/pkgconfig/rockchip_mpp.pc"

    # Same pinned source and compiler, independent library instance for Next.
    cmake -S . -B rkmpp_shared_build -GNinja \
        -DCMAKE_TOOLCHAIN_FILE="$FFBUILD_CMAKE_TOOLCHAIN" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ersatzrs-next-mpp \
        -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=ON -DBUILD_TEST=OFF
    cmake --build rkmpp_shared_build --parallel "${FFBUILD_JOBS:-4}"
    DESTDIR="$FFBUILD_DESTDIR" cmake --install rkmpp_shared_build
    companion="$FFBUILD_DESTDIR/opt/ersatzrs-next-mpp"
    cp -L "$companion/lib/librockchip_mpp.so.1" "$companion/librockchip_mpp.so.1"
    mkdir -p "$companion/notices" "$FFBUILD_DESTDIR/opt/ersatzrs-svg-sources/rkmpp-notices"
    cp -a LICENSES "$companion/notices/"
    cp readme.txt inc/rk_mpi.h "$companion/notices/"
    cp -a "$companion/notices/". "$FFBUILD_DESTDIR/opt/ersatzrs-svg-sources/rkmpp-notices/"
}
