# hfsapi 使用说明

## 安装（详细）

```bash
# 使用 uv 同步依赖并安装项目（推荐）
uv sync

# 开发与测试：安装 dev 依赖（pytest）
uv sync --group dev
# 或可选依赖：uv sync --extra dev
```

```bash
# 仅 pip
pip install -e .
```

## 与界面权限的对应关系

| 界面项           | API / 配置说明 |
|------------------|----------------|
| 谁可以下载       | 列表项可访问即表示有权限；细粒度由 VFS 节点 `can_read` 控制 |
| 谁可以压缩       | `get_file_list` 返回的 `can_archive`；VFS 节点 `can_archive` |
| 谁可以访问列表   | 能成功调用 `get_file_list` 即有此权限；VFS 节点 `can_list` |
| 谁可以删除       | `can_delete`；VFS 节点 `can_delete` |
| 谁可以上传       | `can_upload`；VFS 节点 `can_upload` |
| 谁可以查看       | VFS 节点 `can_see` |
| 作为网页提供     | VFS 节点 `default: "index.html"`（通过 `set_config` 修改） |

列表项中的 `p` 为权限缩写（仅在与父级不同时返回）：`r`/`R`（下载）、`l`/`L`（列目录）、`d`（删除）。元数据：`n` 名称、`s` 大小、`c` 创建时间、`m` 修改时间。

## 测试环境

测试环境可用 **`tools/docker-compose.yaml`** 启动 HFS 服务：

```bash
cd tools && docker compose up -d
```

启动后需在 HFS 内**手动创建用户**（示例账号：用户名 `abct`、密码 `abc123`），并为分享目录 `/data` 设置「Any account login」等权限，测试与示例脚本才能通过。

- 地址：`http://127.0.0.1:8280/data/`（本机访问可用 `127.0.0.1` 或 `localhost`）
- 示例账号：用户名 `abct`，密码 `abc123`（需在 HFS 中自行创建）

示例脚本与测试的**服务器地址、分享路径、账号**统一写在 **`tests/config.py`**，可按实际环境修改。

运行示例：

```bash
uv run python -m tests.main           # 列出分享目录
uv run python -m tests.main --download  # 列出并下载到 runs/
```

## 运行测试（pytest，uv）

测试针对 **/data** 目录及「Any account login」权限，覆盖：

- **Who can access list**：请求目录列表、列表仅包含可见项、条目元数据
- **Who can zip**：`can_archive` 为 true
- **Who can download**：已登录用户可获取列表
- **Who can delete**：`can_delete` 为 true，并测试先上传再删除（列表中先有后无）
- **Who can upload**：`can_upload` 为 true，并测试实际上传
- **Who can see**：列表中项即当前用户可见项
- 登录与会话、列表项辅助函数（entry_size / entry_created / entry_modified / entry_permissions）

```bash
# 安装依赖（含 dev 组的 pytest）
uv sync --group dev

# 运行全部集成测试（需 HFS 服务器可达）
uv run pytest tests/ -v -m integration

# 仅运行权限相关测试
uv run pytest tests/test_api_permissions.py -v -m integration
```

若使用 pip，可先 `pip install -e ".[dev]"`，再执行 `pytest tests/ -v -m integration`。

若服务器不可达（`http://172.0.0.1:8280`），相关用例会自动 **skip**。

### 上传方式说明

当前测试环境（`http://172.0.0.1:8280/data/`）下，**PUT** 上传可用（与 [HFS 前端](https://github.com/rejetto/hfs) 一致）：  
`PUT http://172.0.0.1:8280/data/文件名?resume=0!`，请求体为文件二进制；需 **session cookie**（无 Basic）+ **Referer**。

```python
# 推荐：与 HFS 前端一致的 PUT 上传（session + Referer）
client.upload_file(
    "share", content, filename="Welcome.md",
    use_put=True, put_params={"resume": "0!"}, use_session_for_put=True,
)
# 或仅 PUT（Basic 认证，部分 HFS 部署可能返回 404）
client.upload_file("share", content, filename="Welcome.md", use_put=True)
```

若使用 POST multipart，需字段名 **`upload`**、路径 `/{folder}`（无末尾斜杠）。  
**PUT 404 与 roots**：HFS 若配置了 [roots](https://github.com/rejetto/hfs)（如 host → `/data`），服务端会做 `ctx.path = join(root, ctx.path)`，此时客户端发 `PUT /data/file` 会变成 `/data//data/file` 导致 404。客户端在 404 时会**自动重试**为 `PUT /filename`（相对 root），则 `ctx.path` 变为 `/data/filename` 可解析。使用 **`use_session_for_put=True`** 与 Referer 与前端一致。

## 发布

推送以 `v` 开头的 tag（如 `v0.1.0`）时，GitHub Action 会：

1. **构建** sdist 与 wheel
2. **上传到 PyPI**（使用 [Trusted Publishing / OIDC](https://docs.pypi.org/trusted-publishers/)，无需在 GitHub 存 token）
3. **创建 GitHub Release**（用 `gh release create`），并将 sdist/wheel 作为附件上传

**PyPI 首次使用：**

1. 在 [PyPI](https://pypi.org) 注册并创建项目（若尚未创建）。
2. 在 PyPI 项目页 **Publishing** → **Add a new pending publisher** 中配置 Trusted Publisher：
   - **Owner**：你的 GitHub 用户名或组织
   - **Repository name**：本仓库名（如 `hfsapi`）
   - **Workflow name**：`publish.yml`
   - **Environment name**：留空
3. 保存后，该 workflow 即可代表该 PyPI 项目发布。

**发布流程：**

```bash
# 确保 pyproject.toml 中 version 已更新
git tag v0.1.0
git push origin v0.1.0
```

完成后可在仓库 **Releases** 页查看并下载对应版本的 sdist/wheel。
