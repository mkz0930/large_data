# prules - 个人编码标准和工作流程

这是一个 Claude Code skill，用于在编码任务中强制执行个人编码标准和 TDD 工作流程。

## 功能特性

- ✅ **测试驱动开发（TDD）**：强制测试先行
- ✅ **中文注释规范**：详细的代码注释要求
- ✅ **完整错误处理**：异常处理 + 日志 + 用户友好提示
- ✅ **代码组织规范**：模块化 + SOLID 原则
- ✅ **Git 工作流**：频繁提交 + 清晰的 commit message
- 🆕 **阶段确认机制**：每个关键阶段完成后等待用户确认
- 🆕 **自动模式**：支持跳过确认，自动完成所有阶段
- 🆕 **变更记录规范**：强制更新 CHANGELOG.md，记录所有变更
- 🆕 **文档组织规范**：一份需求文档 + 多份功能文档的清晰结构
- 🆕 **完整提交要求**：每次 Git 提交必须包含代码、测试、文档和变更日志

## 安装方法

### 方法 1：使用安装脚本（推荐）

#### Linux/macOS:
```bash
cd /path/to/target/project
bash /path/to/this/skill/install.sh .
```

#### Windows PowerShell:
```powershell
cd D:\path\to\target\project
D:\Product\data_summary\.claude\skills\prules\install.ps1 -TargetProject .
```

### 方法 2：手动复制

```bash
# 复制整个 prules 目录到目标项目
cp -r .claude/skills/prules /path/to/target/project/.claude/skills/
```

### 方法 3：创建符号链接

#### Linux/macOS:
```bash
cd /path/to/target/project/.claude/skills/
ln -s /path/to/source/project/.claude/skills/prules prules
```

#### Windows (需要管理员权限):
```cmd
cd D:\TargetProject\.claude\skills\
mklink /D prules D:\Product\data_summary\.claude\skills\prules
```

## 使用方法

安装后，在目标项目中：

```bash
# 手动调用 skill
/prules

# 或者在编码任务中自动应用（无需手动调用）
# 当你请求编写、修改或重构代码时，Claude 会自动遵循这些标准
```

### 工作模式

#### 交互模式（默认）

每个关键阶段完成后都会暂停，等待用户确认：

```
用户: 帮我实现用户注册功能

Claude:
[阶段 1：展示需求分析、技术方案、任务清单]
✋ 这个方案符合你的要求吗？请确认后我将开始编写测试用例。

用户: 确认

Claude:
[阶段 2：展示测试用例]
✋ 测试用例已准备好，请确认后我将开始实现代码。

用户: 继续

Claude:
[阶段 3：展示实现代码]
✋ 实现已完成，所有测试通过。请确认后我将进行最终验证。

用户: 很好

Claude:
[阶段 4：展示最终结果]
✋ 用户注册功能已完成！
```

#### 自动模式

自动完成所有阶段，无需等待确认。启用方式：

**方法 1：在请求中包含关键词**
```
帮我实现用户注册功能，auto 模式
帮我实现用户注册功能，自动执行
帮我实现用户注册功能，no confirm
帮我实现用户注册功能，直接执行
```

**方法 2：创建配置文件（推荐）**
```bash
# 复制配置文件模板
cp .claude/skills/prules/prules.local.md.example .claude/prules.local.md

# 编辑配置文件，设置 mode: auto
```

配置文件内容：
```yaml
---
mode: auto  # 启用自动模式
---
```

自动模式下的行为：
- ✅ 自动完成所有阶段，无需等待确认
- ✅ 仍然会展示每个阶段的输出
- ✅ 遇到错误会自动回滚并重试
- ✅ 完成后展示完整的执行报告

## 文件结构

```
prules/
├── SKILL.md                          # Skill 主文件
├── README.md                         # 本文件
├── install.sh                        # Linux/macOS 安装脚本
├── install.ps1                       # Windows 安装脚本
├── prules.local.md.example           # 配置文件模板
└── coding-standards/                 # 详细编码标准
    ├── comments-guide.md             # 注释规范
    ├── error-handling-guide.md       # 错误处理规范
    ├── code-organization-guide.md    # 代码组织规范
    ├── git-workflow-guide.md         # Git 工作流规范
    ├── workflow-checklist.md         # 工作流程检查清单
    └── CHANGELOG-TEMPLATE.md         # 变更日志模板
```

## 核心工作流程

### 阶段 1：需求理解和头脑风暴 ✋
- 理解需求 → 技术方案设计 → 任务拆分
- **输出**：需求分析、技术方案、任务清单
- **✋ 确认点**：等待用户确认方案（交互模式）

### 阶段 2：测试驱动开发（TDD） ✋
- 先写测试 → 测试失败（红灯）
- **输出**：测试文件、测试用例、测试结果
- **✋ 确认点**：等待用户确认测试用例（交互模式）

### 阶段 3：实现代码 ✋
- Git 提交（回滚点）→ 写代码 → 测试通过（绿灯）
- **输出**：实现代码、测试结果、Git 提交
- **✋ 确认点**：等待用户确认实现（交互模式）

### 阶段 4：完成和验证 ✋
- 运行所有测试 → 代码审查 → **更新 CHANGELOG.md** → **更新功能文档** → 最终提交
- **输出**：测试报告、审查结果、**CHANGELOG 更新**、**文档更新列表**、最终提交
- **✋ 确认点**：等待用户最终确认（交互模式）

**注意**：自动模式下会跳过所有确认点，自动完成所有阶段。

## 文档组织规范

prules 强制执行清晰的文档组织结构：

### 需求文档（唯一）
- **文件**：`README.md` 或 `REQUIREMENTS.md`
- **内容**：项目整体需求、目标、架构说明
- **原则**：只维护一份总体需求文档，不包含具体功能的详细实现

### 功能文档（多份）
- **位置**：`docs/features/` 目录
- **命名**：`功能名称.md`（如 `用户注册.md`、`数据导出.md`）
- **内容**：功能详细说明、API 接口、使用示例、注意事项
- **原则**：每个功能模块维护独立的文档

### 变更日志（必须）
- **文件**：`CHANGELOG.md`
- **内容**：按时间倒序记录所有变更
- **格式**：使用标准格式（日期、版本、变更类型、详细说明）
- **模板**：参考 `coding-standards/CHANGELOG-TEMPLATE.md`

### Git 提交要求

每次提交必须包含：
1. ✅ 代码变更
2. ✅ 相关测试
3. ✅ 文档更新（功能文档）
4. ✅ CHANGELOG.md 更新

**示例提交结构**：
```bash
git add src/services/user_service.py          # 代码
git add tests/test_user_service.py            # 测试
git add docs/features/用户注册.md              # 功能文档
git add CHANGELOG.md                          # 变更日志
git commit -m "feat: 实现用户注册功能

- 新增 UserService 类
- 实现输入验证、密码加密、数据库保存
- 完整的错误处理和日志记录
- 更新 CHANGELOG.md 和功能文档

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## 适用语言

- Python
- JavaScript/TypeScript
- Java
- C#
- Go
- Rust
- 等等

## 自定义

你可以根据项目需求修改 `coding-standards/` 目录下的文件来自定义编码标准。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
