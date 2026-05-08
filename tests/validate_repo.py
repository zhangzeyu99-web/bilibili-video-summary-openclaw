#!/usr/bin/env python
"""Repository self-checks for the OpenClaw Bilibili summary skill."""

from __future__ import annotations

import hashlib
import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "bilibili-video-summary"
TOOL_SCRIPT = ROOT / "tools" / "bili_video_material.py"
SKILL_SCRIPT = SKILL_DIR / "scripts" / "bili_video_material.py"


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"Cannot parse {path}: {exc}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def validate_metadata() -> None:
    package = load_json(ROOT / "package.json")
    manifest = load_json(ROOT / "openclaw.plugin.json")

    require(package.get("license") == "MIT", "package.json license must be MIT")
    require(package.get("openclaw", {}).get("extensions") == ["./index.js"], "package.json must declare openclaw.extensions")
    require((ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"), "LICENSE must contain MIT text")

    require(manifest.get("id") == "bilibili-video-summary", "plugin id mismatch")
    require(manifest.get("skills") == ["./skills/bilibili-video-summary"], "plugin skills path mismatch")
    require(manifest.get("configSchema", {}).get("additionalProperties") is False, "plugin configSchema must be strict")

    for rel in package.get("files", []):
        require((ROOT / rel).exists(), f"package files entry does not exist: {rel}")


def validate_skill() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    require(skill.startswith("---\n"), "SKILL.md must start with YAML frontmatter")
    require("name: bilibili-video-summary" in skill, "SKILL.md name is missing")
    require("description:" in skill, "SKILL.md description is missing")
    require((SKILL_DIR / "agents" / "openai.yaml").exists(), "agents/openai.yaml is missing")


def validate_scripts() -> None:
    require(TOOL_SCRIPT.exists(), "tools script is missing")
    require(SKILL_SCRIPT.exists(), "skill script is missing")
    require(sha256(TOOL_SCRIPT) == sha256(SKILL_SCRIPT), "tool script and skill script must stay identical")

    for script in (TOOL_SCRIPT, SKILL_SCRIPT):
        tmp_pyc = Path(tempfile.gettempdir()) / f"{script.stem}-{sha256(script)[:12]}.pyc"
        try:
            py_compile.compile(str(script), cfile=str(tmp_pyc), doraise=True)
        finally:
            tmp_pyc.unlink(missing_ok=True)
    subprocess.run([sys.executable, str(TOOL_SCRIPT), "--help"], check=True, stdout=subprocess.DEVNULL)


def validate_docs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    require("openclaw plugins install git:https://github.com/zhangzeyu99-web/bilibili-video-summary-openclaw.git --force" in readme, "README install command missing")
    require("MIT" in readme, "README license section missing")
    require("�" not in readme, "README contains replacement characters")


def main() -> int:
    validate_metadata()
    validate_skill()
    validate_scripts()
    validate_docs()
    print("[OK] repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
