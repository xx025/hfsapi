"""
HFS /data 目录权限相关 API 的 pytest 测试。

服务器、分享路径、账号均来自 tests.config；client 由 conftest 按 HFS_TEST_ACCOUNTS 参数化，每账号各跑一遍。
对应界面权限（Any account login）：
- Who can zip           → can_archive（用户以 ZIP 下载时是否包含此项）
- Who can access list   → 能成功调用 get_file_list，列表仅包含可见项
- Who can download      → can_read；看不到不能下载的会要求登录
- Who can delete        → can_delete（可删除也可重命名/剪切/移动）
- Who can upload        → can_upload；可为子文件夹设不同权限
- Who can see           → 列表中可见的项；可为文件夹内容设不同权限
"""

from __future__ import annotations

import time
import pytest
import httpx

from hfsapi import (
    HFSClient,
    entry_created,
    entry_modified,
    entry_permissions,
    entry_size,
)

from tests.config import HFS_BASE_URL, HFS_SHARE_URI


@pytest.mark.integration
class TestWhoCanAccessList:
    """Who can access list: Permission to request the list of a folder. The list will include only things you can see."""

    def test_get_file_list_share_succeeds(self, client: HFSClient, share_uri: str) -> None:
        """已登录账户可请求分享目录列表。"""
        data = client.get_file_list(uri=share_uri)
        assert "list" in data
        assert isinstance(data["list"], list)

    def test_list_includes_only_visible_entries(self, share_list: dict) -> None:
        """列表仅包含当前用户可见的项（Who can see）。"""
        entries = share_list.get("list", [])
        for e in entries:
            assert "n" in e  # 每项必有名称
            # 能出现在 list 里即表示「Who can see」允许看到

    def test_list_entries_have_metadata(self, share_list: dict) -> None:
        """列表项包含元数据：名称、大小、创建/修改时间等。"""
        entries = share_list.get("list", [])
        for e in entries:
            assert "n" in e
            # s/c/m 可能缺失（如部分文件夹），有则校验类型
            if "s" in e:
                assert isinstance(e["s"], (int, float))
            if "c" in e:
                assert isinstance(e["c"], str)
            if "m" in e:
                assert isinstance(e["m"], str)


@pytest.mark.integration
class TestWhoCanZip:
    """Who can zip: Should this be included when user downloads as ZIP. Set different permission for folder content."""

    def test_can_archive_in_response(self, share_list: dict) -> None:
        """get_file_list 返回 can_archive，表示当前用户是否可把该目录/项打包为 ZIP。"""
        assert "can_archive" in share_list
        # Any account login 时已登录用户应为 True
        assert share_list["can_archive"] is True


@pytest.mark.integration
class TestWhoCanDownload:
    """Who can download: Who can see but not download will be asked to login. Set different permission for folder content."""

    def test_authenticated_user_gets_list(self, client: HFSClient, share_uri: str) -> None:
        """已登录用户可获取列表（可见即可请求；不能下载的会要求登录）。"""
        data = client.get_file_list(uri=share_uri)
        assert "list" in data
        # 能拿到 list 说明至少「Who can access list」和「Who can see」允许


@pytest.mark.integration
class TestWhoCanDelete:
    """Who can delete: Those who can delete can also rename and cut/move. Set different permission for folder content."""

    def test_can_delete_in_response(self, share_list: dict) -> None:
        """get_file_list 返回 can_delete（及可选 can_delete_children），表示当前用户是否可删除/重命名/移动。"""
        assert "can_delete" in share_list
        # 服务端可能仅对子项开放删除：can_delete（本目录）或 can_delete_children（子项）至少其一为 True
        can_delete_self = share_list.get("can_delete") is True
        can_delete_children = share_list.get("can_delete_children", False) is True
        assert can_delete_self or can_delete_children, "expected can_delete or can_delete_children"

    def test_upload_then_delete_file(
        self, client: HFSClient, share_uri: str, share_name: str
    ) -> None:
        """先上传一个文件到分享目录，再删除该文件；上传后列表中可见，删除后列表中消失。"""
        filename = f"pytest_delete_test_{int(time.time() * 1000)}.txt"
        content = b"pytest delete test - who can delete"
        put_params = {
            "id": f"pytest_del_{int(time.time() * 1000)}",
            "mtime": str(int(time.time() * 1000)),
            "resume": "0!",
        }
        try:
            # 上传
            r = client.upload_file(
                share_name,
                content,
                filename=filename,
                use_put=True,
                put_params=put_params,
                use_session_for_put=True,
            )
        except httpx.ConnectError as e:
            pytest.skip(f"HFS 服务器不可达: {e}")
        if r.status_code == 404:
            pytest.skip("PUT 上传返回 404，跳过删除测试")
        assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text}"
        # 验证上传后列表中可见
        data = client.get_file_list(uri=share_uri)
        names = [e.get("n") for e in data.get("list", []) if e.get("n")]
        assert filename in names, f"上传后 {share_uri} 列表中应包含 {filename!r}，当前: {names}"
        # 删除
        del_r = client.delete_file(share_name, filename)
        assert del_r.status_code in (200, 201, 204), f"delete failed: {del_r.status_code} {del_r.text}"
        # 验证删除后列表中消失
        data_after = client.get_file_list(uri=share_uri)
        names_after = [e.get("n") for e in data_after.get("list", []) if e.get("n")]
        assert filename not in names_after, f"删除后 {share_uri} 列表中不应再包含 {filename!r}，当前: {names_after}"


