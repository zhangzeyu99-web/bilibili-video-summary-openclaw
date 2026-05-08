#!/usr/bin/env python
"""Extract visual frames from a Bilibili video for visual-only summaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
PLAYINFO_RE = re.compile(r"<script>window\.__playinfo__=(.*?)</script>")
INITIAL_STATE_RE = re.compile(r"window\.__INITIAL_STATE__=(.*?);\(function\(\)")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract representative frames from a Bilibili video.")
    parser.add_argument("bv_or_url", help="Bilibili BV id, bilibili.com URL, or b23.tv short URL")
    parser.add_argument("--out", default="video_summaries", help="Output root directory")
    parser.add_argument("--max-frames", type=int, default=12, help="Maximum frames to extract")
    parser.add_argument("--seconds", default="", help="Comma-separated timestamps, overrides --max-frames")
    return parser.parse_args()


def resolve_redirect_location(value: str) -> str | None:
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        value,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"},
    )
    try:
        response = opener.open(req, timeout=20)
        return response.geturl()
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            location = exc.headers.get("Location")
            return urllib.parse.urljoin(value, location) if location else None
        return None
    except Exception:
        return None


def extract_bvid(value: str) -> str:
    match = BVID_RE.search(value)
    if match:
        return match.group(0)
    redirected = resolve_redirect_location(value)
    if redirected:
        match = BVID_RE.search(redirected)
        if match:
            return match.group(0)
    raise SystemExit(f"No BV id found in input: {value}")


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def fetch_page_html(bvid: str) -> str:
    url = f"https://www.bilibili.com/video/{bvid}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"},
    )
    try:
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception:
        pass

    if os.name == "nt":
        command = (
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8; "
            "$ProgressPreference='SilentlyContinue'; "
            f"(Invoke-WebRequest -Uri {ps_quote(url)} -UseBasicParsing).Content"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout

    proc = subprocess.run(
        ["curl", "-L", "-A", "Mozilla/5.0", "-e", "https://www.bilibili.com", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    raise RuntimeError("Failed to fetch Bilibili page HTML for visual extraction.")


def parse_page(html: str) -> tuple[dict[str, Any], dict[str, Any]]:
    play_match = PLAYINFO_RE.search(html)
    if not play_match:
        raise RuntimeError("Cannot find window.__playinfo__ in Bilibili page.")
    playinfo = json.loads(play_match.group(1))
    state: dict[str, Any] = {}
    state_match = INITIAL_STATE_RE.search(html)
    if state_match:
        try:
            state = json.loads(state_match.group(1))
        except Exception:
            state = {}
    return playinfo, state


def choose_video_stream(playinfo: dict[str, Any]) -> dict[str, Any]:
    videos = playinfo.get("data", {}).get("dash", {}).get("video", [])
    if not videos:
        raise RuntimeError("No DASH video stream found in playinfo.")
    return max(videos, key=lambda item: (item.get("width") or 0, item.get("bandwidth") or 0))


def download_video_stream(stream: dict[str, Any], bvid: str, out_dir: Path) -> Path:
    url = stream.get("baseUrl") or stream.get("base_url")
    if not url:
        raise RuntimeError("Selected video stream has no baseUrl.")
    path = out_dir / "video_for_frames.m4s"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://www.bilibili.com/video/{bvid}",
            "Range": "bytes=0-",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response, path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    return path


def frame_seconds(playinfo: dict[str, Any], explicit: str, max_frames: int) -> list[float]:
    if explicit.strip():
        return [float(part.strip()) for part in explicit.split(",") if part.strip()]
    duration = (playinfo.get("data", {}).get("timelength") or 0) / 1000
    if duration <= 0:
        duration = 48
    count = max(1, min(max_frames, int(duration // 2) + 1))
    if count == 1:
        return [0.0]
    step = duration / (count - 1)
    return [round(min(duration, i * step), 2) for i in range(count)]


def extract_frames(video_path: Path, seconds: list[float], frames_dir: Path) -> list[Path]:
    try:
        import av
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyAV is required. Install with: python -m pip install av pillow") from exc

    frames_dir.mkdir(parents=True, exist_ok=True)
    container = av.open(str(video_path))
    stream = container.streams.video[0]
    paths: list[Path] = []
    for second in seconds:
        container.seek(int(second / stream.time_base), stream=stream, any_frame=False, backward=True)
        for frame in container.decode(stream):
            frame_time = float(frame.pts * frame.time_base) if frame.pts is not None else second
            if frame_time >= max(0.0, second - 0.5):
                path = frames_dir / f"frame_{int(round(second)):03d}.png"
                frame.to_image().save(path)
                paths.append(path)
                break
    return paths


def create_montage(paths: list[Path], output: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Pillow is required. Install with: python -m pip install pillow") from exc

    if not paths:
        raise RuntimeError("No frames extracted.")
    images = [Image.open(path).convert("RGB") for path in paths]
    width, height = images[0].size
    thumb_width = 320
    thumb_height = int(height * thumb_width / width)
    cols = min(3, len(images))
    rows = (len(images) + cols - 1) // cols
    canvas = Image.new("RGB", (thumb_width * cols, (thumb_height + 26) * rows), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (path, image) in enumerate(zip(paths, images)):
        x = (index % cols) * thumb_width
        y = (index // cols) * (thumb_height + 26)
        label = path.stem.replace("frame_", "t=") + "s"
        draw.text((x + 6, y + 5), label, fill=(0, 0, 0))
        canvas.paste(image.resize((thumb_width, thumb_height)), (x, y + 26))
    canvas.save(output, quality=92)


def main() -> int:
    args = parse_args()
    bvid = extract_bvid(args.bv_or_url)
    out_dir = Path(args.out).resolve() / bvid
    out_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_page_html(bvid)
    (out_dir / "page.html").write_text(html, encoding="utf-8")
    playinfo, state = parse_page(html)
    stream = choose_video_stream(playinfo)
    video_path = download_video_stream(stream, bvid, out_dir)
    seconds = frame_seconds(playinfo, args.seconds, args.max_frames)
    frames = extract_frames(video_path, seconds, out_dir / "visual_frames")
    montage = out_dir / "frames_montage.jpg"
    create_montage(frames, montage)

    video_data = state.get("videoData") or {}
    result = {
        "ok": True,
        "bvid": bvid,
        "title": video_data.get("title") or "",
        "duration_seconds": round((playinfo.get("data", {}).get("timelength") or 0) / 1000, 2),
        "video_path": str(video_path),
        "frames": [str(path) for path in frames],
        "montage": str(montage),
    }
    (out_dir / "visual_material.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
