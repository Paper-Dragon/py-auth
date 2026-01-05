# 更新日志 (CHANGELOG)

本文档记录项目的所有重要变更。

## [0.1.2] - 2025-01-05

### 🔥 重大变更 (Breaking Changes)

#### 客户端变更

**AuthClient 类：**
- `software_name` 参数从可选变为**必填**，且参数位置调整为第二个参数（在 `server_url` 之后）
- `device_id` 参数位置调整为第三个参数（在 `software_name` 之后）
- `software_name` 现在用于生成 device_id，确保同一设备上的不同软件有不同的 device_id

**AuthCache 类：**
- `software_name` 参数现在是必填参数
- 缓存文件名基于 `device_id + software_name` 生成，确保不同软件使用不同的缓存文件
- 加密密钥包含 `software_name`，确保不同软件的缓存相互独立

**设备ID生成 (`build_device_id`)：**
- `build_device_id()` 函数现在接收 `software_name` 参数
- device_id 生成时包含 `software_name`，确保不同软件有不同的 device_id
- 设备ID持久化路径包含 `software_name`，不同软件使用不同的持久化文件（`~/.py_auth_device/device_{server_hash}_{software_hash}.txt`）

**辅助函数：**
- `check_authorization()` 函数的参数顺序调整：`software_name` 从第三个参数变为第二个参数（必填）

### ✨ 新增功能

- ✅ **多软件授权支持**：同一台电脑上的多款软件可以独立授权
- ✅ 每个软件使用独立的授权记录和缓存文件
- ✅ 支持为不同软件设置不同的授权状态

### 🔄 改进

- ✅ **优化了设备ID生成**：在客户端生成 device_id 时包含 software_name，确保不同软件有不同的 device_id
- ✅ 改进了缓存机制，不同软件的缓存相互隔离
- ✅ 改进了设备ID持久化，不同软件使用不同的持久化文件

### 📝 迁移指南

**对于代码迁移：**

所有使用 `AuthClient` 的代码需要更新，`software_name` 现在是必填的第二个参数：

```python
# 0.1.2 之前（software_name 是可选的第三个参数）
client = AuthClient(
    server_url="http://localhost:8000",
    device_id="xxx",  # 可选
    software_name="我的软件"  # 可选
)

# 0.1.2 及之后（software_name 是必填的第二个参数）
client = AuthClient(
    server_url="http://localhost:8000",
    software_name="我的软件",  # 必填，第二个参数
    device_id="xxx"  # 可选，第三个参数
)
```

**重要说明：**
- 升级后，同一台电脑上的不同软件会有不同的 device_id（因为 device_id 包含 software_name）
- 旧的 device_id 可能无法继续使用，需要重新授权
- 建议清空本地设备ID缓存文件（`~/.py_auth_device/` 目录）

### 🐛 修复

- 修复了同一设备上多款软件共享授权记录的问题
- 修复了不同软件缓存相互覆盖的问题

---

## [0.1.1] - 2025-12-30

### 🔄 改进

- ✅ 添加 GitHub Actions 构建工作流
- ✅ 优化构建包配置

---

## [0.1.0] - 2025-12-30

### ✨ 新增功能

- ✅ **远端 API 和缓存功能实现**：完善了客户端与服务端的交互逻辑
- ✅ 优化了授权客户端代码结构
- ✅ 改进了设备工具函数

### 🔄 改进

- ✅ 重构了 `auth_client.py`，提升了代码可维护性
- ✅ 优化了 `device_utils.py` 的设备信息收集逻辑
- ✅ 更新了客户端使用示例

---

