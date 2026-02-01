"""
pytest 配置与共享 fixture。

测试目标与账号见 tests.config。
集成测试会对 HFS_TEST_ACCOUNTS 中每个账号各执行一次（client 参数化）。
"""

from __future__ import annotations

import pytest

from hfsapi import HFSClient

from tests.config import (
    HFS_BASE_URL,
    HFS_SHARE_URI,
    HFS_TEST_ACCOUNTS,
)


@pytest.fixture(scope="module", params=[pytest.param(acc, id=acc["username"]) for acc in HFS_TEST_ACCOUNTS])
def client(request: pytest.FixtureRequest) -> HFSClient:
    """使用测试账号的 HFS 客户端；每个 HFS_TEST_ACCOUNTS 账号各跑一遍。"""
    acc = request.param
    return HFSClient(
        base_url=HFS_BASE_URL,
        username=acc["username"],
        password=acc["password"],
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
        usernames = [acc["username"] for acc in HFS_TEST_ACCOUNTS]
        pytest.skip(
            f"HFS 测试服务器不可用 ({HFS_BASE_URL}): {e}. "
            f"请确保服务器运行且测试账号 {usernames} 有效。"
        )
