# Bilibili Video Summary Flow

This repo uses `tools/bili_video_material.py` to collect video materials before
the assistant writes the final summary.

## Default Command

```powershell
python tools\bili_video_material.py "https://www.bilibili.com/video/BVxxxx/"
```

The script writes materials to:

```text
video_summaries\<BVID>\
```

Key outputs:

- `summary_input.md`: compact file for assistant summarization.
- `transcript.txt`: transcript text only.
- `material.json`: structured metadata, official AI summary, subtitles, transcript, and run logs.
- `run_log.json`: command timings and fallback details.

## Flow

1. Extract the BV id from the URL.
2. Run `bili-cli` with saved Bilibili login credentials:

   ```powershell
   bili video <BVID> --subtitle --subtitle-timeline --subtitle-format timeline --ai --json
   ```

3. If Bilibili subtitles are available, use them and skip ASR.
4. If subtitles are missing and `--depth deep` is used, download audio-only and run `faster-whisper`.
5. The assistant reads `summary_input.md` and writes the final user-facing summary.

## Useful Modes

Fast official-only pass:

```powershell
python tools\bili_video_material.py "BVxxxx" --depth quick --asr never
```

Force local ASR:

```powershell
python tools\bili_video_material.py "BVxxxx" --asr always --asr-model small
```

Use a lighter ASR model when speed matters more than term accuracy:

```powershell
python tools\bili_video_material.py "BVxxxx" --asr always --asr-model base
```

## Current Local Baseline

After Bilibili login, both tested videos returned official subtitles and AI
summary in about 2.5 seconds, with ASR skipped.

If Bilibili credentials expire, run:

```powershell
C:\Users\Administrator\AppData\Roaming\Python\Python314\Scripts\bili.exe login
```

