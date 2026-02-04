"""
测试用配置：服务器地址、分享路径、账号、下载目录。

仅在此处维护，conftest、main.py 及各 test_*.py 均从此导入。
- 集成测试：对 HFS_TEST_ACCOUNTS 中每个账号各执行一次（API + CLI 集成）。
- 单元测试：用本配置中的 URL/路径做 mock 或断言，保证多条件覆盖。
"""

from pathlib import Path

# ---------- 服务器与路径 ----------
HFS_BASE_URL = "http://127.0.0.1:8280"
HFS_SHARE_URI = "/data"
# 分享目录名（无前导斜杠），用于 upload_file(folder, ...)、delete_file(folder, filename) 等
HFS_SHARE_NAME = HFS_SHARE_URI.strip("/").split("/")[0] if HFS_SHARE_URI.strip("/") else "data"

# 示例路径（CLI/API 测试中用于「路径 vs 完整 URL」等多条件）
HFS_SAMPLE_REMOTE_FILE = "data/sample.txt"
HFS_SAMPLE_REMOTE_DIR = "data"
HFS_FULL_URL_LIST = f"{HFS_BASE_URL}/data"
HFS_FULL_URL_FILE = f"{HFS_BASE_URL}/data/sample.txt"

# ---------- 账号 ----------
# 每个账号都会跑一遍集成测试（list/upload/download/delete/mkdir 等）
HFS_TEST_ACCOUNTS = [
    {"username": "abct", "password": "abc123"},
    {"username": "你好", "password": "abc123"},
]
# 兼容：第一个账号，供 main.py、单用户 CLI 单元测试等使用
HFS_USERNAME = HFS_TEST_ACCOUNTS[0]["username"]
HFS_PASSWORD = HFS_TEST_ACCOUNTS[0]["password"]

# ---------- 本地目录 ----------
_TESTS_DIR = Path(__file__).resolve().parent
RUNS_DIR = _TESTS_DIR.parent / "runs"
