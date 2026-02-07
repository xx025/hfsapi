"""
CLI（typer）单元测试。不依赖真实 HFS 服务器，通过 mock 验证命令与输出。
所有 URL、路径、账号均从 tests.config 读取，覆盖路径/URL、有无认证等多种条件。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hfsapi.cli import app, _format_size, _make_progress_callback

from tests.config import (
    HFS_BASE_URL,
    HFS_FULL_URL_FILE,
    HFS_FULL_URL_LIST,
    HFS_SHARE_NAME,
    HFS_SAMPLE_REMOTE_FILE,
    HFS_USERNAME,
    HFS_PASSWORD,
)

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
    """login 使用参数时调用 save_config 并输出 Saved.（base_url 来自 config）。"""
    result = runner.invoke(
        app,
        ["login", "--base-url", HFS_BASE_URL, "--username", "u", "--password", "p"],
    )
    assert result.exit_code == 0
    assert "Saved." in result.stdout

    from hfsapi.cli_config import load_config

    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == HFS_BASE_URL
    assert cfg["username"] == "u"
    assert cfg["password"] == "p"


def test_login_with_chinese_username_saves_and_loads_correctly() -> None:
    """中文用户名 你好 / 密码 abc123 能正确保存并读出（账号来自 config）。"""
    from tests.config import HFS_TEST_ACCOUNTS

    acc = HFS_TEST_ACCOUNTS[1]
    result = runner.invoke(
        app,
        [
            "login",
            "--base-url", HFS_BASE_URL,
            "--username", acc["username"],
            "--password", acc["password"],
        ],
    )
    assert result.exit_code == 0
    assert "Saved." in result.stdout

    from hfsapi.cli_config import load_config

    cfg = load_config()
    assert cfg is not None
    assert cfg["base_url"] == HFS_BASE_URL
    assert cfg["username"] == acc["username"]
    assert cfg["password"] == acc["password"]


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
    """已登录时 auth status 输出 base_url 和 auth: yes（config 的 base_url）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, "u", "p")
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert f"base_url: {HFS_BASE_URL}" in result.stdout
    assert "auth: yes" in result.stdout


def test_info_not_logged_in() -> None:
    """未登录时 info 输出 Not logged in。"""
    from hfsapi.cli_config import clear_config

    clear_config()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Not logged in" in result.stdout


def test_info_logged_in() -> None:
    """已登录时 info 输出 base_url 和 auth（config 的 base_url）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, "u", "p")
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert f"base_url: {HFS_BASE_URL}" in result.stdout
    assert "auth: yes" in result.stdout


# ------------------------- progress / format_size -------------------------


def test_format_size() -> None:
    """_format_size 将字节数格式化为 B/KiB/MiB/GiB。"""
    assert _format_size(0) == "0 B"
    assert _format_size(100) == "100 B"
    assert _format_size(1024) == "1.0 KiB"
    assert _format_size(1024 * 1024) == "1.0 MiB"
    assert _format_size(1024 * 1024 * 1024) == "1.0 GiB"
    assert _format_size(1536 * 1024) == "1.5 MiB"


def test_make_progress_callback_invokes() -> None:
    """_make_progress_callback 返回的 on_progress 可调用且不抛错；finish 换行。"""
    on_progress, finish = _make_progress_callback("foo.bin")
    assert callable(on_progress)
    assert callable(finish)
    on_progress(0, 100)
    on_progress(50, 100)
    on_progress(100, 100)
    finish()


# ------------------------- path or URL 解析 -------------------------


def test_parse_path_or_url() -> None:
    """路径与完整链接均能解析为 (path, base_url_override)；含 config 中的 URL。"""
    from hfsapi.cli import _parse_path_or_url

    # 纯路径
    path, base = _parse_path_or_url(HFS_SAMPLE_REMOTE_FILE)
    assert path == HFS_SAMPLE_REMOTE_FILE
    assert base is None

    path, base = _parse_path_or_url("/data/foo")
    assert path == "data/foo"
    assert base is None

    # 完整 URL（与 config 一致）
    path, base = _parse_path_or_url(HFS_FULL_URL_FILE)
    assert path == HFS_SAMPLE_REMOTE_FILE
    assert base == HFS_BASE_URL

    path, base = _parse_path_or_url("https://example.com:8080/share/sub/")
    assert path == "share/sub"
    assert base == "https://example.com:8080"

    path, base = _parse_path_or_url("  http://host/data  ")
    assert path == "data"
    assert base == "http://host"


# ------------------------- list（需 mock client） -------------------------


def test_list_without_credentials_exits_1() -> None:
    """无保存认证且未传 --base-url 时 list 退出 1 并报错。"""
    from hfsapi.cli_config import clear_config

    clear_config()
    result = runner.invoke(app, ["list", "/"])
    assert result.exit_code == 1
    assert "no saved credentials" in result.stdout or "no saved credentials" in result.stderr


def test_list_with_mock_client() -> None:
    """有认证时 list 调用 get_file_list 并输出列表（路径来自 config）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    mock_client = MagicMock()
    mock_client.get_file_list.return_value = {
        "list": [
            {"n": "file1.txt", "s": 100, "c": "2024-01-01", "m": "2024-01-02"},
            {"n": "dir/", "s": 0},
        ],
    }

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        result = runner.invoke(app, ["list", HFS_SHARE_NAME])
    assert result.exit_code == 0
    assert "file1.txt" in result.stdout
    assert "dir/" in result.stdout
    mock_client.get_file_list.assert_called_once()
    mock_client.close.assert_called_once()


