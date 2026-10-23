# Teletext decoder fixture

`teletext.ts` is original synthetic data dedicated to CC0 by ErsatzRS. It was
copied from ErsatzRS commit `06b3a923`, not captured from a broadcaster.

SHA256: `17dba7c8d448388877f3d19bb2e4989484d86ddccd2e7a20a069249ac0938067`.

Page 200 contains cyan/green guide text, page 201 is independently transmitted
and must remain unselected, and page 888 contains boxed subtitle text. The
standalone package check preserves the application probe's exact options,
fixture digest, text/bitmap dimensions and ten-second process/output bounds.
The canonical generator is `scripts/calibration/generate-teletext-fixture.py`
in ErsatzRS. A fixture change must update both repositories and their digest
checks deliberately. This fixture does not establish authored-service output.
