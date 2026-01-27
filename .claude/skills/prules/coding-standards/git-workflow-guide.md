# Git 版本管理规范

## 分支策略

- `main/master`: 主分支，始终保持可部署状态
- `develop`: 开发分支
- `feature/*`: 功能分支（例如：`feature/user-authentication`）
- `bugfix/*`: 修复分支（例如：`bugfix/login-error`）
- `hotfix/*`: 紧急修复分支（例如：`hotfix/security-patch`）

## Commit 规范

### Commit Message 格式

```
<type>: <subject>

<body>（可选）

<footer>（可选）
```

### Type 类型

- `feat`: 新功能
- `fix`: 修复 bug
- `refactor`: 重构（既不是新功能也不是修复 bug）
- `test`: 添加或修改测试
- `docs`: 文档更新
- `style`: 代码格式调整（不影响代码逻辑）
- `chore`: 构建/工具变动
- `perf`: 性能优化

### Commit Message 示例

```bash
# 简单的 commit
feat: 添加用户注册功能

# 带详细说明的 commit
fix: 修复登录时的会话过期问题

当用户在登录页面停留超过30分钟后，会话会过期，
但系统没有正确处理这种情况，导致用户无法登录。

现在添加了会话过期检测和友好的错误提示。

Closes #123
```

## 工作流程

### 1. 开始新功能

```bash
# 从 develop 分支创建新的功能分支
git checkout develop
git pull origin develop
git checkout -b feature/user-authentication

# 开始开发...
```

### 2. 提交代码

```bash
# 查看修改
git status
git diff

# 添加文件到暂存区
git add src/services/user_service.py
git add tests/services/test_user_service.py

# 提交（使用 HEREDOC 确保格式正确）
git commit -m "$(cat <<'EOF'
feat: 实现用户注册功能

添加了用户注册的核心逻辑，包括：
- 输入验证
- 密码加密
- 数据库保存
- 错误处理

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

### 3. 推送到远程

```bash
# 首次推送需要设置上游分支
git push -u origin feature/user-authentication

# 后续推送
git push
```

### 4. 合并到 develop

```bash
# 切换到 develop 分支
git checkout develop
git pull origin develop

# 合并功能分支
git merge feature/user-authentication

# 推送到远程
git push origin develop

# 删除本地功能分支（可选）
git branch -d feature/user-authentication
```

## 回滚策略

### 1. 撤销未提交的修改

```bash
# 撤销工作区的修改（危险操作！）
git checkout -- <file>

# 撤销所有未提交的修改（危险操作！）
git reset --hard HEAD
```

### 2. 撤销已提交但未推送的 commit

```bash
# 撤销最后一次 commit，保留修改
git reset --soft HEAD~1

# 撤销最后一次 commit，丢弃修改（危险操作！）
git reset --hard HEAD~1
```

### 3. 撤销已推送的 commit

```bash
# 创建一个新的 commit 来撤销之前的修改
git revert <commit-hash>

# 推送到远程
git push
```

### 4. 临时保存工作

```bash
# 保存当前工作到 stash
git stash save "临时保存：正在开发的用户认证功能"

# 查看 stash 列表
git stash list

# 恢复 stash
git stash pop

# 或者应用 stash 但不删除
git stash apply
```

## 标签管理

### 创建标签

```bash
# 创建轻量标签
git tag v1.0.0

# 创建带注释的标签（推荐）
git tag -a v1.0.0 -m "版本 1.0.0：首次正式发布"

# 推送标签到远程
git push origin v1.0.0

# 推送所有标签
git push origin --tags
```

### 查看标签

```bash
# 列出所有标签
git tag

# 查看标签详情
git show v1.0.0
```

## 最佳实践

### 1. 频繁提交

- 每完成一个小功能就提交
- 提交粒度要小，方便回滚
- 每次提交都应该是一个可工作的状态

### 2. 清晰的 Commit Message

- 使用清晰、描述性的 commit message
- 说明"做了什么"和"为什么这样做"
- 遵循团队的 commit message 规范

### 3. 使用分支

- 不要直接在 main/master 分支上开发
- 为每个功能创建独立的分支
- 功能完成后合并到 develop 分支

### 4. 定期同步

```bash
# 定期从远程拉取最新代码
git pull origin develop

# 或者使用 rebase 保持提交历史整洁
git pull --rebase origin develop
```

### 5. 代码审查

- 使用 Pull Request 进行代码审查
- 合并前确保所有测试通过
- 至少一个团队成员审查代码

## 常用命令速查

```bash
# 查看状态
git status

# 查看修改
git diff
git diff --staged

# 查看提交历史
git log
git log --oneline
git log --graph --oneline --all

# 查看某个文件的修改历史
git log -p <file>

# 查看某次提交的详情
git show <commit-hash>

# 查看分支
git branch
git branch -a  # 包括远程分支

# 切换分支
git checkout <branch>
git switch <branch>  # Git 2.23+

# 创建并切换分支
git checkout -b <branch>
git switch -c <branch>  # Git 2.23+

# 删除分支
git branch -d <branch>  # 安全删除
git branch -D <branch>  # 强制删除

# 合并分支
git merge <branch>

# 变基
git rebase <branch>

# 暂存
git stash
git stash pop
git stash list
git stash apply

# 标签
git tag
git tag -a <tag> -m "message"
git push origin <tag>
```

## 危险操作警告

以下操作会丢失数据，使用前请三思：

```bash
# ⚠️ 危险：丢弃所有未提交的修改
git reset --hard HEAD

# ⚠️ 危险：强制推送（会覆盖远程历史）
git push --force

# ⚠️ 危险：删除未跟踪的文件
git clean -fd
```

## TDD 工作流中的 Git 使用

### 红灯阶段（测试失败）

```bash
# 编写测试后提交
git add tests/test_user_service.py
git commit -m "test: 添加用户注册功能的测试用例"
```

### 绿灯阶段（测试通过）

```bash
# 实现功能后提交
git add src/user_service.py
git commit -m "feat: 实现用户注册功能"
```

### 重构阶段

```bash
# 重构后提交
git add src/user_service.py
git commit -m "refactor: 优化用户注册逻辑，提高代码可读性"
```

### 测试失败时回滚

```bash
# 如果测试失败且无法快速修复，回滚到上一个稳定版本
git reset --hard HEAD

# 或者回滚到特定的 commit
git reset --hard <commit-hash>
```
