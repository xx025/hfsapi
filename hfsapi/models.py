"""
HFS API 数据模型（与 OpenAPI / 前端一致）。

与界面「谁可以下载/压缩/访问列表/删除/上传/查看」对应：
- 列表项中的 p：权限缩写，仅在与父级不同时返回。
  - r: 不可下载  R: 仅其他凭证可下载
  - l: 不可列目录  L: 仅其他凭证可列目录
  - d: 可删除
- 修改这些权限需通过 set_config 修改 VFS 节点上的 can_read / can_archive / can_list / can_delete / can_upload / can_see。
"""

from typing import Any

# DirEntry：get_file_list 返回的 list 中每一项
# n=名称, c=创建时间, m=修改时间, s=大小(字节), p=权限缩写, comment=注释
DirEntry = dict[str, Any]

# get_file_list 响应：can_archive, can_upload, can_delete, can_comment, list
FileListResponse = dict[str, Any]


def entry_size(entry: DirEntry) -> int:
    """条目大小（字节），文件夹可为 0 或未提供。"""
    return int(entry.get("s") or 0)


def entry_created(entry: DirEntry) -> str | None:
    """条目创建时间（ISO 字符串）。"""
    return entry.get("c")


def entry_modified(entry: DirEntry) -> str | None:
    """条目修改时间（ISO 字符串）。"""
    return entry.get("m")


def entry_permissions(entry: DirEntry) -> str:
    """权限字符串，如 'rLd'；仅在与父级不同时存在。"""
    return entry.get("p") or ""
