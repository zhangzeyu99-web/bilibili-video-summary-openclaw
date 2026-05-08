#!/usr/bin/env python
"""Collect Bilibili video materials for assistant summarization.

The script prefers Bilibili's own metadata, subtitles, and AI summary via
``bili-cli``. When subtitles are unavailable and a deep transcript is requested,
it can fall back to audio-only download plus faster-whisper ASR.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import site
import subprocess
import sys
import sysconfig
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Bilibili video metadata, subtitle/summary, and optional ASR transcript."
    )
    parser.add_argument("bv_or_url", help="Bilibili BV id or URL containing a BV id")
    parser.add_argument(
        "--out",
        default="video_summaries",
        help="Output root directory. A BV-id subdirectory will be created.",
    )
    parser.add_argument(
        "--depth",
        choices=("quick", "deep"),
        default="deep",
        help="quick avoids ASR unless forced; deep falls back to ASR when subtitles are missing.",
    )
    parser.add_argument(
        "--asr",
        choices=("auto", "never", "always"),
        default="auto",
        help="ASR fallback policy.",
    )
    parser.add_argument(
        "--asr-model",
        default="small",
        help="faster-whisper model name/path for ASR fallback, e.g. tiny/base/small.",
    )
    parser.add_argument(
        "--bili",
        default=None,
        help="Path to bili.exe. Defaults to PATH, then %%APPDATA%%/Python/Python314/Scripts/bili.exe.",
    )
    return parser.parse_args()


def resolve_redirect_location(value: str) -> str | None:
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        value,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com",
        },
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


def bili_exe(explicit: str | None) -> str:
    candidates: list[Path] = []
    executable_names = ["bili.exe", "bili.cmd", "bili"]
    if explicit:
        candidates.append(Path(explicit))
    for name in executable_names:
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for scripts_dir in {
        sysconfig.get_path("scripts"),
        str(Path(getattr(site, "USER_BASE", "")) / "Scripts") if getattr(site, "USER_BASE", "") else "",
    }:
        if scripts_dir:
            for name in executable_names:
                candidates.append(Path(scripts_dir) / name)

    appdata = os.environ.get("APPDATA")
    if appdata:
        for name in executable_names:
            candidates.extend((Path(appdata) / "Python").glob(f"Python*/Scripts/{name}"))

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        for name in executable_names:
            candidates.extend((Path(localappdata) / "Programs" / "Python").glob(f"Python*/Scripts/{name}"))

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return str(candidate)
    raise SystemExit("Cannot find bili executable. Pass --bili or install bilibili-cli.")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    return env


def run_command(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=command_env(),
        timeout=timeout,
    )


def parse_first_json(text: str) -> Any:
    stripped = text.lstrip()
    if not stripped:
        raise ValueError("empty stdout")
    return json.JSONDecoder().raw_decode(stripped)[0]


def collect_official(bili: str, bvid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    start = time.time()
    proc = run_command(
        [
            bili,
            "video",
            bvid,
            "--subtitle",
            "--subtitle-timeline",
            "--subtitle-format",
            "timeline",
            "--ai",
            "--json",
        ],
        timeout=180,
    )
    log = {
        "command": " ".join(proc.args),
        "returncode": proc.returncode,
        "elapsed_sec": round(time.time() - start, 2),
        "stderr": proc.stderr.strip(),
    }
    try:
        payload = parse_first_json(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        log["stdout_head"] = proc.stdout[:2000]
        raise RuntimeError(f"Failed to parse bili-cli JSON: {exc}") from exc
    return payload, log


def should_run_asr(payload: dict[str, Any], depth: str, policy: str) -> bool:
    if policy == "never":
        return False
    if policy == "always":
        return True
    data = payload.get("data") or {}
    subtitle = data.get("subtitle") or {}
    text = subtitle.get("text") or ""
    if depth == "quick":
        return False
    return not (subtitle.get("available") and len(text.strip()) > 80)


def download_audio(bili: str, bvid: str, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    proc = run_command([bili, "audio", bvid, "--no-split", "-o", str(audio_dir)], timeout=240)
    audio_files = [
        p
        for p in audio_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".m4a", ".m4s", ".mp3", ".wav", ".aac"}
    ]
    if not audio_files:
        raise RuntimeError(
            "bili audio did not create an audio file. stderr="
            + proc.stderr.strip()
            + " stdout="
            + proc.stdout[:1000]
        )
    newest = max(audio_files, key=lambda p: p.stat().st_mtime)
    log = {
        "command": " ".join(proc.args),
        "returncode": proc.returncode,
        "elapsed_sec": round(time.time() - start, 2),
        "stderr": proc.stderr.strip(),
        "stdout_tail": proc.stdout[-1000:],
        "audio_path": str(newest),
        "audio_bytes": newest.stat().st_size,
    }
    return newest, log


def transcribe_audio(audio_path: Path, model_name: str, out_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    start = time.time()
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("faster-whisper is not installed") from exc

    threads = min(8, os.cpu_count() or 4)
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=threads,
        num_workers=1,
    )
    segments_iter, info = model.transcribe(
        str(audio_path),
        language="zh",
        task="transcribe",
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    segments: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue
        segments.append({"from": round(seg.start, 2), "to": round(seg.end, 2), "content": text})
        texts.append(text)

    result = {
        "available": True,
        "source": f"faster-whisper:{model_name}:int8",
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "text": "\n".join(texts),
        "items": segments,
    }
    log = {
        "elapsed_sec": round(time.time() - start, 2),
        "model": model_name,
        "threads": threads,
        "segments": len(segments),
        "chars": len(result["text"]),
    }
    (out_dir / "asr_transcript.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result, log


def write_outputs(
    out_dir: Path,
    bvid: str,
    payload: dict[str, Any],
    transcript: dict[str, Any],
    logs: dict[str, Any],
) -> dict[str, str]:
    data = payload.get("data") or {}
    video = data.get("video") or {}
    ai_summary = data.get("ai_summary") or ""
    subtitle = data.get("subtitle") or {}

    material = {
        "bvid": bvid,
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": video,
        "official_ai_summary": ai_summary,
        "official_subtitle": subtitle,
        "transcript": transcript,
        "logs": logs,
    }

    material_path = out_dir / "material.json"
    transcript_path = out_dir / "transcript.txt"
    prompt_path = out_dir / "summary_input.md"
    log_path = out_dir / "run_log.json"

    material_path.write_text(json.dumps(material, ensure_ascii=False, indent=2), encoding="utf-8")
    transcript_text = transcript.get("text") or ""
    transcript_path.write_text(transcript_text, encoding="utf-8-sig")

    stats = video.get("stats") or {}
    prompt = [
        f"# Bilibili Video Material: {video.get('title', bvid)}",
        "",
        f"- BVID: {bvid}",
        f"- URL: {video.get('url', '')}",
        f"- Owner: {(video.get('owner') or {}).get('name', '')}",
        f"- Duration: {video.get('duration', video.get('duration_seconds', ''))}",
        f"- Views/Likes/Coins/Favorites: {stats.get('view', '')}/{stats.get('like', '')}/{stats.get('coin', '')}/{stats.get('favorite', '')}",
        f"- Transcript source: {transcript.get('source', 'official-subtitle')}",
        "",
        "## Official AI Summary",
        ai_summary or "(none)",
        "",
        "## Transcript",
        transcript_text or "(none)",
        "",
    ]
    prompt_path.write_text("\n".join(prompt), encoding="utf-8-sig")
    log_path.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "material": str(material_path),
        "transcript": str(transcript_path),
        "summary_input": str(prompt_path),
        "run_log": str(log_path),
    }


def main() -> int:
    args = parse_args()
    bvid = extract_bvid(args.bv_or_url)
    out_dir = Path(args.out).resolve() / bvid
    out_dir.mkdir(parents=True, exist_ok=True)

    bili = bili_exe(args.bili)
    logs: dict[str, Any] = {"bili_exe": bili}

    payload, official_log = collect_official(bili, bvid)
    logs["official"] = official_log
    data = payload.get("data") or {}
    subtitle = data.get("subtitle") or {}

    transcript: dict[str, Any] = {
        "available": bool(subtitle.get("available")),
        "source": "bilibili-subtitle",
        "text": subtitle.get("text") or "",
        "items": subtitle.get("items") or [],
    }

    if should_run_asr(payload, args.depth, args.asr):
        audio_path, audio_log = download_audio(bili, bvid, out_dir)
        logs["audio"] = audio_log
        transcript, asr_log = transcribe_audio(audio_path, args.asr_model, out_dir)
        logs["asr"] = asr_log
    else:
        logs["asr"] = {"skipped": True, "reason": "subtitle_available_or_policy"}

    paths = write_outputs(out_dir, bvid, payload, transcript, logs)
    result = {
        "ok": True,
        "bvid": bvid,
        "title": ((data.get("video") or {}).get("title") or ""),
        "duration": ((data.get("video") or {}).get("duration") or ""),
        "has_ai_summary": bool(data.get("ai_summary")),
        "transcript_source": transcript.get("source"),
        "transcript_chars": len(transcript.get("text") or ""),
        "paths": paths,
        "elapsed": logs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
