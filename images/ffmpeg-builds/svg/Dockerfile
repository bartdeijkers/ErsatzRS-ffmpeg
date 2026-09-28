# Extend an explicitly selected, already-built dependency image.
# The host invokes Docker directly; this image never needs the Docker socket.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG FFBUILD_JOBS=8
ENV FFBUILD_JOBS=${FFBUILD_JOBS} CARGO_BUILD_JOBS=${FFBUILD_JOBS}
COPY build-dependency.sh /svg/build-dependency.sh
COPY recipes/libffi.sh /svg/recipes/libffi.sh
RUN bash /svg/build-dependency.sh libffi
COPY recipes/pcre2.sh /svg/recipes/pcre2.sh
RUN bash /svg/build-dependency.sh pcre2
COPY recipes/glib.sh /svg/recipes/glib.sh
RUN bash /svg/build-dependency.sh glib
COPY recipes/cairo.sh /svg/recipes/cairo.sh
RUN bash /svg/build-dependency.sh cairo
COPY recipes/pango.sh /svg/recipes/pango.sh
RUN bash /svg/build-dependency.sh pango
COPY recipes/librsvg.sh /svg/recipes/librsvg.sh
RUN bash /svg/build-dependency.sh librsvg

COPY recipes/rav1e.sh /svg/recipes/rav1e.sh
RUN bash /svg/build-dependency.sh rav1e

ENV FF_CONFIGURE="${FF_CONFIGURE} --enable-librsvg"
