# Extend the verified SVG dependency image with the legacy oneVPL dispatcher fix.
# Host Docker owns the build; no Docker socket is mounted in this image.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY svg/build-dependency.sh /svg/build-dependency.sh
COPY onevpl/recipe.sh /svg/recipes/onevpl.sh
COPY onevpl/legacy-device-discovery.patch /ersatzrs-onevpl/legacy-device-discovery.patch
RUN bash /svg/build-dependency.sh onevpl && \
    sha256sum /ersatzrs-onevpl/legacy-device-discovery.patch > /opt/ersatzrs-svg-sources/onevpl-patches.sha256
