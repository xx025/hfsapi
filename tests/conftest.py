"""
pytest 配置与共享 fixture。

测试目标与账号见 tests.config。
"""

from __future__ import annotations

import pytest

from hfsapi import HFSClient

from tests.config import (
    HFS_BASE_URL,
    HFS_PASSWORD,
    HFS_SHARE_URI,
    HFS_USERNAME,
)


@pytest.fixture(scope="module")
def client() -> HFSClient:
    """使用测试账号的 HFS 客户端，模块内复用。"""
    return HFSClient(
        base_url=HFS_BASE_URL,
        username=HFS_USERNAME,
        password=HFS_PASSWORD,
        timeout=10.0,
    )


@pytest.fixture(scope="module")
def share_uri() -> str:
    """分享目录 URI（如 /data）。"""
    return HFS_SHARE_URI


@pytest.fixture(scope="module")
def share_name() -> str:
    """分享目录名，用于 upload_file/delete_file 等（如 data）。"""
    return HFS_SHARE_URI.strip("/").split("/")[0] or "data"


@pytest.fixture(scope="module")
def share_list(client: HFSClient, share_uri: str):
    """
    请求分享目录列表；若服务器不可达则跳过整个模块。
    对应权限：Who can access list = Any account login。
    """
    try:
        data = client.get_file_list(uri=share_uri, request_c_and_m=True)
        return data
    except Exception as e:
        pytest.skip(
            f"HFS 测试服务器不可用 ({HFS_BASE_URL}): {e}. "
            f"请确保服务器运行且账号 {HFS_USERNAME} 有效。"
        )