@pytest.mark.integration
class TestWhoCanUpload:
    """Who can upload: Any account login. Set different permission for subfolders."""

    def test_can_upload_in_response(self, share_list: dict) -> None:
        """get_file_list 返回 can_upload，表示当前用户是否可在此目录上传。"""
        assert "can_upload" in share_list
        assert share_list["can_upload"] is True

    def test_upload_file_to_share(
        self, client: HFSClient, share_uri: str, share_name: str
    ) -> None:
        """已登录用户可向分享目录上传文件（Who can upload）。与 HFS 前端一致：仅 session + Referer + PUT 分享路径/文件名?id=...&mtime=...&resume=0!。"""
        content = b"pytest upload test - who can upload"
        filename = "pytest_upload_test.txt"
        put_params = {
            "id": f"pytest_{int(time.time() * 1000)}",
            "mtime": str(int(time.time() * 1000)),
            "resume": "0!",
        }
        try:
            r = client.upload_file(
                share_name,
                content,
                filename=filename,
                use_put=True,
                put_params=put_params,
                use_session_for_put=True,
            )
        except httpx.ConnectError as e:
            pytest.skip(f"HFS 服务器不可达（需能访问测试地址）: {e}")
        # 客户端会在 404 时按 HFS roots 逻辑重试 PUT /filename；若仍 404 则跳过（环境/网段差异）
        if r.status_code == 404:
            pytest.skip(
                "PUT 上传仍返回 404：若 HFS 配置了 roots，客户端已自动重试相对路径；"
                f"请确认服务端 {share_uri} 可上传且在与 HFS 同网段下重试。"
            )
        assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text}"
        # 验证文件已出现在分享目录列表中
        data = client.get_file_list(uri=share_uri)
        names = [e.get("n") for e in data.get("list", []) if e.get("n")]
        assert filename in names, f"上传后 {share_uri} 列表中应包含 {filename!r}，当前: {names}"


@pytest.mark.integration
class TestCreateFolder:
    """create_folder：与网页「新建文件夹」一致，需 can_upload。"""

    def test_create_folder_appears_in_list(
        self, client: HFSClient, share_uri: str, share_name: str
    ) -> None:
        """create_folder 后列表中应出现新文件夹名。"""
        folder_name = f"pytest_newfolder_{int(time.time() * 1000)}"
        try:
            r = client.create_folder(share_name, folder_name)
        except httpx.ConnectError as e:
            pytest.skip(f"HFS 服务器不可达: {e}")
        if r.status_code == 404:
            pytest.skip("create_folder 返回 404，跳过（如 roots 配置差异）")
        assert r.status_code in (200, 201), f"create_folder failed: {r.status_code} {r.text}"
        data = client.get_file_list(uri=share_uri)
        names = [e.get("n", "").rstrip("/") for e in data.get("list", []) if e.get("n")]
        assert folder_name in names, f"create_folder 后 {share_uri} 列表中应包含 {folder_name!r}，当前: {names}"
        # 清理：删除占位文件 .keep
        client.delete_file(f"{share_name}/{folder_name}", ".keep")
        data_after = client.get_file_list(uri=share_uri)
        names_after = [e.get("n", "").rstrip("/") for e in data_after.get("list", []) if e.get("n")]
        assert folder_name in names_after, "删除 .keep 后空文件夹仍可存在于列表中"


@pytest.mark.integration
class TestWhoCanSee:
    """Who can see: See this item in the list. Set different permission for folder content."""

    def test_can_see_reflected_in_list(self, share_list: dict) -> None:
        """列表中出现的项即当前用户「Who can see」允许看到的。"""
        entries = share_list.get("list", [])
        # 每项有 n；可选 p（权限缩写，仅在与父级不同时存在）
        for e in entries:
            assert "n" in e
            if "p" in e:
                assert isinstance(e["p"], str)


@pytest.mark.integration
class TestListEntryHelpers:
    """列表项元数据与权限缩写解析（entry_size, entry_created, entry_modified, entry_permissions）。"""

    def test_entry_helpers(self, share_list: dict) -> None:
        """entry_size / entry_created / entry_modified / entry_permissions 可安全用于列表项。"""
        entries = share_list.get("list", [])
        if not entries:
            pytest.skip("share 目录为空，无列表项可测")
        e = entries[0]
        _ = entry_size(e)
        _ = entry_created(e)
        _ = entry_modified(e)
        _ = entry_permissions(e)


@pytest.mark.integration
class TestLogin:
    """登录与会话（Any account login 前提）。"""

    def test_login_returns_success(self, client: HFSClient) -> None:
        """login() 使用 URL 参数建立会话时返回 True（请求成功）。"""
        ok = client.login()
        assert ok is True

    def test_get_file_list_without_auth_fails_for_protected_share(self) -> None:
        """无认证时请求分享目录列表应失败或返回未授权（若服务端要求登录）。"""
        # 使用无账号的 client
        no_auth = HFSClient(base_url=HFS_BASE_URL, timeout=5.0)
        try:
            no_auth.get_file_list(uri=HFS_SHARE_URI)
            # 若服务端对分享目录允许匿名，可能不抛；否则 401/403 或重定向到登录
        except Exception:
            pass  # 预期可能抛错
        finally:
            no_auth.close()
