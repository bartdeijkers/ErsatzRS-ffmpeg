ARG BASE_IMAGE
FROM debian:bookworm-slim@sha256:f3034a6ec3c1205360777c4aae76234998866ad18806ae62b63a3f84ccad782b AS compiler
RUN apt-get update && apt-get install --no-install-recommends -y \
    gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf && \
    dpkg-query -W > /cross-packages.txt

FROM ${BASE_IMAGE}

# Reuse Debian's existing compiler instead of bootstrapping GCC and glibc.
COPY --from=compiler /usr/bin/arm-linux-gnueabihf-* /usr/bin/
COPY --from=compiler /usr/arm-linux-gnueabihf /usr/arm-linux-gnueabihf
COPY --from=compiler /usr/lib/gcc-cross /usr/lib/gcc-cross
COPY --from=compiler /cross-packages.txt /opt/ersatzrs-armv7-toolchain-packages.txt

# Prefer static codecs and dynamic glibc. Keep the empty libpthread/libdl
# compatibility archives required by the merged glibc 2.36 implementation.
RUN \
    find /usr/arm-linux-gnueabihf /usr/lib/gcc-cross \( -type l \
        -and -name '*.so' \
        -and -not -ipath '*plugin*' \
        -and -not -name 'libdl.*' \
        -and -not -name 'libc.*' \
        -and -not -name 'libm.*' \
        -and -not -name 'libmvec.*' \
        -and -not -name 'librt.*' \
        -and -not -name 'libpthread.*' \
        \) -delete && \
    find /usr/arm-linux-gnueabihf /usr/lib/gcc-cross \( \
        -name 'libc.a' \
        -or -name 'libm.a' \
        -or -name 'libmvec.a' \
        \) -delete && \
    mkdir /opt/ffbuild

ENV FFBUILD_TOOLCHAIN=arm-linux-gnueabihf \
    FFBUILD_RUST_TARGET="armv7-unknown-linux-gnueabihf"

RUN \
    rustup target add "$FFBUILD_RUST_TARGET" && \
    echo "[target.$FFBUILD_RUST_TARGET]\nlinker = \"${FFBUILD_TOOLCHAIN}-gcc\"\nar = \"${FFBUILD_TOOLCHAIN}-gcc-ar\"\n" > "$CARGO_HOME"/config.toml

ADD toolchain.cmake /toolchain.cmake
ADD cross.meson /cross.meson

ADD gen-implib.sh /usr/bin/gen-implib
RUN git clone --filter=blob:none https://github.com/yugr/Implib.so /opt/implib && \
    git -C /opt/implib checkout a3e167cf978a5b8a38ec0f710d8c4331e8dcdd9a

ENV QEMU_LD_PREFIX="/usr/arm-linux-gnueabihf" \
    FFBUILD_TARGET_FLAGS="--pkg-config=pkg-config --cross-prefix=${FFBUILD_TOOLCHAIN}- --arch=arm --cpu=armv7-a --target-os=linux" \
    FFBUILD_CROSS_PREFIX="${FFBUILD_TOOLCHAIN}-" \
    FFBUILD_PREFIX=/opt/ffbuild \
    FFBUILD_DESTDIR=/opt/ffdest \
    FFBUILD_DESTPREFIX=/opt/ffdest/opt/ffbuild \
    FFBUILD_CMAKE_TOOLCHAIN=/toolchain.cmake \
    PKG_CONFIG=pkg-config \
    PKG_CONFIG_LIBDIR=/opt/ffbuild/lib/pkgconfig:/opt/ffbuild/share/pkgconfig \
    CC="${FFBUILD_TOOLCHAIN}-gcc" \
    CXX="${FFBUILD_TOOLCHAIN}-g++" \
    LD="${FFBUILD_TOOLCHAIN}-ld" \
    AR="${FFBUILD_TOOLCHAIN}-gcc-ar" \
    RANLIB="${FFBUILD_TOOLCHAIN}-gcc-ranlib" \
    NM="${FFBUILD_TOOLCHAIN}-gcc-nm" \
    CFLAGS="-static-libgcc -static-libstdc++ -I/opt/ffbuild/include -O2 -pipe -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard -fPIC -DPIC -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -pthread" \
    CXXFLAGS="-static-libgcc -static-libstdc++ -I/opt/ffbuild/include -O2 -pipe -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard -fPIC -DPIC -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -pthread" \
    LDFLAGS="-static-libgcc -static-libstdc++ -L/opt/ffbuild/lib -O2 -pipe -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard -fstack-protector-strong -fstack-clash-protection -Wl,-z,relro,-z,now -pthread -lm" \
    STAGE_CFLAGS="-fvisibility=hidden -fno-semantic-interposition" \
    STAGE_CXXFLAGS="-fvisibility=hidden -fno-semantic-interposition"

# Debian's cross binutils have architecture-specific host helper libraries.
COPY --from=compiler /usr/lib/x86_64-linux-gnu/*armhf.so* /usr/lib/x86_64-linux-gnu/
COPY --from=compiler /usr/lib/x86_64-linux-gnu/libsframe.so* /usr/lib/x86_64-linux-gnu/

# Verify compiler subprocesses and host shared-library dependencies immediately.
RUN printf '#include <iostream>\nint main(){std::cout << "armv7";}\n' > /tmp/check.cpp && \
    $CXX $CXXFLAGS /tmp/check.cpp $LDFLAGS -o /tmp/check-armv7 && \
    readelf -h /tmp/check-armv7 | grep 'Machine:.*ARM' && \
    rm /tmp/check.cpp /tmp/check-armv7
