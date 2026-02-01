"""
CLI（typer）单元测试。不依赖真实 HFS 服务器，通过 mock 验证命令与输出。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hfsapi.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_config_path(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """将配置路径指向临时目录。"""
    config_dir = tmp_path / "hfsapi"
    config_dir.mkdir(parents=True, exist_ok=True)

    def _config_dir():
        return config_dir

    monkeypatch.setattr("hfsapi.cli_config._config_dir", _config_dir)


# ------------------------- login / logout / auth / info -------------------------


def test_login_saves_config() -> None:
    """login 使用参数时调用 save_config 并输出 Saved.。"""
    result = runner.invoke(
        app,
        ["login", "--base-url", "http://127.0.0.1:8280", "--username", "u", "--password", "p"],
    )
    assert result.exit_code == 0
    assert "Saved." in result.stdout

    from hfsapi.cli_config import load_config

    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == "http://127.0.0.1:8280"
    assert cfg["username"] == "u"
    assert cfg["password"] == "p"


def test_logout_clears_config() -> None:
    """logout 清除配置并输出 Cleared.。"""
    from hfsapi.cli_config import load_config, save_config

    save_config("http://x", "u", "p")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "Cleared." in result.stdout
    assert load_config() is None

    result2 = runner.invoke(app, ["logout"])
    assert result2.exit_code == 0
    assert "No saved credentials." in result2.stdout


def test_auth_status_not_logged_in() -> None:
    """未登录时 auth status 输出 Not logged in.。"""
    from hfsapi.cli_config import clear_config

    clear_config()
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "Not logged in." in result.stdout


def test_auth_status_logged_in() -> None:
    """已登录时 auth status 输出 base_url 和 auth: yes。"""
    from hfsapi.cli_config import save_config

    save_config("http://127.0.0.1:8280", "u", "p")
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "base_url: http://127.0.0.1:8280" in result.stdout
    assert "auth: yes" in result.stdout


def test_info_not_logged_in() -> None:
    """未登录时 info 输出 Not logged in。"""
    from hfsapi.cli_config import clear_config

    clear_config()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Not logged in" in result.stdout


def test_info_logged_in() -> None:
    """已登录时 info 输出 base_url 和 auth。"""
    from hfsapi.cli_config import save_config

    save_config("http://127.0.0.1:8280", "u", "p")
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "base_url: http://127.0.0.1:8280" in result.stdout
    assert "auth: yes" in result.stdout


# ------------------------- list（需 mock client） -------------------------


def test_list_without_credentials_exits_1() -> None:
    """无保存认证且未传 --base-url 时 list 退出 1 并报错。"""
    from hfsapi.cli_config import clear_config

    clear_config()
    result = runner.invoke(app, ["list", "/"])
    assert result.exit_code == 1
    assert "no saved credentials" in result.stdout or "no saved credentials" in result.stderr


def test_list_with_mock_client() -> None:
    """有认证时 list 调用 get_file_list 并输出列表。"""
    from hfsapi.cli_config import save_config

    save_config("http://127.0.0.1:8280", "u", "p")
    mock_client = MagicMock()
    mock_client.get_file_list.return_value = {
        "list": [
            {"n": "file1.txt", "s": 100, "c": "2024-01-01", "m": "2024-01-02"},
            {"n": "dir/", "s": 0},
        ],
    }

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        result = runner.invoke(app, ["list", "/data"])
    assert result.exit_code == 0
    assert "file1.txt" in result.stdout
    assert "dir/" in result.stdout
    mock_client.get_file_list.assert_called_once()
    mock_client.close.assert_called_once()


# ------------------------- help -------------------------


def test_help_lists_commands() -> None:
    """--help 列出所有子命令。"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "login" in result.stdout
    assert "logout" in result.stdout
    assert "list" in result.stdout
    assert "upload" in result.stdout
    assert "download" in result.stdout
    assert "mkdir" in result.stdout
    assert "delete" in result.stdout
    assert "config" in result.stdout
    assert "vfs" in result.stdout
    assert "info" in result.stdout
    assert "auth" in result.stdout


def test_login_help() -> None:
    """hfs login --help 显示选项。"""
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "--base-url" in result.stdout
    assert "--username" in result.stdout
    assert "--password" in result.stdout
