#!/bin/bash
# Static pixman for the win-x64 FFmpeg-Builds image. Required by cairo, which
# BtbN/FFmpeg-Builds does not ship (we add cairo for FFmpeg's --enable-cairo,
# matching the linux-x64 package). Copied into the cloned FFmpeg-Builds
# scripts.d/ by .github/workflows/release.yml before makeimage/build.

SCRIPT_REPO="https://gitlab.freedesktop.org/pixman/pixman.git"
SCRIPT_COMMIT="pixman-0.46.4"

ffbuild_enabled() {
    return 0
}

ffbuild_dockerbuild() {
    mkdir build && cd build

    local myconf=(
        --prefix="$FFBUILD_PREFIX"
        --buildtype=release
        --default-library=static
        -Dtests=disabled
        -Ddemos=disabled
        -Dgtk=disabled
        -Dlibpng=disabled
    )

    if [[ $TARGET == win* || $TARGET == linux* ]]; then
        myconf+=(
            --cross-file=/cross.meson
        )
    else
        echo "Unknown target"
        return -1
    fi

    meson setup "${myconf[@]}" ..
    ninja -j"$(nproc)"
    DESTDIR="$FFBUILD_DESTDIR" ninja install
}

# pixman is a transitive dependency of cairo, not an FFmpeg library itself, so
# it contributes no ./configure flag (default ffbuild_configure is a no-op).
