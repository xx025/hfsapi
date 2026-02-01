# hfsapi

**English** | [中文](README.zh-CN.md)

[![development 100% AI](https://img.shields.io/badge/development-100%25%20AI-8A2BE2)](AI.md)
[![author](https://img.shields.io/badge/author-Multiple%20AI%20models%20(mixed)-blue)](AI.md)

Python API client for [HFS (HTTP File Server)](https://github.com/rejetto/hfs): login, file listing, upload, config, and permissions.

## Install

From PyPI (recommended):

```bash
pip install hfsapi
# or
uv add hfsapi
```

From source:

```bash
uv sync
# or
pip install -e .
```

## Quick start

```python
from hfsapi import HFSClient, entry_size, entry_created, entry_modified

with HFSClient("http://127.0.0.1:8280", username="abct", password="abc123") as client:
    data = client.get_file_list(uri="/data")
    for e in data.get("list", []):
        print(e["n"], entry_size(e), entry_created(e), entry_modified(e))

    # Create folder (same as “New folder” in the web UI)
    client.create_folder("data", "myfolder")

    # Upload
    client.upload_file("data", b"content", filename="hello.txt", use_put=True)
```

## CLI

After `pip install hfsapi`, the `hfs` command is available. Log in once to save credentials locally; all other commands then use them (or pass `--base-url` if not logged in).

```bash
hfs login --base-url http://127.0.0.1:8280 -u abct -p abc123
hfs list /data
hfs upload ./local.txt --folder data
hfs upload ./mydir --folder data   # folder: upload recursively
hfs mkdir data myfolder
hfs download data/foo.txt -o ./foo.txt
hfs delete data foo.txt
hfs config get
hfs vfs
hfs info
hfs logout
```

See `hfs --help` and `hfs <command> --help` for options.

## Core API

| Method / function | Description |
|-------------------|-------------|
| **HFSClient**(base_url, username, password, timeout) | Client; use `with` or call `close()` when done. |
| **login()** | Establish session via URL params (alternative or complement to Basic auth). |
| **get_file_list**(uri, offset, limit, search, request_c_and_m) | Get directory listing, current user permissions, and entry metadata. |
| **list_entries**(uri, ...) | Returns only the `list` array from `get_file_list`. |
| **upload_file**(folder, file_content, filename, use_put, put_params, use_session_for_put) | Upload a file to the given folder. |
| **create_folder**(parent_folder, new_name, use_put) | Create a new folder under the parent (same as “New folder” in the web UI). |
| **delete_file**(folder, filename) | Delete a file under the given folder. |
| **get_config**(only, omit) / **set_config**(values) | Read/write HFS config; e.g. VFS and permissions. |
| **get_vfs()** | Get current VFS tree (including permission structure). |
| **entry_size**(e) / **entry_created**(e) / **entry_modified**(e) / **entry_permissions**(e) | Helpers for list entry metadata and permission abbreviations. |

In list responses: `n` = name, `s` = size, `c`/`m` = created/modified time; `can_archive`, `can_upload`, `can_delete`, etc. indicate the current user’s permissions for that directory.

More details (permission mapping, testing, publishing, upload options and roots) in **[HELP.md](HELP.md)**.

**Legal:** [DISCLAIMER.md](DISCLAIMER.md) — no warranty, no liability, use at your own risk.
