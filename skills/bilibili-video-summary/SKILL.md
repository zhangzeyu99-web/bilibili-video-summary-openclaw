---
name: bilibili-video-summary
description: Use when summarizing Bilibili videos from BV IDs or bilibili.com links, especially when official subtitles, AI summaries, fast material extraction, or ASR fallback are needed.
---

# Bilibili Video Summary

Use this skill to collect Bilibili video material before writing a summary. The workflow prefers official Bilibili metadata, AI summary, and subtitles, then falls back to audio ASR only when necessary.

## Workflow

1. Resolve the BV id from the user input. Accept either `BV...` or a `bilibili.com/video/...` URL.
2. From this skill directory, run:

   ```powershell
   python scripts\bili_video_material.py "<BV-or-URL>"
   ```

   The script writes output under `video_summaries\<BVID>\` in the current workspace.

3. Read `video_summaries\<BVID>\summary_input.md`.
4. Write the final answer from the collected material, not from memory. Keep the summary concise and separate facts from inference when the video material is incomplete.

## Speed Policy

- Default mode uses official Bilibili AI summary and subtitles first.
- If subtitles are available, do not run ASR.
- Use quick official-only mode when the user cares most about speed:

  ```powershell
  python scripts\bili_video_material.py "<BV-or-URL>" --depth quick --asr never
  ```

- Use ASR only when official subtitles are missing and the user needs a deeper summary:

  ```powershell
  python scripts\bili_video_material.py "<BV-or-URL>" --depth deep --asr auto
  ```

## Dependencies

Required:

- Python 3.10+
- `bili` from `bilibili-cli`, authenticated with Bilibili if the video requires login

Optional for ASR fallback:

- `faster-whisper`
- FFmpeg or a media stack supported by the local audio decoder

If `bili` login has expired, run `bili login` in the user's terminal/browser flow, then retry the script.

## Expected Outputs

- `summary_input.md`: compact prompt material for the assistant
- `transcript.txt`: transcript text only
- `material.json`: structured metadata, official AI summary, subtitles, transcript, and run logs
- `run_log.json`: command timings and fallback decisions
