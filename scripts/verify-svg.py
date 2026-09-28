#!/usr/bin/env python3
"""Check actual SVG decoding, alpha, scaling and text using synthetic inputs.

Usage: python3 scripts/verify-svg.py /path/to/ffmpeg[.exe]
Windows binaries may be exercised from WSL. No user media is accessed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    ffmpeg = Path(sys.argv[1]).resolve()
    windows = ffmpeg.suffix.lower() == ".exe"

    def native_path(value):
        if windows and os.name != "nt":
            return subprocess.check_output(
                ["wslpath", "-w", str(value)], text=True, timeout=10
            ).strip()
        return str(value)

    def run(args):
        result = subprocess.run(
            [str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", *args],
            capture_output=True, timeout=30, check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout

    with tempfile.TemporaryDirectory(prefix="ersatzrs-svg-") as directory:
        root = Path(directory)
        shapes = root / "shapes.svg"
        shapes.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48" viewBox="0 0 64 48">
<rect x="8" y="8" width="16" height="16" fill="#ff0000"/>
<rect x="32" y="8" width="16" height="16" fill="#0000ff" fill-opacity="0.5"/>
</svg>''')

        def decode(source, width, height, filters=None):
            args = ["-i", native_path(source)]
            if filters:
                args += ["-vf", filters]
            data = run(args + ["-frames:v", "1", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"])
            if len(data) != width * height * 4:
                raise AssertionError(f"Unexpected decoded dimensions: {len(data)} bytes")
            return data

        def pixel(data, width, x, y):
            offset = (y * width + x) * 4
            return tuple(data[offset:offset + 4])

        decoded = decode(shapes, 64, 48)
        assert pixel(decoded, 64, 2, 2) == (0, 0, 0, 0), "transparent background lost"
        assert pixel(decoded, 64, 12, 12) == (255, 0, 0, 255), "red fill changed"
        blue = pixel(decoded, 64, 36, 12)
        # The stock FFmpeg librsvg decoder returns Cairo premultiplied alpha.
        assert blue[:2] == (0, 0) and 127 <= blue[2] <= 128 and blue[2] == blue[3], blue
        scaled = decode(shapes, 128, 96, "scale=128:96:flags=neighbor")
        assert pixel(scaled, 128, 24, 24) == (255, 0, 0, 255), "scaled fill changed"
        assert pixel(scaled, 128, 4, 4)[3] == 0, "scaled transparency lost"

        composite = run([
            "-f", "lavfi", "-i", "color=white:s=64x48:d=1",
            "-i", native_path(shapes),
            "-filter_complex", "[0:v][1:v]overlay=format=rgb",
            "-frames:v", "1", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1",
        ])
        assert pixel(composite, 64, 2, 2) == (255, 255, 255, 255), "transparent overlay changed background"
        blended = pixel(composite, 64, 36, 12)
        assert all(abs(a - b) <= 1 for a, b in zip(blended, (127, 127, 255, 255))), blended

        text = root / "text.svg"
        text.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="64">
<text x="4" y="44" font-family="sans-serif" font-size="32" fill="white">ErsatzRS</text>
</svg>''')
        glyphs = decode(text, 256, 64)
        visible = sum(alpha > 0 for alpha in glyphs[3::4])
        assert 200 < visible < 6000, f"SVG text did not render: {visible} visible pixels"

    print(json.dumps({
        "ffmpeg_sha256": hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
        "svg_dimensions": "64x48", "scaled_dimensions": "128x96",
        "alpha_and_colours": "passed", "automatic_overlay": "passed", "text_visible_pixels": visible,
    }, indent=2))


if __name__ == "__main__":
    main()
