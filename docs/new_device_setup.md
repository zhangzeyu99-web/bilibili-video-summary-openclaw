# 新设备配置说明

这份文档用于在一台新 Windows 设备上配置本仓库和 OpenClaw skill。

## 前置条件

- 已安装 Git
- 已安装 Python 3.10+
- 已安装 OpenClaw，并且 `openclaw --version` 可执行
- PowerShell 可用

## 推荐安装

```powershell
git clone https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git
cd bilibili-video-summary-openclaw
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Login -SmokeTest
openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force
openclaw gateway restart
openclaw skills list --eligible --json
```

确认输出里有：

```text
bilibili-video-summary
```

## 只装依赖，不登录

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

之后手动登录：

```powershell
bili login
```

如果 `bili` 不在 PATH 里，工具脚本也会自动扫描常见 Python Scripts 目录。

## 启用 ASR fallback

只有官方字幕缺失时才需要 ASR。需要时运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -InstallAsr
```

然后使用：

```powershell
python tools\bili_video_material.py "BVxxxx" --depth deep --asr auto
```

## 常见问题

`Cannot find bili executable`：

- 先运行 `python -m pip install --user -r requirements.txt`
- 再运行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1`
- 或者显式传入 `--bili C:\path\to\bili.exe`

`bili` 未登录或字幕为空：

- 运行 `bili login`
- 重新执行视频材料采集

OpenClaw 已安装但 skill 没出现：

```powershell
openclaw plugins inspect bilibili-video-summary --json
openclaw gateway restart
openclaw skills list --eligible --json
```
