#!/usr/bin/env python3
"""Prove optional teletext decoding on an exact FFmpeg 9 package (P9A-02).

The fixture is original CC0 data from ErsatzRS. This does not prove authored
page encoding, carriage or native platform acceptance under an emulator.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re

FIXTURE_SHA256 = "17dba7c8d448388877f3d19bb2e4989484d86ddccd2e7a20a069249ac0938067"
OPTIONS = {"txt_page", "txt_default_region", "txt_chop_top", "txt_format",
           "txt_chop_spaces", "txt_duration", "txt_transparent", "txt_opacity"}
BITMAP_BYTES = 492 * 250 * 3
PROBE_TIMEOUT = 10


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def bounded_read(stream, limit):
    data = bytearray()
    while block := await stream.read(min(16384, limit + 1 - len(data))):
        data.extend(block)
        require(len(data) <= limit, "teletext probe output exceeded its bound")
    return bytes(data)


async def run(command, arguments, fixture=b"", limit=65536):
    child = await asyncio.create_subprocess_exec(
        *command, "-hide_banner", "-loglevel", "error", *arguments,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    async def write():
        try:
            child.stdin.write(fixture)
            await child.stdin.drain()
        finally:
            child.stdin.close()
            await child.stdin.wait_closed()

    tasks = [asyncio.create_task(write()),
             asyncio.create_task(bounded_read(child.stdout, limit)),
             asyncio.create_task(bounded_read(child.stderr, 65536)),
             asyncio.create_task(child.wait())]
    try:
        _, output, _, status = await asyncio.wait_for(asyncio.gather(*tasks), PROBE_TIMEOUT)
        require(status == 0, "teletext probe process failed")
        return output
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if child.returncode is None:
            child.kill()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Killing a child does not resume a paused, full asyncio pipe reader.
        # Drain without retaining data so exit/EOF can complete on every host.
        async def discard(stream):
            while await stream.read(16384):
                pass

        await asyncio.wait_for(asyncio.gather(discard(child.stdout),
                                              discard(child.stderr), child.wait()), 2)


async def verify(ffmpeg, fixture_path, expected_sha256=None, emulator=None, sysroot=None, execution_kind="direct"):
    executable_sha256 = sha256(ffmpeg)
    if expected_sha256:
        require(re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "invalid executable digest")
        require(executable_sha256 == expected_sha256, "FFmpeg executable digest differs")
    require(sha256(fixture_path) == FIXTURE_SHA256, "independent fixture digest differs")
    require(bool(emulator) == bool(sysroot), "emulator and sysroot must be supplied together")
    command = [str(ffmpeg)]
    if emulator:
        command = [str(emulator), "-L", str(sysroot), *command]
    fixture = fixture_path.read_bytes()
    version = (await run(command, ["-version"])).decode("utf-8")
    require(re.match(r"ffmpeg version n?9\.\d+(?:\D|$)", version), "FFmpeg 9 is required")
    configuration = (await run(command, ["-buildconf"])).decode("utf-8")
    require("--enable-libzvbi" in configuration, "libzvbi build flag is missing")
    help_text = (await run(command, ["-h", "decoder=libzvbi_teletextdec"])).decode("utf-8")
    actual_options = set(re.findall(r"^\s+-([a-z_]+)\s", help_text, re.MULTILINE))
    require(OPTIONS <= actual_options, "required decoder options are missing")
    text = (await run(command, [
        "-txt_page", "200,888", "-txt_format", "text", "-txt_chop_top", "0",
        "-txt_duration", "1000", "-f", "mpegts", "-i", "pipe:0", "-map", "0:s:0",
        "-c:s", "srt", "-f", "srt", "pipe:1"], fixture)).decode("utf-8")
    require(all(value in text for value in ("TV GUIDE INDEX", "Synthetic subtitle page 888",
            "Independent decoder fixture", "00:00:00,200")), "expected page/caption text is missing")
    require("CHANNEL ONE" not in text, "unselected page 201 was decoded")
    bitmap = await run(command, [
        "-f", "lavfi", "-i", "color=c=black:s=492x250:r=25", "-txt_page", "200",
        "-txt_format", "bitmap", "-txt_chop_top", "0", "-f", "mpegts", "-i", "pipe:0",
        "-filter_complex", r"[0:v][1:s:0]overlay,select=gte(t\,1)", "-t", "2",
        "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
        fixture, BITMAP_BYTES)
    require(len(bitmap) == BITMAP_BYTES, "decoded bitmap dimensions differ")
    cyan = green = 0
    for offset in range(0, len(bitmap), 3):
        red, g, blue = bitmap[offset:offset + 3]
        cyan += red < 80 and g > 160 and blue > 160
        green += red < 80 and g > 160 and blue < 80
    require(cyan > 10 and green > 10, "decoded page colours are missing")
    return {"teletext": "passed", "ffmpeg_sha256": executable_sha256,
            "fixture_sha256": FIXTURE_SHA256, "execution": "emulated" if emulator else execution_kind,
            "selected_pages": [200, 888], "excluded_page": 201,
            "cyan_pixels": cyan, "green_pixels": green}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ffmpeg", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--fixture", type=Path,
                        default=Path(__file__).parent / "fixtures/teletext.ts")
    parser.add_argument("--emulator", type=Path)
    parser.add_argument("--sysroot", type=Path)
    parser.add_argument("--execution-kind", choices=("direct", "emulated"), default="direct",
                        help="Mark external binfmt/container emulation explicitly")
    args = parser.parse_args()
    result = asyncio.run(verify(args.ffmpeg.resolve(), args.fixture.resolve(),
                               args.expected_sha256, args.emulator, args.sysroot, args.execution_kind))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
