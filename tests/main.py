"""
HFS API 示例：连接测试服务器，列出分享目录；可选将文件下载到 runs/。

测试地址与账号见 tests.config。

用法:
  uv run python -m tests.main           # 列出分享目录
  uv run python -m tests.main --download  # 列出并将文件下载到 runs/
"""

import argparse
import sys
from pathlib import Path

# 从 tests/ 直接运行 python main.py 时，把项目根加入 path
_root = Path(__file__).resolve().parent.parent
if _root not in [Path(p).resolve() for p in sys.path]:
    sys.path.insert(0, str(_root))

from tests.config import HFS_BASE_URL, HFS_PASSWORD, HFS_SHARE_URI, HFS_USERNAME, RUNS_DIR

from hfsapi import (
    HFSClient,
    entry_created,
    entry_modified,
    entry_permissions,
    entry_size,
)


def download_share_to_runs(client: HFSClient) -> int:
    """将分享目录下文件下载到 runs/，返回成功下载数量。"""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    data = client.get_file_list(uri=HFS_SHARE_URI, request_c_and_m=True)
    entries = data.get("list", [])
    count = 0
    for e in entries:
        name = e.get("n")
        if not name or name.endswith("/"):
            continue
        remote_path = f"{HFS_SHARE_URI.rstrip('/')}/{name}"
        local_path = RUNS_DIR / name
        try:
            client.download_file(remote_path, save_to=str(local_path))
            size = entry_size(e)
            print(f"  已下载: {name} ({size} B) -> runs/{name}")
            count += 1
        except Exception as err:
            print(f"  跳过 {name}: {err}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="HFS 分享列表示例，可选下载到 runs/")
    parser.add_argument("--download", action="store_true", help="将分享目录下文件下载到 runs/")
    args = parser.parse_args()

    with HFSClient(HFS_BASE_URL, username=HFS_USERNAME, password=HFS_PASSWORD) as client:
        client.login()
        data = client.get_file_list(uri=HFS_SHARE_URI, request_c_and_m=True)
        entries = data.get("list", [])
        print(f"目录 {HFS_SHARE_URI} 共 {len(entries)} 项")
        print(f"当前用户：可压缩={data.get('can_archive')}, 可上传={data.get('can_upload')}, 可删除={data.get('can_delete')}")
        print()

        for e in entries[:20]:
            name = e.get("n", "")
            size = entry_size(e)
            created = entry_created(e) or "-"
            modified = entry_modified(e) or "-"
            perm = entry_permissions(e)
            perm_str = f" [权限: {perm}]" if perm else ""
            print(f"  {name}  大小: {size} B  创建: {created}  修改: {modified}{perm_str}")

        if len(entries) > 20:
            print(f"  ... 其余 {len(entries) - 20} 项省略")

        if args.download:
            print()
            print(f"下载到 {RUNS_DIR} ...")
            n = download_share_to_runs(client)
            print(f"共下载 {n} 个文件到 runs/")


if __name__ == "__main__":
    main()
