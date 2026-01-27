# 变更日志

本文档记录项目的所有重要变更。

## 格式说明

每个版本的变更记录包含以下部分：

- **Added（新增）**：新增的功能
- **Changed（变更）**：现有功能的变更
- **Fixed（修复）**：Bug 修复
- **Removed（移除）**：移除的功能
- **Security（安全）**：安全相关的修复

## [Unreleased]

### Added
- 待发布的新功能

### Changed
- 待发布的变更

### Fixed
- 待发布的修复

---

## [版本号] - YYYY-MM-DD

### Added
- 新增功能描述
  - 相关文件：`path/to/file.py`
  - 影响范围：模块名称

### Changed
- 变更内容描述
  - 相关文件：`path/to/file.py`
  - 影响范围：模块名称

### Fixed
- 修复的 Bug 描述
  - 相关文件：`path/to/file.py`
  - 问题原因：简要说明
  - 解决方案：简要说明

### Removed
- 移除的功能描述
  - 相关文件：`path/to/file.py`
  - 移除原因：简要说明

---

## 示例

## [1.2.0] - 2024-01-15

### Added
- 新增用户注册功能
  - 相关文件：`src/services/user_service.py`, `tests/test_user_service.py`
  - 影响范围：用户管理模块
  - 功能文档：`docs/features/用户注册.md`

- 新增邮箱验证功能
  - 相关文件：`src/utils/validators.py`
  - 影响范围：输入验证模块

### Changed
- 优化密码加密算法，从 MD5 升级到 bcrypt
  - 相关文件：`src/utils/crypto.py`
  - 影响范围：安全模块
  - 迁移说明：需要重置所有用户密码

### Fixed
- 修复登录时的空指针异常
  - 相关文件：`src/services/auth_service.py:45`
  - 问题原因：未检查用户是否存在
  - 解决方案：添加用户存在性检查

### Security
- 修复 SQL 注入漏洞
  - 相关文件：`src/database/query_builder.py`
  - 影响范围：数据库查询模块
  - 解决方案：使用参数化查询

---

## [1.1.0] - 2024-01-01

### Added
- 新增用户登录功能
  - 相关文件：`src/services/auth_service.py`
  - 影响范围：认证模块

### Changed
- 重构数据库连接池
  - 相关文件：`src/database/connection.py`
  - 影响范围：数据库模块

---

## [1.0.0] - 2023-12-15

### Added
- 项目初始化
- 基础架构搭建
- 核心模块实现