def test_list_with_url_parses_link() -> None:
    """list 传入完整 URL 时解析出 path，并用 URL 的 base 创建 client（config URL）。"""
    from hfsapi.cli_config import save_config

    save_config("http://other:9999", "u", "p")
    mock_client = MagicMock()
    mock_client.get_file_list.return_value = {"list": []}

    with patch("hfsapi.cli._get_client", return_value=mock_client) as get_client:
        runner.invoke(app, ["list", HFS_FULL_URL_LIST])
    get_client.assert_called_once()
    assert get_client.call_args[0][0] == HFS_BASE_URL
    mock_client.get_file_list.assert_called_once()
    assert mock_client.get_file_list.call_args[1]["uri"] == f"/{HFS_SHARE_NAME}"


# ------------------------- upload / download / mkdir / delete（mock，多条件） -------------------------


def test_upload_with_path_folder_calls_client(tmp_path: Path) -> None:
    """upload 使用路径形式的 --folder 时传入解析后的 path（config 的 share）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    f = tmp_path / "f.txt"
    f.write_text("x")
    mock_client = MagicMock()
    mock_client.upload_file.return_value = MagicMock(status_code=200)

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        runner.invoke(app, ["upload", str(f), "--folder", HFS_SHARE_NAME])
    mock_client.upload_file.assert_called_once()
    assert mock_client.upload_file.call_args[0][0] == HFS_SHARE_NAME
    assert mock_client.upload_file.call_args[1].get("on_progress") is None


def test_upload_with_progress_passes_callback(tmp_path: Path) -> None:
    """upload 带 --progress/-p 时传入可调用的 on_progress，且上传成功。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    f = tmp_path / "f.txt"
    f.write_text("x")
    mock_client = MagicMock()
    mock_client.upload_file.return_value = MagicMock(status_code=200)

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        result = runner.invoke(app, ["upload", str(f), "--folder", HFS_SHARE_NAME, "--progress"])
    assert result.exit_code == 0
    mock_client.upload_file.assert_called_once()
    on_progress = mock_client.upload_file.call_args[1].get("on_progress")
    assert on_progress is not None and callable(on_progress)
    on_progress(500, 1000)
    on_progress(1000, 1000)


def test_upload_with_url_folder_parses_and_calls(tmp_path: Path) -> None:
    """upload --folder 为完整 URL 时解析出 base 与 path 并调用 client。"""
    from hfsapi.cli_config import save_config

    save_config("http://other:9999", "u", "p")
    f = tmp_path / "f.txt"
    f.write_text("x")
    mock_client = MagicMock()
    mock_client.upload_file.return_value = MagicMock(status_code=200)

    with patch("hfsapi.cli._get_client", return_value=mock_client) as get_client:
        runner.invoke(app, ["upload", str(f), "--folder", HFS_FULL_URL_LIST])
    get_client.assert_called_once()
    assert get_client.call_args[0][0] == HFS_BASE_URL
    assert mock_client.upload_file.call_args[0][0] == HFS_SHARE_NAME


def test_upload_show_url_prints_link_file(tmp_path: Path) -> None:
    """upload 带 --show-url/-u 时上传成功后输出真实文件链接（走 get_uploaded_file_url，可含重命名后 URL）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    f = tmp_path / "f.txt"
    f.write_text("x")
    mock_response = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.upload_file.return_value = mock_response
    mock_client.get_uploaded_file_url.return_value = "http://127.0.0.1:8280/data/f.txt"

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        result = runner.invoke(app, ["upload", str(f), "--folder", HFS_SHARE_NAME, "--show-url"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:8280/data/f.txt" in result.stdout
    mock_client.get_uploaded_file_url.assert_called_once()
    assert mock_client.get_uploaded_file_url.call_args[0][:2] == (HFS_SHARE_NAME, "f.txt")
    assert mock_client.get_uploaded_file_url.call_args[0][2] is mock_response


def test_upload_folder_with_progress_passes_callback(tmp_path: Path) -> None:
    """upload 目录且带 --progress/-p 时传入 on_file_progress 与 on_progress，上传成功后显示双进度条。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    d = tmp_path / "mydir"
    d.mkdir()
    (d / "a.txt").write_text("a")
    (d / "b.txt").write_text("b")
    mock_client = MagicMock()
    mock_client.upload_folder.return_value = (2, [])

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        runner.invoke(app, ["upload", str(d), "--folder", HFS_SHARE_NAME, "--progress"])
    mock_client.upload_folder.assert_called_once()
    on_file_progress = mock_client.upload_folder.call_args[1].get("on_file_progress")
    on_progress = mock_client.upload_folder.call_args[1].get("on_progress")
    assert on_file_progress is not None and callable(on_file_progress)
    assert on_progress is not None and callable(on_progress)
    on_file_progress(1, 2, "a.txt", 1)
    on_progress(1, 1)
    on_file_progress(2, 2, "b.txt", 1)
    on_progress(1, 1)


