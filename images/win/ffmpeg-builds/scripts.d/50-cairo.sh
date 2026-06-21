#!/bin/bash
# Static cairo for the win-x64 FFmpeg-Builds image, so the package can be built
# with FFmpeg's --enable-cairo (parity with the linux-x64 Dockerfile). BtbN
# ships neither cairo nor its pixman dependency, so both are added as overrides
# (see 47-pixman.sh).
#
# --enable-cairo gates exactly one FFmpeg component: the `drawvg` filter
# (drawvg_filter_deps="cairo"). drawvg uses only core cairo — image surfaces,
# paths, patterns, fill/stroke/transforms (cairo_image_surface_create_for_data,
# cairo_fill, ...). It uses no PNG/SVG/script surfaces and no text/font API, so
# every optional cairo backend is disabled here. The result is a minimal static
# cairo that depends only on pixman (the Win32 surface/font backends are always
# compiled on Windows and pull gdi32/msimg32, which cairo's meson records in
# cairo.pc, so FFmpeg's static link resolves them automatically).

SCRIPT_REPO="https://gitlab.freedesktop.org/cairo/cairo.git"
SCRIPT_COMMIT="1.18.4"

ffbuild_depends() {
    echo base
    echo pixman
}

ffbuild_enabled() {
    return 0
}

ffbuild_dockerbuild() {
    mkdir build && cd build

    local myconf=(
        --prefix="$FFBUILD_PREFIX"
        --buildtype=release
        --default-library=static
        # Font backends — drawvg renders no text.
        -Ddwrite=disabled
        -Dfreetype=disabled
        -Dfontconfig=disabled
        # Surface backends — drawvg only needs the image surface.
        -Dpng=disabled
        -Dquartz=disabled
        -Dtee=disabled
        -Dxcb=disabled
        -Dxlib=disabled
        -Dzlib=disabled
        # Util/misc/tests.
        -Dlzo=disabled
        -Dglib=disabled
        -Dspectre=disabled
        -Dsymbol-lookup=disabled
        -Dtests=disabled
        -Dgtk_doc=false
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

    # cairo.h marks its API as __declspec(dllimport) on Windows unless
    # CAIRO_WIN32_STATIC_BUILD is defined. Cairo defines it only for its own
    # compilation, not in the installed cairo.pc, so static consumers (FFmpeg's
    # configure) compile against the dllimport decl and fail to link the static
    # libcairo.a (undefined reference to __imp_cairo_create). Propagate the
    # macro through the pkg-config Cflags.
    if [[ $TARGET == win* ]]; then
        sed -i 's/^Cflags:/Cflags: -DCAIRO_WIN32_STATIC_BUILD/' \
            "$FFBUILD_DESTPREFIX"/lib/pkgconfig/cairo.pc
    fi
}

ffbuild_configure() {
    echo --enable-cairo
}

ffbuild_unconfigure() {
    echo --disable-cairo
}
