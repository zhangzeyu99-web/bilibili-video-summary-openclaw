# Bilibili Video Summary OpenClaw Skill

这是一个用于 B 站视频总结的 OpenClaw skill/plugin 包。它把“看视频”拆成可复用的材料采集流程：先拿 Bilibili 官方 AI 总结和字幕，只有缺字幕时才走音频下载与本地 ASR。

## 当前流程

1. 从 B 站链接或 BV 号提取 `BVID`。
2. 调用 `bili video <BVID> --subtitle --subtitle-timeline --subtitle-format timeline --ai --json`。
3. 如果官方字幕可用，直接生成总结输入，跳过 ASR。
4. 如果没有字幕，并且使用 deep 模式，再下载音频并调用 `faster-whisper`。
5. 读取 `video_summaries\<BVID>\summary_input.md`，由模型输出最终总结。

本机测试里，两个测试视频都能在约 2.5 秒拿到官方字幕和 AI 总结，ASR 被跳过。

## 直接运行工具

```powershell
python tools\bili_video_material.py "https://www.bilibili.com/video/BVxxxx/"
```

快速官方模式：

```powershell
python tools\bili_video_material.py "BVxxxx" --depth quick --asr never
```

输出目录：

```text
video_summaries\<BVID>\
```

关键文件：

- `summary_input.md`
- `transcript.txt`
- `material.json`
- `run_log.json`

## OpenClaw 安装方式

不要手动复制 skill。发布到 GitHub 后，用 OpenClaw 自己从 GitHub 安装：

```powershell
openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force
```

验证：

```powershell
openclaw skills list --eligible --json
```

列表里应该出现 `bilibili-video-summary`。

## 依赖

必需：

- Python 3.10+
- `bili` CLI，并完成 Bilibili 登录

可选：

- `faster-whisper`
- FFmpeg

只有在官方字幕缺失且需要 deep 模式时，才需要 ASR 相关依赖。
