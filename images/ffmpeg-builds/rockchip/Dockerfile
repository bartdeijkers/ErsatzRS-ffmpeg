# Extend the exact reviewed ARM64 codec image. Host Docker manages this build;
# no Docker socket is mounted into the image or its containers.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG FFBUILD_JOBS=4
ENV FFBUILD_JOBS=${FFBUILD_JOBS}
COPY svg/build-dependency.sh /svg/build-dependency.sh
COPY rockchip/mpp.sh /svg/recipes/rkmpp.sh
RUN test "$TARGET" = linuxarm64 && bash /svg/build-dependency.sh rkmpp
COPY rockchip/rga.sh /svg/recipes/rkrga.sh
RUN test "$TARGET" = linuxarm64 && bash /svg/build-dependency.sh rkrga
ENV FF_CONFIGURE="${FF_CONFIGURE} --enable-rkmpp --enable-rkrga"
