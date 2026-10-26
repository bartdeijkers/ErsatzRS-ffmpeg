# Upstream regression fixtures

The scripts and DVD-subtitle fixture are retained unchanged from
`ErsatzTV/ErsatzTV-ffmpeg@aed834faa58cc0fd1f620eaf4edaa1a704182b31`.
The corresponding FFmpeg 9 adaptations are common patches 0018 and 0019.

Run `tests/sub2video-heartbeat-burst.sh FFMPEG` with its original 2.0 bound.
For native macOS caption acceptance, supply a captioned H.264 fixture through
`tests/videotoolbox-caption-sei.sh FFMPEG FFPROBE NEW_OUTPUT_DIR CAPTIONED_INPUT`.
That hardware check remains explicitly unverified until an appropriate native
environment is qualified; a source build does not establish it.

Retire each local patch when the adopted upstream source passes the same
regression without it. Preserve the reproducer and its acceptance conditions.
