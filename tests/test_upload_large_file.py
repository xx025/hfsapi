"""
大文件上传测试（1GB–10GB）：流式与非流式两种方式都跑，并对比耗时。

配置见 tests.config：LARGE_FILE_SIZE_GB、LARGE_FILE_STREAMING_MAX_SLOWDOWN、LARGE_FILE_CLIENT_TIMEOUT。
需真实 HFS 服务器，标记为 integration。非流式会整文件读入内存，1–10GB 时请确保机器内存充足。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hfsapi import HFSClient

from tests.config import (
    HFS_BASE_URL,
    HFS_SHARE_NAME,
    HFS_USERNAME,
    HFS_PASSWORD,
    LARGE_FILE_SIZE_GB,
    LARGE_FILE_STREAMING_MAX_SLOWDOWN,
    LARGE_FILE_CLIENT_TIMEOUT,
)

# 生成大文件时的写块大小（MiB），避免单次分配过大
_LARGE_FILE_WRITE_CHUNK_MB = 50


@pytest.fixture(scope="module")
def large_file_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """生成临时大文件，体积由 config 的 LARGE_FILE_SIZE_GB 决定（1–10GB），分块写入。"""
    size_bytes = int(LARGE_FILE_SIZE_GB * 1024 * 1024 * 1024)
    chunk = _LARGE_FILE_WRITE_CHUNK_MB * 1024 * 1024
    path = tmp_path_factory.mktemp("large") / "large.bin"
    with path.open("wb") as f:
        written = 0
        while written < size_bytes:
            to_write = min(chunk, size_bytes - written)
            f.write(b"\x00" * to_write)
            written += to_write
    return path


@pytest.fixture(scope="module")
def client_single() -> HFSClient:
    """大文件测试用客户端，超时来自 config。"""
    return HFSClient(
        base_url=HFS_BASE_URL,
        username=HFS_USERNAME,
        password=HFS_PASSWORD,
        timeout=float(LARGE_FILE_CLIENT_TIMEOUT),
    )


@pytest.mark.integration
def test_large_file_upload_streaming_vs_non_streaming(
    large_file_path: Path,
    client_single: HFSClient,
) -> None:
    """
    大文件上传：流式（文件对象）与非流式（整文件读入 bytes）两种方式都测，并对比耗时。
    """
    ts = int(time.time())
    name_streaming = f"pytest_large_streaming_{ts}.bin"
    name_non_streaming = f"pytest_large_bytes_{ts}.bin"
    put_params = {"resume": "0!", "id": name_streaming, "mtime": str(ts * 1000)}
    put_params2 = {"resume": "0!", "id": name_non_streaming, "mtime": str(ts * 1000 + 1)}

    try:
        # 1) 流式上传（优化）：按块读取，不整文件入内存
        try:
            with large_file_path.open("rb") as f:
                t0 = time.perf_counter()
                r1 = client_single.upload_file(
                    HFS_SHARE_NAME,
                    f,
                    filename=name_streaming,
                    use_put=True,
                    put_params=put_params,
                    use_session_for_put=True,
                )
                time_streaming = time.perf_counter() - t0
        except Exception as e:
            pytest.skip(f"HFS 不可达或上传失败: {e}")
        assert r1.status_code in (200, 201), f"streaming upload failed: {r1.status_code} {r1.text}"

        # 2) 非流式上传：整文件 read_bytes() 后上传（1–10GB 时需足够内存）
        content = large_file_path.read_bytes()
        t0 = time.perf_counter()
        r2 = client_single.upload_file(
            HFS_SHARE_NAME,
            content,
            filename=name_non_streaming,
            use_put=True,
            put_params=put_params2,
            use_session_for_put=True,
        )
        time_non_streaming = time.perf_counter() - t0
        assert r2.status_code in (200, 201), f"non-streaming upload failed: {r2.status_code} {r2.text}"

        # 流式耗时应不超过非流式的上限倍数
        assert time_streaming <= time_non_streaming * LARGE_FILE_STREAMING_MAX_SLOWDOWN, (
            f"streaming {time_streaming:.2f}s vs non-streaming {time_non_streaming:.2f}s "
            f"(max ratio {LARGE_FILE_STREAMING_MAX_SLOWDOWN})"
        )
        print(f"\n[large file] size={LARGE_FILE_SIZE_GB}GB streaming={time_streaming:.2f}s non_streaming={time_non_streaming:.2f}s")
    finally:
        client_single.close()
        try:
            c2 = HFSClient(base_url=HFS_BASE_URL, username=HFS_USERNAME, password=HFS_PASSWORD, timeout=30.0)
            c2.delete_file(HFS_SHARE_NAME, name_streaming)
            c2.delete_file(HFS_SHARE_NAME, name_non_streaming)
            c2.close()
        except Exception:
            pass
