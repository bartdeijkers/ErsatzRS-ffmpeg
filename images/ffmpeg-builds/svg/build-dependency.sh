#!/bin/bash
set -euo pipefail
name=${1:?dependency required}
source "/svg/recipes/$name.sh"
source_dir="/tmp/ersatzrs-svg-$name"
mkdir "$source_dir"
if [[ -n "${SOURCE_ARCHIVE:-}" ]]; then
    archive="$source_dir/source.tar.gz"
    curl --fail --location --retry 3 "$SOURCE_ARCHIVE" -o "$archive"
    printf '%s  %s\n' "$SOURCE_SHA256" "$archive" | sha256sum -c -
    tar -xf "$archive" --strip-components=1 -C "$source_dir"
    rm "$archive"
    resolved_source="$SCRIPT_COMMIT sha256:$SOURCE_SHA256"
else
    git -C "$source_dir" init -q
    git -C "$source_dir" remote add origin "$SCRIPT_REPO"
    git -C "$source_dir" fetch --depth=1 origin "$SCRIPT_COMMIT"
    git -C "$source_dir" checkout --detach FETCH_HEAD
    resolved_source=$(git -C "$source_dir" rev-parse HEAD)
fi
cd "$source_dir"
if [[ "$name" == glib ]]; then
    git submodule update --init --recursive --depth=1
    meson subprojects download proxy-libintl
elif [[ "$name" == librsvg ]]; then
    mkdir -p .cargo
    vendor_home=$(mktemp -d)
    CARGO_HOME="$vendor_home" cargo vendor --locked --versioned-dirs > .cargo/config.toml
    rm -rf "$vendor_home"
fi
# Recipes use staged installs. Keep each dependency isolated, then merge it
# into the inherited prefix so following recipes can consume it.
export FFBUILD_DESTDIR="/tmp/ersatzrs-svg-dest-$name"
export FFBUILD_DESTPREFIX="$FFBUILD_DESTDIR$FFBUILD_PREFIX"
ffbuild_dockerbuild
cp -a "$FFBUILD_DESTDIR"/. /
mkdir -p /opt/ersatzrs-svg-sources
printf '%s %s\n' "$SCRIPT_REPO" "$resolved_source" > "/opt/ersatzrs-svg-sources/$name.txt"
for license in "$source_dir"/COPYING* "$source_dir"/LICENSE*; do
    if [[ -f "$license" ]]; then
        cp "$license" "/opt/ersatzrs-svg-sources/$name-${license##*/}"
    fi
done
if [[ -f "$source_dir/Cargo.lock" ]]; then
    cp "$source_dir/Cargo.lock" "/opt/ersatzrs-svg-sources/$name-Cargo.lock"
fi
cd /
rm -rf "$source_dir" "$FFBUILD_DESTDIR"
