---
name: bilibili-video-summary
description: Use when summarizing Bilibili or B站 videos from BV IDs, bilibili.com URLs, or b23.tv short links; especially when official subtitles, AI summaries, ASR fallback, visual frame extraction, or fast video-summary material collection are needed.
---

# Bilibili Video Summary

Use this skill to collect Bilibili video material before writing a summary. Prefer official metadata, AI summary, and subtitles. Use ASR only when text is missing. Use visual frame extraction when the video is visual-only or ASR returns empty text.

## Workflow

1. Run the fast text-first pass:

   ```powershell
   python scripts\bili_video_material.py "<BV-or-URL>" --depth quick --asr never
   ```

2. Read `video_summaries\<BVID>\summary_input.md` and `material.json`.
3. If official AI summary or transcript text is useful, write the final summary from those materials.
4. If transcript text is empty, rerun with ASR:

   ```powershell
   python scripts\bili_video_material.py "<BV-or-URL>" --depth deep --asr auto --asr-model base
   ```

5. If ASR is still empty, extract visual frames:

   ```powershell
   python scripts\bili_video_frames.py "<BV-or-URL>" --max-frames 12
   ```

   Open `video_summaries\<BVID>\frames_montage.jpg` and summarize from the image sequence. Clearly say the summary is based on visual frames when there is no subtitle or speech transcript.

## Output Policy

- Default to Chinese final summaries unless the user asks otherwise.
- Separate confirmed video facts from inference.
- Do not invent narration when official subtitles and ASR are empty.
- For short videos, include title, BV id, duration, source basis, core message, and practical judgment.

## Dependencies

Required:

- Python 3.10+
- `bili` from `bilibili-cli`, authenticated when needed

Optional:

- `faster-whisper` for ASR fallback
- `av` and `pillow` for visual frame extraction

If `bili` is not on PATH, the bundled script scans common Python `Scripts` directories. If login expires, run `bili login` and retry.
