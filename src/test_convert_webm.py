#!/usr/bin/env python3
"""
Test: generate synthetic webm (vp8), convert to mp4/h264 ≤1080p with ffmpeg,
and verify the output with ffprobe.
Standalone — no project imports.
"""

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s %(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def ffprobe_info(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    data = json.loads(r.stdout)
    for s in data.get("streams", []):
        if s["codec_type"] == "video":
            return {"codec": s.get("codec_name"), "w": s.get("width", 0), "h": s.get("height", 0)}
    return {"codec": None, "w": 0, "h": 0}


def test_webm_to_mp4(height: int, fps: int = 24, duration: int = 3):
    """Generate a synthetic webm of given height, convert to mp4, verify."""
    log.info("=" * 60)
    log.info("Test: %dp webm -> mp4/h264", height)

    with tempfile.TemporaryDirectory(prefix=f"test-webm-{height}p-") as tmp:
        tmpdir = Path(tmp)
        webm_path = tmpdir / f"input_{height}p.webm"
        mp4_path = tmpdir / "output.mp4"

        # 1. generate synthetic webm with ffmpeg
        log.info("Generating %dp webm (vp8)...", height)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"testsrc=size={height*16//9}x{height}:rate={fps}:duration={duration}",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:v", "libvpx",
                "-b:v", "500k",
                "-c:a", "libvorbis",
                "-shortest",
                str(webm_path),
            ],
            capture_output=True, check=True, timeout=120,
        )

        orig_info = ffprobe_info(webm_path)
        log.info("Original: ext=%s codec=%s %dx%d size=%d",
                 webm_path.suffix, orig_info["codec"],
                 orig_info["w"], orig_info["h"], webm_path.stat().st_size)

        # verify it's actually webm
        assert webm_path.suffix.lower() == ".webm", f"Expected .webm, got {webm_path.suffix}"

        # 2. convert with the same logic as ensure_streamable_video
        cmd = [
            "ffmpeg", "-y",
            "-i", str(webm_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
        ]
        if height > 720:
            cmd.extend(["-vf", "scale='if(gt(iw,ih),min(720,iw),-2)':'if(gt(iw,ih),-2,min(720,ih))':force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2"])

        cmd.append(str(mp4_path))

        log.info("Converting webm -> mp4 ...")
        subprocess.run(cmd, capture_output=True, timeout=300)

        # 3. verify output
        assert mp4_path.exists(), "mp4 not created"
        assert mp4_path.stat().st_size > 0, "mp4 is empty"

        new_info = ffprobe_info(mp4_path)
        log.info("Converted: ext=%s codec=%s %dx%d size=%d",
                 mp4_path.suffix, new_info["codec"],
                 new_info["w"], new_info["h"], mp4_path.stat().st_size)

        checks = 0
        if new_info["codec"] != "h264":
            log.error("FAIL: codec = %s (expected h264)", new_info["codec"])
        else:
            checks += 1

        if mp4_path.suffix.lower() != ".mp4":
            log.error("FAIL: ext = %s (expected .mp4)", mp4_path.suffix)
        else:
            checks += 1

        if height > 720:
            # scale was applied — longest edge must be ≤720
            longest = max(new_info["w"], new_info["h"])
            if longest > 720:
                log.error("FAIL: longest edge = %d (expected ≤720)", longest)
            else:
                checks += 1
        else:
            # no scale — original dimensions unchanged
            if new_info["w"] == orig_info["w"] and new_info["h"] == orig_info["h"]:
                checks += 1
            else:
                log.error("FAIL: dimensions changed from %dx%d to %dx%d",
                          orig_info["w"], orig_info["h"], new_info["w"], new_info["h"])

        if checks == 3:
            log.info("PASS: %dp webm -> mp4/h264 %dx%d", height, new_info["w"], new_info["h"])
        else:
            sys.exit(1)


def main():
    # test 360p webm (no resize needed)
    test_webm_to_mp4(360, duration=1, fps=30)
    # test 1080p webm (should scale down to 720p)
    test_webm_to_mp4(1080, duration=1, fps=30)
    log.info("=" * 60)
    log.info("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
