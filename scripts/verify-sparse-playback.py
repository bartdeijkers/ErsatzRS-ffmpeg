#!/usr/bin/env python3
"""Verify bounded pacing, sparse PGS rendering and alternate audio.

Usage: python3 scripts/verify-sparse-playback.py /path/to/ffmpeg[.exe]
The sibling ffprobe is required. Windows executables run through WSL interop;
all paths belong to a disposable synthetic fixture. No user media is accessed.
"""
import json, pathlib, selectors, struct, subprocess, tempfile, time, sys

workspace = tempfile.TemporaryDirectory(prefix="ersatzrs-readrate-")
root = pathlib.Path(workspace.name)
ffmpeg = pathlib.Path(sys.argv[1])
ffprobe = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
windows = ffmpeg.suffix == ".exe"


def path(p):
    return (
        subprocess.check_output(["wslpath", "-w", str(p)], text=True).strip()
        if windows
        else str(p)
    )


def run(tool, args, timeout=40):
    result = subprocess.run(
        [str(tool), *map(str, args)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def pace(args):
    global progress_metrics
    points = []
    fields = {}
    pending = b""
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            [
                str(ffmpeg),
                "-nostats",
                "-stats_period",
                "0.1",
                "-progress",
                "pipe:1",
                *map(str, args),
            ],
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                if time.monotonic() - start > 35:
                    raise TimeoutError("35-second playback deadline exceeded")
                if not selector.select(0.25):
                    continue
                data = process.stdout.read1(4096)
                if not data:
                    break
                pending += data
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    key, _, value = line.decode().partition("=")
                    fields[key] = value
                    if key == "progress" and fields.get("out_time_us", "N/A") != "N/A":
                        points.append(
                            (
                                time.monotonic() - start,
                                int(fields["out_time_us"]) / 1000000,
                            )
                        )
            status = process.wait(timeout=3)
            if status:
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors="replace"))
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    assert points, "missing progress"
    changed = [points[0]]
    for point in points[1:]:
        if point[1] > changed[-1][1] + 0.05:
            changed.append(point)
    longest_gap = max(b[0] - a[0] for a, b in zip(changed, changed[1:]))
    lead = max(media - wall for wall, media in points)
    progress_metrics = {
        "max_media_lead_seconds": round(lead, 3),
        "max_progress_gap_seconds": round(longest_gap, 3),
    }
    assert lead < 1.0, progress_metrics
    assert longest_gap < 2.0, progress_metrics


out = bytearray()


def seg(t, k, p):
    out.extend(b"PG" + struct.pack(">IIBH", t * 90000, t * 90000, k, len(p)) + p)


for t in [0, 2, 10, 14]:
    x = 30 if t < 10 else 230
    seg(
        t,
        0x16,
        struct.pack(">HHBH", 320, 180, 0x30, t)
        + bytes([0x80, 0, 0, 1, 0, 0, 0, 0])
        + struct.pack(">HH", x, 140),
    )
    seg(t, 0x17, bytes([1, 0]) + struct.pack(">HHHH", x, 140, 60, 24))
    seg(t, 0x14, bytes([0, 0, 0, 16, 128, 128, 0, 1, 235, 128, 128, 255]))
    seg(
        t,
        0x15,
        bytes([0, 0, 0, 0xC0, 0, 0, 124, 0, 60, 0, 24])
        + bytes([0, 0xBC, 1, 0, 0]) * 24,
    )
    seg(t, 0x80, b"")
(root / "sparse.sup").write_bytes(out)
clip = root / ("windows-source.mkv" if windows else "linux-source.mkv")
result = root / ("windows-output.mkv" if windows else "linux-output.mkv")
run(
    ffmpeg,
    [
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=black:size=320x180:rate=25:duration=16",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=16",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000:duration=16",
        "-i",
        path(root / "sparse.sup"),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-map",
        "3:s",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "pcm_s16le",
        "-c:s",
        "copy",
        "-metadata:s:a:0",
        "language=eng",
        "-metadata:s:a:1",
        "language=nld",
        "-t",
        "16",
        path(clip),
    ],
)
start = time.monotonic()
pace(
    [
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-readrate",
        "1",
        "-readrate_initial_burst",
        "0",
        "-i",
        path(clip),
        "-filter_complex",
        "[0:v:0][0:s:0]overlay=eof_action=pass[v]",
        "-map",
        "[v]",
        "-map",
        "0:a:1",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "pcm_s16le",
        "-t",
        "16",
        path(result),
    ]
)
elapsed = time.monotonic() - start
assert elapsed < 20, elapsed
info = json.loads(
    run(
        ffprobe,
        [
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,nb_read_frames,duration:format=duration",
            "-of",
            "json",
            path(result),
        ],
    )
)
assert info["streams"][0]["nb_read_frames"] == "400", info
assert 15.9 <= float(info["format"]["duration"]) <= 16.1, info
for second, expected_x in [(3, 30), (11, 230)]:
    rgb = run(
        ffmpeg,
        [
            "-v",
            "error",
            "-nostdin",
            "-ss",
            str(second),
            "-i",
            path(result),
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
    )
    count = sum(
        all(c > 180 for c in rgb[(y * 320 + x) * 3 : (y * 320 + x) * 3 + 3])
        for y in range(140, 164)
        for x in range(expected_x, expected_x + 60)
    )
    assert count > 1300, (second, count)
audio = run(
    ffmpeg,
    [
        "-v",
        "error",
        "-nostdin",
        "-i",
        path(result),
        "-map",
        "0:a",
        "-ac",
        "1",
        "-ar",
        "8000",
        "-f",
        "s16le",
        "pipe:1",
    ],
)
samples = struct.unpack("<" + "h" * (len(audio) // 2), audio)
assert len(samples) >= 127000, len(samples)
crossings = sum(a <= 0 < b for a, b in zip(samples, samples[1:]))
frequency = crossings * 8000 / len(samples)
assert 870 < frequency < 890, frequency
run(
    ffmpeg,
    ["-v", "error", "-xerror", "-nostdin", "-i", path(result), "-f", "null", "-"],
)
print(
    json.dumps(
        {
            "platform": "windows" if windows else "linux",
            "elapsed_seconds": round(elapsed, 3),
            "frames": 400,
            "duration": info["format"]["duration"],
            "selected_audio_hz": round(frequency, 2),
            "bitmap_before_after_gap": "passed",
            "decode": "passed",
            **progress_metrics,
        }
    )
)

workspace.cleanup()
