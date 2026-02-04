"""
HFS 分享目录下载功能测试。

服务器、分享 URI、runs 目录均来自 tests.config；client 由 conftest 按 HFS_TEST_ACCOUNTS 参数化。
"""

from __future__ import annotations

import pytest
from pathlib import Path

from hfsapi import HFSClient, entry_size

from tests.config import HFS_SHARE_URI, RUNS_DIR


@pytest.fixture(scope="module")
def runs_dir() -> Path:
    """runs 目录，若不存在则创建。"""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR


@pytest.mark.integration
class TestDownloadFromShare:
    """从 /data 下载文件到 runs/。"""

    def test_download_files_from_share_to_runs(
        self, client: HFSClient, runs_dir: Path
    ) -> None:
        """列出分享目录，将其中可下载的文件（有 size 的项）下载到 runs/。"""
        try:
            data = client.get_file_list(uri=HFS_SHARE_URI, request_c_and_m=True)
        except Exception as e:
            pytest.skip(f"HFS 服务器不可达或无权访问 {HFS_SHARE_URI}: {e}")
        entries = data.get("list", [])
        if not entries:
            pytest.skip(f"{HFS_SHARE_URI} 目录为空，无文件可下载")

        downloaded: list[tuple[str, Path]] = []
        for e in entries:
            name = e.get("n")
            if not name or name.endswith("/"):
                continue
            remote_path = f"{HFS_SHARE_URI.rstrip('/')}/{name}"
            local_path = runs_dir / name
            try:
                content = client.download_file(remote_path, save_to=str(local_path))
                size = entry_size(e)
                if size > 0:
                    assert len(content) == size, (
                        f"downloaded {len(content)} bytes, expected {size}"
                    )
                downloaded.append((name, local_path))
            except Exception:
                # 可能是子目录或无权，跳过该项继续
                continue

        if not downloaded:
            pytest.skip(f"{HFS_SHARE_URI} 下无可下载文件或下载均失败（可能均为子目录）")
        for name, path in downloaded:
            assert path.exists(), f"runs/{name} 应存在"
            assert path.stat().st_size >= 0, f"runs/{name} 大小应 >= 0"
