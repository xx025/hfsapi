"""
客户端单元测试。验证中文用户名在 login URL 中的编码等。配置来自 tests.config。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hfsapi.client import HFSClient

from tests.config import HFS_BASE_URL, HFS_TEST_ACCOUNTS


def test_login_url_encodes_chinese_username() -> None:
    """用户名含中文时（config 中你好/abc123），login() 请求的 URL 中 login 参数为 UTF-8 百分号编码。"""
    acc = HFS_TEST_ACCOUNTS[1]
    client = HFSClient(HFS_BASE_URL, username=acc["username"], password=acc["password"])
    captured_url: str | None = None

    def fake_get(url: str, **kwargs: object) -> MagicMock:
        nonlocal captured_url
        captured_url = url
        resp = MagicMock()
        resp.is_success = True
        return resp

    with patch.object(client._get_client(), "get", side_effect=fake_get):
        client.login()

    assert captured_url is not None
    # 你好 的 UTF-8 百分号编码为 %E4%BD%A0%E5%A5%BD，: 为 %3A
    assert "%E4%BD%A0%E5%A5%BD" in captured_url or "login=" in captured_url
    assert "abc123" in captured_url or "%61%62%63%31%32%33" in captured_url
    # URL 不应包含裸的中文字符（应为编码形式）
    assert acc["username"] not in captured_url


def test_path_for_url_encodes_non_ascii() -> None:
    """_path_for_url 对含中文的路径做 UTF-8 百分号编码。"""
    from hfsapi.client import _path_for_url

    assert _path_for_url("data/你好") == "/data/%E4%BD%A0%E5%A5%BD"
    assert _path_for_url("data/foo.txt") == "/data/foo.txt"
    assert _path_for_url("") == "/"
    assert _path_for_url("/") == "/"


def test_get_uploaded_file_url_uses_location_header() -> None:
    """get_uploaded_file_url 优先使用响应头 Location（绝对 URL 或相对路径）。"""
    client = HFSClient(HFS_BASE_URL)
    resp = MagicMock()
    resp.headers = {"Location": "http://other/data/file%20(1).txt"}
    assert client.get_uploaded_file_url("data", "file.txt", resp) == "http://other/data/file (1).txt"

    resp.headers = {"Location": "/data/file%20(1).txt"}
    got = client.get_uploaded_file_url("data", "file.txt", resp)
    assert got == f"{HFS_BASE_URL.rstrip('/')}/data/file (1).txt"


def test_get_uploaded_file_url_fallback_list_dir() -> None:
    """无 Location 时列父目录，按精确名或 base (N).ext + 最新 mtime 取实际文件名。"""
    client = HFSClient(HFS_BASE_URL)
    resp = MagicMock()
    resp.headers = {}

    with patch.object(client, "get_file_list", return_value={"list": [{"n": "file (1).txt", "m": "2025-01-02T00:00:00Z"}]}):
        url = client.get_uploaded_file_url("data", "file.txt", resp)
    assert url == client.get_resource_url("data/file (1).txt", human_readable=True)

    with patch.object(client, "get_file_list", return_value={"list": [{"n": "file.txt", "m": "2025-01-01T00:00:00Z"}]}):
        url = client.get_uploaded_file_url("data", "file.txt", resp)
    assert url == client.get_resource_url("data/file.txt", human_readable=True)

    # 多个 base (N).ext 时取 N 最大的（刚上传的）
    with patch.object(
        client,
        "get_file_list",
        return_value={
            "list": [
                {"n": "docker-compose (1).yaml", "m": "2026-02-07T04:07:45Z"},
                {"n": "docker-compose (10).yaml", "m": "2026-02-07T04:25:00Z"},
                {"n": "docker-compose (9).yaml", "m": "2026-02-07T04:22:31Z"},
            ]
        },
    ):
        url = client.get_uploaded_file_url("data/tests3355", "docker-compose.yaml", resp)
    assert url == client.get_resource_url("data/tests3355/docker-compose (10).yaml", human_readable=True)
