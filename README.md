# Bilibili Video Summary OpenClaw Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

这是一个给 OpenClaw 使用的 B 站视频总结 skill/plugin 包。目标不是“模拟人工看完整个视频”，而是先用 Bilibili 官方接口拿到元数据、AI 总结和字幕；只有官方字幕缺失时，才降级到音频下载和本地 ASR。这样常见视频可以在几秒内进入总结阶段。

## 一句话安装

新设备已经装好 OpenClaw 后，直接运行：

```powershell
openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force
openclaw gateway restart
openclaw skills list --eligible --json
```

`skills list` 里出现 `bilibili-video-summary` 就说明 OpenClaw 已经从 GitHub 安装成功。

## 新设备配置

Windows / PowerShell 推荐流程：

```powershell
git clone https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git
cd bilibili-video-summary-openclaw
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Login -SmokeTest
openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force
openclaw gateway restart
```

`setup.ps1` 会做这些事：

- 检查 Python 版本是否为 3.10+
- 安装 `bilibili-cli`
- 自动定位 `bili.exe`，即使它不在 PATH 里
- 可选执行 `bili login`
- 可选跑一次公开视频 smoke test

如果要启用无字幕视频的本地 ASR，再加 `-InstallAsr`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Login -SmokeTest -InstallAsr
```

如果要启用无字幕、无语音视频的画面抽帧 fallback，再加 `-InstallVisual`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -InstallVisual
```

## 使用方式

OpenClaw 里触发 `bilibili-video-summary` 后，skill 会按下面流程收集材料。也可以直接运行工具脚本：

```powershell
python tools\bili_video_material.py "https://www.bilibili.com/video/BVxxxx/"
```

更快的官方字幕模式：

```powershell
python tools\bili_video_material.py "BVxxxx" --depth quick --asr never
```

强制 ASR：

```powershell
python tools\bili_video_material.py "BVxxxx" --asr always --asr-model small
```

输出目录：

```text
video_summaries\<BVID>\
```

关键文件：

- `summary_input.md`：给模型写总结的压缩材料
- `transcript.txt`：纯字幕/转写文本
- `material.json`：结构化元数据、官方 AI 总结、字幕、转写和日志
- `run_log.json`：命令耗时、fallback 决策和错误信息

## 工作流

1. 从 B 站链接或 BV 号提取 `BVID`。
2. 调用 `bili video <BVID> --subtitle --subtitle-timeline --subtitle-format timeline --ai --json`。
3. 如果官方字幕可用，直接生成 `summary_input.md`，跳过 ASR。
4. 如果官方字幕缺失，并且用户需要 deep 模式，再下载音频并调用 `faster-whisper`。
5. 模型读取 `summary_input.md` 后输出最终总结。

本机基线：两个测试视频都能在约 2.5 到 4 秒内拿到官方字幕和 AI 总结，ASR 被跳过。

## 依赖

必需：

- OpenClaw 2026.5.7 或更高版本
- Python 3.10+
- `bilibili-cli`
- Bilibili 登录态，部分视频和字幕需要登录

可选：

- `faster-whisper`
- FFmpeg 或本机可用的音频解码栈

## 仓库维护

本地自检：

```powershell
python tests\validate_repo.py
npm pack --dry-run
```

提交前建议至少跑：

```powershell
python -m py_compile tools\bili_video_material.py skills\bilibili-video-summary\scripts\bili_video_material.py
python tests\validate_repo.py
```

发布后验证 GitHub 安装：

```powershell
openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force
openclaw plugins inspect bilibili-video-summary --json
openclaw skills list --eligible --json
```

## License

MIT. See [LICENSE](LICENSE).
