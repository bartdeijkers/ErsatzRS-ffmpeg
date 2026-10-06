#!/usr/bin/env python3
"""Verify animated-WebP frame order, embedded loops and generic fractional seek.

Usage: python3 scripts/verify-webp.py /path/to/ffmpeg[.exe]
Optional: --source-file /path/to/libavformat/webp_anim_dec.c --cc cc
The source option runs an exact-block C harness for ICC/EXIF short-read cleanup,
which cannot be established from a successful ffprobe exit. No user media,
third-party Python packages or hardware acceleration are required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

SIZE = 64
COLORS = ((0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0))
FRAME_BYTES = SIZE * SIZE * 3


def chunk(tag, payload, declared_size=None):
    size = len(payload) if declared_size is None else declared_size
    return tag + struct.pack("<I", size) + payload + (b"\0" if declared_size is None and len(payload) & 1 else b"")


def chunks(data):
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", "invalid fixture RIFF"
    offset = 12
    result = []
    while offset < len(data):
        tag = data[offset:offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        result.append((tag, data[offset + 8:offset + 8 + size]))
        offset += 8 + size + (size & 1)
    assert offset == len(data), "truncated generated fixture"
    return result


def riff(body):
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


def metadata_harness(source, compiler, directory):
    """Execute the actual two patched blocks against observable I/O stubs.

    This proves their error return and allocation removal, not an FFmpeg ABI or
    native-platform acceptance. The compiled CLI tests supply separate runtime
    evidence. Extraction intentionally fails when source structure changes.
    """
    text = source.read_text()
    blocks = []
    for field in ("iccp", "exif"):
        end = text.index(f"ctx->has_{field} = 1;") + len(f"ctx->has_{field} = 1;")
        start = text.rfind("AVPacketSideData *sd =", 0, end)
        block = text[start:end]
        assert "ffio_read_size" in block, f"{field} exact-read correction missing"
        assert "av_packet_side_data_remove" in block, f"{field} allocation cleanup missing"
        blocks.append(block)
    harness = r'''#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define AVERROR(e) (-(e))
#define AV_PKT_DATA_ICC_PROFILE 1
#define AV_PKT_DATA_EXIF 2
typedef struct { unsigned char *data; int type; } AVPacketSideData;
typedef struct { AVPacketSideData *coded_side_data; int nb_coded_side_data; } Codec;
typedef struct { Codec *codecpar; } Stream;
typedef struct { int has_iccp; int has_exif; } Context;
static int short_read;
static AVPacketSideData *av_packet_side_data_new(AVPacketSideData **p, int *n, int type, int size, int unused) {
    (void)unused;
    *p = calloc(1, sizeof(**p)); (*p)->data = malloc(size); (*p)->type = type;
    memset((*p)->data, 0xcc, size); ++*n; return *p;
}
static int ffio_read_size(void *pb, unsigned char *data, int size) {
    (void)pb;
    int available = short_read ? size - 1 : size;
    memset(data, 0x42, available);
    return short_read ? -5 : size;
}
static void av_packet_side_data_remove(AVPacketSideData *p, int *n, int type) {
    if (p && p->type == type) { free(p->data); p->data = NULL; --*n; }
}
'''
    for field, block in zip(("iccp", "exif"), blocks):
        harness += f"static int check_{field}(Stream *st, Context *ctx) {{ void *pb = NULL; int size = 16, ret;\n{block}\nreturn 0; }}\n"
    harness += r'''int main(void) {
    for (int field = 0; field < 2; ++field) {
        for (short_read = 0; short_read < 2; ++short_read) {
            Codec codec = {0}; Stream stream = {&codec}; Context context = {0};
            int ret = field ? check_exif(&stream, &context) : check_iccp(&stream, &context);
            int flag = field ? context.has_exif : context.has_iccp;
            if (short_read) {
                if (ret >= 0 || codec.nb_coded_side_data != 0 || flag || codec.coded_side_data->data) return 1;
            } else {
                if (ret || codec.nb_coded_side_data != 1 || !flag || codec.coded_side_data->data[15] != 0x42) return 2;
                free(codec.coded_side_data->data);
            }
            free(codec.coded_side_data);
        }
    }
    puts("ICCP and EXIF: full reads retained, short reads removed"); return 0;
}
'''
    c_file = directory / "metadata-harness.c"
    c_file.write_text(harness)
    binary = directory / ("metadata-harness.exe" if os.name == "nt" else "metadata-harness")
    subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", str(c_file), "-o", str(binary)], check=True, capture_output=True, timeout=30)
    subprocess.run([str(binary)], check=True, capture_output=True, timeout=10)
    return {"status": "passed", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "scope": "exact source blocks with instrumented short-read and allocation stubs"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ffmpeg", type=Path)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--metadata-harness", type=Path, help="actual-library verify-webp-metadata binary")
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    ffmpeg = args.ffmpeg.resolve()
    ffprobe = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
    windows_interop = ffmpeg.suffix.lower() == ".exe" and os.name != "nt"

    def native_path(value):
        if windows_interop:
            return subprocess.check_output(["wslpath", "-w", str(value)], text=True, timeout=10).strip()
        return str(value)

    def run(tool, options, data=None, allow_error=False):
        result = subprocess.run([str(tool), "-hide_banner", "-loglevel", "error", *options], input=data, capture_output=True, timeout=30)
        if result.returncode and not allow_error:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result

    results = []
    with tempfile.TemporaryDirectory(prefix="ersatzrs-webp-") as directory:
        root = Path(directory)
        frames = b"".join(bytes(color) * (SIZE * SIZE) for color in COLORS)
        webp = root / "animation.webp"
        gif = root / "animation.gif"
        common = ["-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{SIZE}x{SIZE}", "-framerate", "2", "-i", "pipe:0", "-frames:v", "4"]
        run(ffmpeg, common + ["-c:v", "libwebp_anim", "-lossless", "1", "-loop", "1", native_path(webp)], frames)
        run(ffmpeg, common + ["-loop", "0", native_path(gif)], frames)
        original = chunks(webp.read_bytes())
        assert sum(tag == b"ANMF" for tag, _ in original) == 4, "encoder did not preserve four distinct frames"
        animations = {}
        for loops in (0, 1, 2):
            body = b"".join(chunk(tag, payload[:4] + struct.pack("<H", loops) if tag == b"ANIM" else payload) for tag, payload in original)
            path = root / f"loop-{loops}.webp"
            path.write_bytes(riff(body))
            animations[loops] = path

        def decode(name, source, input_options, expected, limit=None):
            options = ["-nostdin", *input_options, "-i", native_path(source)]
            if limit is not None:
                options += ["-frames:v", str(limit)]
            result = run(ffmpeg, options + ["-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
            data = result.stdout
            assert len(data) == len(expected) * FRAME_BYTES, f"{name}: expected {len(expected)} frames, got {len(data) / FRAME_BYTES}"
            for index, color in enumerate(expected):
                # Verify the whole central area, including colour through every
                # rewind. Merely counting packets would miss stale/blank frames.
                for y in range(24, 40):
                    for x in range(24, 40):
                        offset = index * FRAME_BYTES + (y * SIZE + x) * 3
                        actual = data[offset:offset + 3]
                        assert all(abs(a - b) <= 4 for a, b in zip(actual, color)), f"{name}: frame {index} colour {tuple(actual)} != {color}"
            assert b"Error during demuxing" not in result.stderr, f"{name}: demuxing reported an error"
            results.append({"case": name, "decoded_frames": len(expected), "frame_order": "passed", "bounded_exit": "passed"})

        decode("embedded-once", animations[1], ["-ignore_loop", "0"], COLORS)
        decode("embedded-twice", animations[2], ["-ignore_loop", "0"], COLORS * 2)
        decode("embedded-infinite-bounded", animations[0], ["-ignore_loop", "0"], COLORS * 3, 12)
        for loops in (0, 1, 2):
            decode(f"generic-three-cycles-embedded-{loops}", animations[loops], ["-ignore_loop", "1", "-stream_loop", "2"], COLORS * 3)
            decode(f"generic-infinite-seek-500ms-embedded-{loops}", animations[loops], ["-ignore_loop", "1", "-stream_loop", "-1", "-ss", "0.5"], (COLORS[1:] + COLORS + COLORS + COLORS[:1]), 12)
        decode("gif-generic-repeat-control", gif, ["-ignore_loop", "1", "-stream_loop", "2"], COLORS * 3)
        decode("gif-generic-seek-control", gif, ["-ignore_loop", "1", "-stream_loop", "-1", "-ss", "0.5"], COLORS[1:] + COLORS + COLORS + COLORS[:1], 12)

        # Input-side duration bound, matching scheduled media: no frame cache,
        # explicit finite programme duration, and natural process termination.
        bounded = run(ffmpeg, ["-nostdin", "-ignore_loop", "1", "-stream_loop", "-1", "-i", native_path(animations[1]), "-t", "6", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
        assert len(bounded.stdout) == 12 * FRAME_BYTES, "programme duration did not bound repetition to 12 frames"
        results.append({"case": "six-second-programme-bound", "decoded_frames": 12, "bounded_exit": "passed"})

        packet_info = json.loads(run(ffprobe, ["-show_packets", "-show_entries", "packet=pos,flags,duration_time", "-of", "json", native_path(animations[1])]).stdout)
        offsets = []
        offset = 12
        for tag, payload in original:
            if tag == b"ANMF":
                offsets.append(offset)
            offset += 8 + len(payload) + (len(payload) & 1)
        packets = packet_info["packets"]
        assert [int(packet["pos"]) for packet in packets] == offsets, "packet positions must address ANMF headers"
        assert "K" in packets[0]["flags"], "first animation frame lost its keyframe flag"
        assert all(abs(float(packet["duration_time"]) - 0.5) < 0.000001 for packet in packets), "animation frame duration changed"

        metadata_cases = []
        metadata_paths = {}
        for tag, bit in ((b"ICCP", 0x20), (b"EXIF", 0x08)):
            tagged = [(name, bytes([payload[0] | bit]) + payload[1:] if name == b"VP8X" else payload) for name, payload in original]
            body = b"".join(chunk(name, payload) for name, payload in tagged)
            if tag == b"ICCP":
                payload = bytearray(128)
                payload[:4] = struct.pack(">I", 128)
                payload[36:40] = b"acsp"
                first = chunk(*tagged[0])
                valid_body = first + chunk(tag, bytes(payload)) + body[len(first):]
            else:
                payload = b"II\x2a\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                valid_body = body + chunk(tag, payload)
            valid_path = root / f"valid-{tag.decode().lower()}.webp"
            valid_path.write_bytes(riff(valid_body))
            valid_info = json.loads(run(ffprobe, ["-show_packets", "-of", "json", native_path(valid_path)]).stdout)
            assert len(valid_info.get("packets", [])) == 4, "full metadata read changed animation packet count"
            metadata_paths[f"valid_{tag.decode().lower()}"] = valid_path
            malformed = chunk(tag, b"\0\0", declared_size=64)
            if tag == b"ICCP":
                first = chunk(*tagged[0])
                body = first + malformed  # Header parser encounters short ICCP.
            else:
                body += malformed  # Packet parser encounters short EXIF after frames.
            path = root / f"truncated-{tag.decode().lower()}.webp"
            path.write_bytes(riff(body))
            metadata_paths[f"truncated_{tag.decode().lower()}"] = path
            info = run(ffprobe, ["-show_packets", "-show_streams", "-of", "json", native_path(path)], allow_error=True)
            parsed = json.loads(info.stdout or b"{}")
            if tag == b"ICCP":
                assert info.returncode != 0 and not parsed.get("streams"), "short ICCP header was accepted"
            else:
                assert len(parsed.get("packets", [])) == 4, "truncated EXIF corrupted preceding animation packets"
            metadata_cases.append({"case": tag.decode(), "bounded_exit": "passed", "cli_returncode": info.returncode})
        source_check = metadata_harness(args.source_file.resolve(), args.cc, root) if args.source_file else {"status": "not run", "reason": "--source-file is required for instrumented exact-block proof"}
        library_check = {"status": "not run", "reason": "--metadata-harness is required for actual-library cleanup proof"}
        if args.metadata_harness:
            executable = args.metadata_harness.resolve()
            subprocess.run([str(executable), *(str(metadata_paths[key]) for key in ("valid_iccp", "truncated_iccp", "valid_exif", "truncated_exif"))], check=True, capture_output=True, timeout=30)
            library_check = {"status": "passed", "harness_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "scope": "actual built demuxer preserves full ICC/EXIF and removes incomplete side data"}

    print(json.dumps({"ffmpeg_sha256": hashlib.sha256(ffmpeg.read_bytes()).hexdigest(), "ffprobe_sha256": hashlib.sha256(ffprobe.read_bytes()).hexdigest(), "animation_cases": results, "packet_header_positions": "passed", "truncated_metadata_runtime": metadata_cases, "metadata_cleanup_source_harness": source_check, "metadata_cleanup_actual_library": library_check}, indent=2))


if __name__ == "__main__":
    main()
