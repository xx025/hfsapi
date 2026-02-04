"""
CLI 认证配置（cli_config）单元测试。URL/账号均从 tests.config 读取。
"""

from __future__ import annotations

import pytest

from hfsapi.cli_config import clear_config, load_config, save_config

from tests.config import HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD


@pytest.fixture(autouse=True)
def _patch_config_path(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """将配置路径指向临时目录，避免污染用户 ~/.config/hfsapi。"""
    config_dir = tmp_path / "hfsapi"
    config_dir.mkdir(parents=True, exist_ok=True)

    def _config_dir():
        return config_dir

    monkeypatch.setattr("hfsapi.cli_config._config_dir", _config_dir)


def test_load_config_missing_returns_none() -> None:
    """无配置文件时 load_config 返回 None。"""
    assert load_config() is None


def test_load_config_invalid_json_returns_none(tmp_path: pytest.TempPathFactory) -> None:
    """无效 JSON 时 load_config 返回 None。"""
    config_file = tmp_path / "hfsapi" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("not json", encoding="utf-8")
    assert load_config() is None


def test_load_config_missing_base_url_returns_none(tmp_path: pytest.TempPathFactory) -> None:
    """缺少 base_url 时 load_config 返回 None。"""
    config_file = tmp_path / "hfsapi" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('{"username": "u"}', encoding="utf-8")
    assert load_config() is None


def test_save_config_creates_dir_and_file() -> None:
    """save_config 创建目录并写入 config.json（使用 config 的 base_url/账号）。"""
    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == HFS_BASE_URL
    assert cfg["username"] == HFS_USERNAME
    assert cfg["password"] == HFS_PASSWORD


def test_save_config_strips_trailing_slash() -> None:
    """save_config 会去掉 base_url 末尾斜杠。"""
    save_config(f"{HFS_BASE_URL}/", "u", "p")
    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == HFS_BASE_URL


def test_save_config_optional_username_password() -> None:
    """save_config 可不传 username/password。"""
    save_config(HFS_BASE_URL)
    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == HFS_BASE_URL
    assert "username" not in cfg or cfg.get("username") is None
    assert "password" not in cfg or cfg.get("password") is None


def test_clear_config_removes_file() -> None:
    """clear_config 删除配置文件并返回 True。"""
    save_config(HFS_BASE_URL, "u", "p")
    assert load_config() is not None
    assert clear_config() is True
    assert load_config() is None


def test_clear_config_when_missing_returns_false() -> None:
    """无配置文件时 clear_config 返回 False。"""
    assert clear_config() is False
