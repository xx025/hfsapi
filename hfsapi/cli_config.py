"""
CLI 认证配置：本地保存/读取 base_url、username、password。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    """配置目录：~/.config/hfsapi（所有平台统一）。"""
    return Path.home() / ".config" / "hfsapi"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict[str, Any] | None:
    """读取本地配置；不存在或无效则返回 None。"""
    p = _config_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "base_url" not in data:
            return None
        return data
    except Exception:
        return None


def save_config(base_url: str, username: str | None = None, password: str | None = None) -> None:
    """保存认证信息到本地。"""
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"base_url": base_url.rstrip("/")}
    if username is not None:
        data["username"] = username
    if password is not None:
        data["password"] = password
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_config() -> bool:
    """清除本地配置；存在则删除并返回 True。"""
    p = _config_path()
    if p.exists():
        p.unlink()
        return True
    return False
