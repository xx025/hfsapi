# hfsapi

[English](README.md) | **中文**

[![development 100% AI](https://img.shields.io/badge/development-100%25%20AI-8A2BE2)](AI.md)
[![author](https://img.shields.io/badge/author-Multiple%20AI%20models%20(mixed)-blue)](AI.md)

[HFS (HTTP File Server)](https://github.com/rejetto/hfs) 的 Python API 客户端，支持登录、文件列表、上传、配置与权限相关操作。

## 安装

从 PyPI 安装（推荐）：

```bash
pip install hfsapi
# 或
uv add hfsapi
```

从源码安装：

```bash
uv sync
# 或
pip install -e .
```

## 快速开始

```python
from hfsapi import HFSClient, entry_size, entry_created, entry_modified

with HFSClient("http://127.0.0.1:8280", username="abct", password="abc123") as client:
    data = client.get_file_list(uri="/data")
    for e in data.get("list", []):
        print(e["n"], entry_size(e), entry_created(e), entry_modified(e))

    # 创建文件夹（与网页「新建文件夹」一致）
    client.create_folder("data", "myfolder")

    # 上传
    client.upload_file("data", b"content", filename="hello.txt", use_put=True)
```

## CLI

安装后可使用 `hfs` 命令。认证一次保存到本地，其它命令自动使用；未登录时可传 `--base-url`。

```bash
hfs login --base-url http://127.0.0.1:8280 -u abct -p abc123
hfs list /data
hfs upload ./local.txt --folder data
hfs upload ./mydir --folder data   # 目录：递归上传
hfs mkdir data myfolder
hfs download data/foo.txt -o ./foo.txt
hfs delete data foo.txt
hfs config get
hfs vfs
hfs info
hfs logout
```

`hfs --help` 与 `hfs <命令> --help` 查看选项。

## 核心 API

| 方法 / 函数 | 说明 |
|-------------|------|
| **HFSClient**(base_url, username, password, timeout) | 客户端；建议用 `with` 或显式 `close()`。 |
| **login()** | 使用 URL 参数建立会话（与 Basic 二选一或配合使用）。 |
| **get_file_list**(uri, offset, limit, search, request_c_and_m) | 获取目录列表及当前用户在该目录的权限、条目元数据。 |
| **list_entries**(uri, ...) | 仅返回 `get_file_list` 的 `list` 数组。 |
| **upload_file**(folder, file_content, filename, use_put, put_params, use_session_for_put) | 上传文件到指定目录。 |
| **create_folder**(parent_folder, new_name, use_put) | 在父目录下创建新文件夹（与网页「新建文件夹」一致）。 |
| **delete_file**(folder, filename) | 删除指定目录下的文件。 |
| **get_config**(only, omit) / **set_config**(values) | 读取/写入 HFS 配置；可改 VFS 与权限等。 |
| **get_vfs()** | 获取当前 VFS 树（含权限结构）。 |
| **entry_size**(e) / **entry_created**(e) / **entry_modified**(e) / **entry_permissions**(e) | 列表项元数据与权限缩写解析。 |

列表响应中：`n` 名称、`s` 大小、`c`/`m` 创建/修改时间；`can_archive`、`can_upload`、`can_delete` 等表示当前用户在该目录的权限。

更多说明（权限对应、测试、发布、上传方式与 roots 等）见 **[HELP.md](HELP.md)**。

**法律声明：** [DISCLAIMER.md](DISCLAIMER.md) — 不提供担保、不承担责任，使用风险自负。
