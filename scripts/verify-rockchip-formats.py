#!/usr/bin/env python3
"""Verify ARM64 NV15/NV20 software unpacking without Rockchip hardware.

Usage: verify-rockchip-formats.py FFMPEG
Independent synthetic packed samples must decode to exact 10-bit planar values.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def packed_row(values):
    # Four 10-bit samples occupy five little-endian bytes; the last group may
    # be partial. Construct the integer independently of libswscale's C loops.
    word = sum(value << (10 * index) for index, value in enumerate(values))
    return word.to_bytes((len(values) * 10 + 7) // 8, "little")


def verify(ffmpeg):
    cases = []
    edges = [0, 1, 2, 3, 63, 64, 65, 511, 512, 513, 939, 940, 1022, 1023]
    for format_name, planar, vertical in [("nv15", "yuv420p10le", 2),
                                           ("nv20", "yuv422p10le", 1)]:
        for width in [64, 66]:
            height = 16
            y_rows = [[edges[(x + 3 * y) % len(edges)] for x in range(width)]
                      for y in range(height)]
            u_rows = [[edges[(2 * x + 5 * y + 3) % len(edges)]
                       for x in range(width // 2)] for y in range(height // vertical)]
            v_rows = [[edges[(3 * x + 2 * y + 7) % len(edges)]
                       for x in range(width // 2)] for y in range(height // vertical)]
            uv_rows = [[value for pair in zip(u, v) for value in pair]
                       for u, v in zip(u_rows, v_rows)]
            source = b"".join(packed_row(row) for row in [*y_rows, *uv_rows])
            expected = b"".join(struct.pack("<H", value)
                                for plane in [y_rows, u_rows, v_rows]
                                for row in plane for value in row)
            result = subprocess.run([
                str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "rawvideo", "-pixel_format", format_name,
                "-video_size", f"{width}x{height}", "-i", "pipe:0",
                "-frames:v", "1", "-pix_fmt", planar, "-f", "rawvideo", "pipe:1",
            ], input=source, capture_output=True, timeout=30)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            if result.stdout != expected:
                raise AssertionError(f"{format_name} {width}x{height}: exact 10-bit values differ")
            cases.append({"input": format_name, "output": planar, "width": width,
                          "height": height, "sha256": hashlib.sha256(expected).hexdigest()})
    return {"ffmpeg_sha256": hashlib.sha256(ffmpeg.read_bytes()).hexdigest(),
            "software_unpacking": cases, "hardware_acceptance": "unverified"}


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1]).resolve()), indent=2))
