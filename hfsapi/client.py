"""
HFS (HTTP File Server) Python API 客户端。

基于 https://github.com/rejetto/hfs 的 OpenAPI 与前端行为实现，
支持登录、文件列表、上传、配置及权限相关操作。
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator
from urllib.parse import quote, unquote, urlencode, urlparse

import httpx


def _url_path_readable(url: str) -> str:
    """将 URL 的 path 部分解码为人类可读（如 %20 -> 空格，%281%29 -> (1)）。"""
    p = urlparse(url)
    path = unquote(p.path)
    return f"{p.scheme}://{p.netloc}{path}" + (f"?{p.query}" if p.query else "") + (f"#{p.fragment}" if p.fragment else "")


def _path_for_url(path: str) -> str:
    """将路径按段做 UTF-8 百分号编码，供 URL 使用（避免中文等非 ASCII 导致 ascii codec 错误）。"""
    segments = (path.strip("/").split("/") if path.strip("/") else [])
    return "/" + "/".join(quote(seg, safe="") for seg in segments) if segments else "/"

from hfsapi.models import DirEntry, FileListResponse, entry_modified

# POST 请求需携带的防 CSRF 头（HFS OpenAPI 要求）
HFS_ANTI_CSRF_HEADER = "x-hfs-anti-csrf"
HFS_ANTI_CSRF_VALUE = "1"


class HFSClient:
    """
    HFS 服务器 API 客户端。

    认证方式：使用 Basic HTTP 认证或首次请求带 ?login=用户名:密码 建立会话。
    测试示例： base_url="http://127.0.0.1:8280", username="abct", password="abc123"
    """

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        *,
        timeout: float = 30.0,
        verify: bool = True,
    ):
        """
        :param base_url: 服务器根地址，如 http://127.0.0.1:8280（不要带末尾 /data/）
        :param username: 登录用户名，如 abct
        :param password: 登录密码，如 abc123
        :param timeout: 请求超时秒数
        :param verify: 是否验证 HTTPS 证书
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify = verify
        self._api_base = f"{self.base_url}/~/api"
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            # 统一只用 session（?login=）认证，不用 Basic，保证 /~/api/* 与上传等行为一致
            self._client = httpx.Client(
                base_url=self.base_url,
                auth=None,
                timeout=self.timeout,
                verify=self.verify,
                follow_redirects=True,
            )
            if self.username is not None and self.password is not None:
                login_value = f"{self.username}:{self.password}"
                self._client.get(f"/?{urlencode({'login': login_value})}")
        return self._client

    def _post_headers(self) -> dict[str, str]:
        return {HFS_ANTI_CSRF_HEADER: HFS_ANTI_CSRF_VALUE}

    def close(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def __enter__(self) -> HFSClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get_resource_url(self, path: str, *, human_readable: bool = False) -> str:
        """
        返回指定路径对应的可访问 URL（用于上传后生成文件/文件夹链接）。

        :param path: 相对路径，如 "share"、"share/file.txt" 或 "share/sub/file.txt"
        :param human_readable: 为 True 时 path 不百分号编码（空格、括号等人类可读，浏览器粘贴时会自动编码）
        :return: 完整 URL，如 "http://127.0.0.1:8280/share/file.txt"
        """
        raw = self.base_url + _path_for_url(path.strip("/"))
        return _url_path_readable(raw) if human_readable else raw

    def get_uploaded_file_url(
        self,
        folder: str,
        requested_filename: str,
        response: httpx.Response,
    ) -> str:
        """
        根据上传响应解析出实际文件 URL（服务端可能因「同名自动重命名」改了文件名）。

        先尝试响应头 Location；若无则列出父目录，按「精确名或 base (N).ext」+ 最新 mtime 匹配。

        :param folder: 上传时的远程目录，如 "data"
        :param requested_filename: 上传时请求的文件名（可含子路径），如 "file.txt" 或 "sub/file.txt"
        :param response: upload_file 的响应对象
        :return: 实际可访问的完整 URL
        """
        location = response.headers.get("location") or response.headers.get("Location")
        if location:
            location = location.strip()
            if location.startswith(("http://", "https://")):
                return _url_path_readable(location)
            if location.startswith("/"):
                return self.base_url.rstrip("/") + unquote(location)
            # 相对路径
            path = f"{folder.rstrip('/')}/{unquote(location)}".strip("/")
            return self.get_resource_url(path, human_readable=True)
        # 无 Location：列父目录，按「精确或 base (N).ext」+ 最新 mtime 取实际名
        folder = folder.strip("/")
        req_path = Path(requested_filename)
        base_name = req_path.name
        parent_rel = req_path.parent
        parent_path = f"{folder}/{parent_rel}".strip("/") if str(parent_rel) != "." else folder
        uri = "/" + parent_path if parent_path else "/"
        try:
            data = self.get_file_list(uri, request_c_and_m=True)
        except Exception:
            return self.get_resource_url(f"{parent_path}/{base_name}".strip("/"), human_readable=True)
        entries = data.get("list") or []
        stem = req_path.stem
        ext = req_path.suffix
        pattern = re.compile(r"^" + re.escape(stem) + r" \((\d+)\)" + re.escape(ext) + r"$")
        candidates = [
            e for e in entries
            if isinstance(e.get("n"), str) and (e["n"] == base_name or pattern.match(e["n"]))
        ]
        if not candidates:
            return self.get_resource_url(f"{parent_path}/{base_name}".strip("/"), human_readable=True)
        # 服务端同名重命名为 base (1).ext, base (2).ext … 刚上传的为 N 最大的；先按 N 降序，再按 mtime 降序
        def _sort_key(ent: dict[str, Any]) -> tuple[int, str]:
            n = ent.get("n") or ""
            m = pattern.match(n)
            num = int(m.group(1)) if m else 0
            mtime = entry_modified(ent) or ""
            return (num, mtime)
        candidates.sort(key=_sort_key, reverse=True)
        actual_name = candidates[0]["n"]
        full_path = f"{parent_path}/{actual_name}".strip("/")
        return self.get_resource_url(full_path, human_readable=True)

    # ------------------------- 登录与会话 -------------------------

    def login(self) -> bool:
        """
        使用 URL 参数方式建立登录会话（可选）。
        若已使用 Basic 认证构造客户端，则无需单独调用。
        返回是否请求成功（不保证服务端一定接受凭证）。
        """
        if self.username is None or self.password is None:
            return False
        login_value = f"{self.username}:{self.password}"
        url = f"{self.base_url}/?{urlencode({'login': login_value})}"
        try:
            r = self._get_client().get(url)
            return r.is_success
        except Exception:
            return False

    # ------------------------- 文件列表（对应图片中的「谁可以访问列表」等） -------------------------

    def get_file_list(
        self,
        uri: str = "/",
        *,
        offset: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        request_c_and_m: bool = False,
    ) -> FileListResponse:
        """
        获取指定目录下的文件/文件夹列表（含权限与元数据）。

        对应前端「谁可以访问列表」：有权限时才能拿到 list；列表中每项包含：
        - 名称、创建/修改时间、大小
        - 权限缩写 p（r/R/l/L/d 等，仅在与父级不同时返回）

        :param uri: 目录路径，如 "/" 或 "/data"
        :param offset: 跳过条数
        :param limit: 最多返回条数
        :param search: 搜索关键词（含子目录）
        :param request_c_and_m: 是否同时请求 c（创建）和 m（修改）时间
        :return: 含 can_archive, can_upload, can_delete, can_comment, list 等字段
        """
        params: dict[str, Any] = {"uri": uri}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if search:
            params["search"] = search
        if request_c_and_m:
            params["c"] = "1"
        r = self._get_client().get(f"{self._api_base}/get_file_list", params=params)
        r.raise_for_status()
        return r.json()

    def list_entries(self, uri: str = "/", **kwargs: Any) -> list[DirEntry]:
        """便捷方法：只返回 get_file_list 的 list 数组。"""
        data = self.get_file_list(uri, **kwargs)
        return data.get("list", [])

    # ------------------------- 下载（对应「谁可以下载」） -------------------------

    def download_file(
        self,
        path: str,
        save_to: str | None = None,
    ) -> bytes:
        """
        下载文件。GET 指定路径，返回内容；若提供 save_to 则写入该路径。

        :param path: 远程路径，如 "/data/Welcome.md" 或 "share/foo.txt"
        :param save_to: 本地保存路径，若提供则写入文件
        :return: 文件内容（bytes）
        """
        path = path.strip("/")
        # 使用相对路径，避免带 base_url 的 client 将完整 URL 再拼一次
        url = f"/{path}" if path else "/"
        r = self._get_client().get(url)
        r.raise_for_status()
        content = r.content
        if save_to:
            from pathlib import Path

            Path(save_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_to).write_bytes(content)
        return content

    # ------------------------- 上传（对应「谁可以上传」） -------------------------

    UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB，大文件流式上传块大小，避免整文件读入内存

    def _upload_body_and_headers(
        self,
        file_content: BinaryIO | bytes,
        referer: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[bytes | Iterator[bytes], dict[str, str], bool]:
        """生成 PUT body 与 headers；若为可 seek 的文件对象则流式（迭代器 + Content-Length），否则整块读入。on_progress(sent, total) 在流式时每块后调用。"""
        headers = {**self._post_headers(), "Referer": referer}
        if isinstance(file_content, bytes):
            headers["Content-Length"] = str(len(file_content))
            return file_content, headers, False
        try:
            file_content.seek(0, 2)
            size = file_content.tell()
            file_content.seek(0)
        except (AttributeError, OSError):
            body = file_content.read()
            headers["Content-Length"] = str(len(body))
            return body, headers, False

        def stream_chunks() -> Iterator[bytes]:
            sent = 0
            if on_progress:
                on_progress(0, size)
            while True:
                chunk = file_content.read(self.UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                sent += len(chunk)
                if on_progress:
                    on_progress(sent, size)
                yield chunk

        headers["Content-Length"] = str(size)
        return stream_chunks(), headers, True

    def upload_file(
        self,
        folder: str,
        file_content: BinaryIO | bytes,
        filename: str | None = None,
        *,
        use_put: bool = False,
        put_params: dict[str, str] | None = None,
        use_session_for_put: bool = False,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> httpx.Response:
        """
        上传文件到指定目录。大文件会流式上传（按块读取），不整文件读入内存。

        :param folder: 目录路径，如 "" 或 "share" 或 "share/sub"
        :param file_content: 文件内容（文件对象或 bytes）；文件对象支持 seek 时可流式上传
        :param filename: 使用 PUT 时的文件名；POST 时由服务端从 multipart 解析
        :param use_put: True 时用 PUT /{folder}/{filename}，否则用 POST /{folder} multipart
        :param put_params: PUT 时附加的 query 参数（与前端一致时可传 resume=0! 等）
        :param use_session_for_put: True 时用仅 session（无 Basic）发 PUT，与浏览器一致，需先 login()
        :param on_progress: 可选，流式上传时每块后调用 on_progress(sent_bytes, total_bytes)
        :return: 响应对象，可检查 .status_code 与 .json()
        """
        folder = folder.strip("/")
        if use_put:
            if not filename:
                raise ValueError("use_put=True 时必须提供 filename")
            path = f"{folder}/{filename}".replace("//", "/") if folder else filename
            url = _path_for_url(path)
            if put_params:
                url = f"{url}?{urlencode(put_params)}"
            referer = f"{self.base_url}{_path_for_url(folder)}{'/' if folder else ''}" if folder else f"{self.base_url}/"
            body, headers, is_stream = self._upload_body_and_headers(file_content, referer, on_progress)
            # 统一使用同一 client（已通过 ?login= 建立 session），不再单独建 session_client
            client = self._get_client()
            if use_session_for_put and folder:
                client.get(f"{_path_for_url(folder)}/")
            r = client.put(url, content=body, headers=headers)
            # HFS roots：若 host 映射到 root（如 /data），需发 PUT /filename 相对 root
            if r.status_code == 404 and folder:
                url_rel = f"/{filename}?{urlencode(put_params)}" if put_params else f"/{filename}"
                if is_stream and hasattr(file_content, "seek"):
                    file_content.seek(0)
                    body, headers, _ = self._upload_body_and_headers(file_content, referer, on_progress)
                r = client.put(url_rel, content=body, headers=headers)
            return r
        # POST multipart：HFS 文档写的是 curl -F upload=@FILE FOLDER/，字段名用 upload（路径需编码）
        url = f"{self.base_url}{_path_for_url(folder)}" if folder else self.base_url
        if isinstance(file_content, bytes):
            file_content = io.BytesIO(file_content)
        files = {"upload": (filename or "file", file_content, "application/octet-stream")}
        return self._get_client().post(
            url,
            files=files,
            headers=self._post_headers(),
        )

    def upload_folder(
        self,
        parent_folder: str,
        local_path: str | Path,
        *,
        use_put: bool = True,
        on_file_progress: Callable[[int, int, str, int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[tuple[str, str]]]:
        """
        递归上传本地目录内容到远程 parent_folder（rclone 风格：不把本地目录名带到远程）。

        仅上传文件，子目录通过文件名中的路径（如 subdir/file.txt）由服务端自动创建。
        需当前用户有 can_upload 权限。

        :param parent_folder: 远程父目录，如 "data"
        :param local_path: 本地目录路径
        :param use_put: 是否使用 PUT 上传（与 upload_file 一致）
        :param on_file_progress: 可选，每上传一个文件前调用 on_file_progress(当前序号, 总文件数, 相对路径, 文件字节数)
        :param on_progress: 可选，每个文件上传过程中调用 on_progress(已发送字节, 该文件总字节)，用于单文件进度条
        :return: (成功数, 失败列表 [(相对路径, 错误信息)])
        """
        local_path = Path(local_path)
        if not local_path.is_dir():
            raise NotADirectoryError(f"not a directory: {local_path}")
        files = [f for f in sorted(local_path.rglob("*")) if f.is_file()]
        total = len(files)
        ok = 0
        failed: list[tuple[str, str]] = []
        put_params = {"resume": "0!"} if use_put else None
        for idx, f in enumerate(files):
            rel = f.relative_to(local_path)
            rel_str = str(rel).replace("\\", "/")
            file_size = f.stat().st_size
            if on_file_progress is not None:
                on_file_progress(idx + 1, total, rel_str, file_size)
            with f.open("rb") as fp:
                r = self.upload_file(
                    parent_folder,
                    fp,
                    filename=rel_str,
                    use_put=use_put,
                    put_params=put_params,
                    use_session_for_put=use_put,
                    on_progress=on_progress,
                )
            if r.status_code in (200, 201):
                ok += 1
            else:
                failed.append((rel_str, f"{r.status_code} {r.text}"))
        return (ok, failed)

    # ------------------------- 删除（对应「谁可以删除」） -------------------------

    def delete_file(self, folder: str, filename: str) -> httpx.Response:
        """
        删除指定目录下的文件。

        HFS 3：对文件路径发 DELETE 请求（path 即要删除的文件）；需当前用户有 can_delete 权限。

        :param folder: 目录路径，如 "share" 或 "share/sub"
        :param filename: 要删除的文件名（仅文件名，不含路径）
        :return: 响应对象，可检查 .status_code
        """
        folder = folder.strip("/")
        path = f"{folder}/{filename}".replace("//", "/") if folder else filename
        url = f"/{path}" if path else "/"
        return self._get_client().delete(url)

    # ------------------------- 创建目录（与网页「新建文件夹」一致） -------------------------

    def create_folder(self, parent_folder: str, new_name: str, *, use_put: bool = True) -> httpx.Response:
        """
        在指定父目录下创建新文件夹（与 HFS 网页「新建文件夹」等效）。

        实现方式：向 parent_folder/new_name/.keep 上传空文件；HFS 服务端在上传时会
        fs.mkdirSync(dir, { recursive: true })，从而创建 new_name 目录。需当前用户有 can_upload 权限。

        :param parent_folder: 父目录路径，如 "data" 或 "data/sub"
        :param new_name: 新文件夹名称（仅名称，不含路径）
        :param use_put: True 时用 PUT 上传占位文件（推荐）；False 时用 POST multipart
        :return: 响应对象，可检查 .status_code（200/201 表示成功）
        """
        # 占位文件名，与网页新建空文件夹时行为一致（服务端会递归创建父目录）
        placeholder = f"{new_name.strip('/')}/.keep"
        return self.upload_file(
            parent_folder,
            b"",
            filename=placeholder,
            use_put=use_put,
            put_params={"resume": "0!"} if use_put else None,
            use_session_for_put=use_put,
        )

    # ------------------------- 配置（权限、VFS、Serve as web-page 等） -------------------------

    def get_config(
        self,
        only: list[str] | None = None,
        omit: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        获取服务器配置（含 VFS、权限等）。

        :param only: 只返回这些键
        :param omit: 返回除这些键外的所有键
        """
        params: dict[str, Any] = {}
        if only is not None:
            params["only"] = only
        if omit is not None:
            params["omit"] = omit
        r = self._get_client().get(f"{self._api_base}/get_config", params=params)
        r.raise_for_status()
        return r.json()

    def set_config(self, values: dict[str, Any]) -> httpx.Response:
        """
        设置配置项。可用于修改 VFS 节点权限（can_read, can_see, can_upload 等）
        以及「如果找到 index.html 则作为网页提供」等选项（对应 default 等）。

        与界面权限对应关系：
        - can_read: 谁可以下载
        - can_archive: 谁可以压缩
        - can_list: 谁可以访问列表
        - can_delete: 谁可以删除
        - can_upload: 谁可以上传
        - can_see: 谁可以查看
        - default: 如 "index.html" 表示该文件夹「作为网页提供」

        :param values: 配置键值，参见 HFS config.md
        """
        return self._get_client().post(
            f"{self._api_base}/set_config",
            json={"values": values},
            headers=self._post_headers(),
        )

    def get_vfs(self) -> Any:
        """获取当前 VFS 配置（文件/文件夹树及权限）。"""
        return self.get_config(only=["vfs"]).get("vfs", [])

    # ------------------------- 账户（可选，管理员接口） -------------------------

    def get_accounts(self) -> list[dict[str, Any]]:
        """获取账户列表（需管理员权限）。"""
        r = self._get_client().get(f"{self._api_base}/get_accounts")
        r.raise_for_status()
        return r.json().get("list", [])

    def get_usernames(self) -> list[str]:
        """获取用户名列表。"""
        r = self._get_client().get(f"{self._api_base}/get_usernames")
        r.raise_for_status()
        return r.json().get("list", [])

    def get_account(self, username: str) -> dict[str, Any]:
        """获取单个账户信息。"""
        r = self._get_client().get(f"{self._api_base}/get_account", params={"username": username})
        r.raise_for_status()
        return r.json()
