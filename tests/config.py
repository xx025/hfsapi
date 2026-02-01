"""
测试用配置：服务器地址、分享路径、账号、下载目录。

仅在此处维护，conftest、main.py 及各 test_*.py 均从此导入。
"""

from pathlib import Path

# 测试服务器
HFS_BASE_URL = "http://127.0.0.1:8280"
HFS_SHARE_URI = "/data"

# 测试账号（Any account login 权限）
HFS_USERNAME = "abct"
HFS_PASSWORD = "abc123"

# 下载保存目录（项目根下的 runs/）
_TESTS_DIR = Path(__file__).resolve().parent
RUNS_DIR = _TESTS_DIR.parent / "runs"
