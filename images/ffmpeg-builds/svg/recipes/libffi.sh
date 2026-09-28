#!/bin/bash

SCRIPT_REPO="https://github.com/libffi/libffi.git"
SCRIPT_COMMIT="v3.5.2"
SOURCE_ARCHIVE="https://github.com/libffi/libffi/releases/download/v3.5.2/libffi-3.5.2.tar.gz"
SOURCE_SHA256="f3a3082a23b37c293a4fcd1053147b371f2ff91fa7ea1b2a52e335676bac82dc"

ffbuild_enabled() {
    return 0
}

ffbuild_dockerbuild() {
    # Official release configure avoids obsolete libtool bootstrap macros.

    local myconf=(
        --prefix="$FFBUILD_PREFIX"
        --disable-shared
        --enable-static
        --with-pic
        --disable-docs
        --disable-multi-os-directory
    )

    if [[ $TARGET == win* || $TARGET == linux* ]]; then
        myconf+=(
            --host="$FFBUILD_TOOLCHAIN"
        )
    else
        echo "Unknown target"
        return -1
    fi

    ./configure "${myconf[@]}"
    make -j${FFBUILD_JOBS:-8}
    make install DESTDIR="$FFBUILD_DESTDIR"
}
