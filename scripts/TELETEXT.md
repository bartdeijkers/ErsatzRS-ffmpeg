# Teletext package verification

Phase 9 uses a standalone bounded package probe plus the application runtime
probe. Decoder names or version strings alone do not establish capability.

```sh
python3 scripts/verify-teletext.py <exact-package-ffmpeg> \
  --expected-sha256 <manifest-executable-sha256>
python3 scripts/test-teletext-tools.py
```

The original CC0 fixture selects pages 200/888, excludes 201, checks caption
text/timing and cyan/green full-page bitmap output. Each decoder process has a
ten-second deadline, bounded stdout/stderr and bounded cleanup; overflow or
failure terminates it. No user media or broadcaster capture is needed. Native
Windows runs the same Python check. ARM emulation is explicitly labelled:

```sh
python3 scripts/verify-teletext.py <exact-arm-package-ffmpeg> \
  --expected-sha256 <manifest-executable-sha256> \
  --emulator <qemu-static-executable> --sysroot <matching-host-library-sysroot>
```

The v2.0.6 x64/Windows dependency recipe pins libzvbi
`41477c97c8edf7a01f1594b2a95b94f0117eed21` (0.2.44); the retained ARM dependency
recipes pin `d3a5ee9f2b047bf16cd1ee5ccf6ec05ee75409d0` (0.2.45). Use the actual
recipe/source/build receipt for each artifact. Do not infer one common source
revision from the runtime repository version.

The existing four archives contain a top-level GPL license but lack the exact
libzvbi source/notice inventory required for Phase 9 package acceptance. Stage
notices into a fresh unpublished package using the exact build inputs:

```sh
python3 scripts/stage-teletext-source.py --recipe <actual-zvbi-recipe> \
  --source <exact-source-checkout> --package <unpublished-package-directory>
python3 scripts/verify-teletext-source.py <unpublished-package-directory> \
  --expected-revision <exact-libzvbi-source-revision>
```

This preserves the full upstream license/copyright text, authors, README,
dependency recipe and source archive with checksums. The verifier rejects
changed/missing notices, mismatched recipe/commit, foreign archive identity,
links, unsafe paths and oversized archives. It does not claim that adding
notices rebuilds a binary or independently proves compiler linkage. Keep the
actual dependency-image/compiler provenance with that inventory. Published
archives remain immutable; this procedure never authorizes replacing release
assets or promoting a new runtime pin.

The macOS candidate recipe is documented in `recipes/macos/README.md`.
