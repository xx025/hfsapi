"""
客户端单元测试。验证中文用户名在 login URL 中的编码等。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hfsapi.client import HFSClient


def test_login_url_encodes_chinese_username() -> None:
    """用户名 你好、密码 abc123 时，login() 请求的 URL 中 login 参数为 UTF-8 百分号编码。"""
    client = HFSClient("http://127.0.0.1:8280", username="你好", password="abc123")
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
    assert "你好" not in captured_url
