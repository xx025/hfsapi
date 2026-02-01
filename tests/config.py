"""
测试用配置：服务器地址、分享路径、账号、下载目录。

仅在此处维护，conftest、main.py 及各 test_*.py 均从此导入。
所有需登录的集成测试会对 HFS_TEST_ACCOUNTS 中每个账号各执行一次。
"""

from pathlib import Path

# 测试服务器
HFS_BASE_URL = "http://127.0.0.1:8280"
HFS_SHARE_URI = "/data"

# 测试账号列表（Any account login 权限）；每个账号都会跑一遍集成测试
HFS_TEST_ACCOUNTS = [
    {"username": "abct", "password": "abc123"},
    {"username": "你好", "password": "abc123"},
]

# 兼容：第一个账号，供 main.py 等单用户场景使用
HFS_USERNAME = HFS_TEST_ACCOUNTS[0]["username"]
HFS_PASSWORD = HFS_TEST_ACCOUNTS[0]["password"]

# 下载保存目录（项目根下的 runs/）
_TESTS_DIR = Path(__file__).resolve().parent
RUNS_DIR = _TESTS_DIR.parent / "runs"