def test_upload_show_url_prints_link_folder(tmp_path: Path) -> None:
    """upload 目录且带 --show-url 时上传成功后输出文件夹链接。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    d = tmp_path / "mydir"
    d.mkdir()
    (d / "a.txt").write_text("a")
    mock_client = MagicMock()
    mock_client.upload_folder.return_value = (1, [])
    mock_client.get_resource_url.return_value = "http://127.0.0.1:8280/data"

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        result = runner.invoke(app, ["upload", str(d), "--folder", HFS_SHARE_NAME, "-u"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:8280/data" in result.stdout
    mock_client.get_resource_url.assert_called_once()
    # 上传目录时文件落在 folder_path 下，返回的链接是 folder_path 本身，不是 folder_path/mydir
    assert mock_client.get_resource_url.call_args[0][0] == HFS_SHARE_NAME


def test_download_with_path_calls_client() -> None:
    """download 使用路径时调用 download_file（path 来自 config）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    mock_client = MagicMock()
    mock_client.download_file.return_value = b"content"

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        runner.invoke(app, ["download", HFS_SAMPLE_REMOTE_FILE])
    mock_client.download_file.assert_called_once()
    args = mock_client.download_file.call_args[0]
    assert args[0] == HFS_SAMPLE_REMOTE_FILE


def test_download_with_url_parses_and_calls() -> None:
    """download 传入完整 URL 时解析 base 与 path 并调用 client。"""
    from hfsapi.cli_config import save_config

    save_config("http://other:9999", "u", "p")
    mock_client = MagicMock()
    mock_client.download_file.return_value = b"content"

    with patch("hfsapi.cli._get_client", return_value=mock_client) as get_client:
        runner.invoke(app, ["download", HFS_FULL_URL_FILE])
    get_client.assert_called_once()
    assert get_client.call_args[0][0] == HFS_BASE_URL
    assert mock_client.download_file.call_args[0][0] == HFS_SAMPLE_REMOTE_FILE


def test_mkdir_with_path_calls_create_folder() -> None:
    """mkdir 使用路径时解析 parent/new_name 并调用 create_folder（config 路径）。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    mock_client = MagicMock()
    mock_client.create_folder.return_value = MagicMock(status_code=201)

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        runner.invoke(app, ["mkdir", f"{HFS_SHARE_NAME}/newdir"])
    mock_client.create_folder.assert_called_once()
    assert mock_client.create_folder.call_args[0] == (HFS_SHARE_NAME, "newdir")


def test_mkdir_with_url_parses_base_and_path() -> None:
    """mkdir 传入完整 URL 时解析 base 与 path 并调用 create_folder。"""
    from hfsapi.cli_config import save_config

    save_config("http://other:9999", "u", "p")
    mock_client = MagicMock()
    mock_client.create_folder.return_value = MagicMock(status_code=201)

    with patch("hfsapi.cli._get_client", return_value=mock_client) as get_client:
        runner.invoke(app, ["mkdir", f"{HFS_BASE_URL}/data/mydir"])
    get_client.assert_called_once()
    assert get_client.call_args[0][0] == HFS_BASE_URL
    assert mock_client.create_folder.call_args[0] == ("data", "mydir")


def test_delete_with_path_calls_delete_file() -> None:
    """delete 使用路径时解析 folder/filename 并调用 delete_file。"""
    from hfsapi.cli_config import save_config

    save_config(HFS_BASE_URL, HFS_USERNAME, HFS_PASSWORD)
    mock_client = MagicMock()
    mock_client.delete_file.return_value = MagicMock(status_code=204)

    with patch("hfsapi.cli._get_client", return_value=mock_client):
        runner.invoke(app, ["delete", HFS_SAMPLE_REMOTE_FILE])
    mock_client.delete_file.assert_called_once()
    assert mock_client.delete_file.call_args[0] == ("data", "sample.txt")


def test_delete_with_url_parses_base_and_path() -> None:
    """delete 传入完整 URL 时解析 base 与 path 并调用 delete_file。"""
    from hfsapi.cli_config import save_config

    save_config("http://other:9999", "u", "p")
    mock_client = MagicMock()
    mock_client.delete_file.return_value = MagicMock(status_code=204)

    with patch("hfsapi.cli._get_client", return_value=mock_client) as get_client:
        runner.invoke(app, ["delete", HFS_FULL_URL_FILE])
    get_client.assert_called_once()
    assert get_client.call_args[0][0] == HFS_BASE_URL
    assert mock_client.delete_file.call_args[0] == ("data", "sample.txt")


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
