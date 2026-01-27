#!/bin/bash
# prules skill 安装脚本
# 用法: ./install.sh /path/to/target/project

set -e

if [ -z "$1" ]; then
    echo "用法: $0 <目标项目路径>"
    echo "示例: $0 /path/to/my/project"
    exit 1
fi

TARGET_PROJECT="$1"
SKILL_NAME="prules"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$TARGET_PROJECT/.claude/skills/$SKILL_NAME"

echo "📦 正在安装 prules skill..."
echo "源目录: $SOURCE_DIR"
echo "目标目录: $TARGET_DIR"

# 创建目标目录
mkdir -p "$TARGET_PROJECT/.claude/skills"

# 检查目标是否已存在
if [ -e "$TARGET_DIR" ]; then
    echo "⚠️  目标已存在: $TARGET_DIR"
    read -p "是否覆盖? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 安装已取消"
        exit 1
    fi
    rm -rf "$TARGET_DIR"
fi

# 询问安装方式
echo ""
echo "请选择安装方式:"
echo "1) 复制文件（独立副本）"
echo "2) 创建符号链接（共享更新）"
read -p "请选择 (1/2): " -n 1 -r
echo

if [[ $REPLY == "1" ]]; then
    # 复制文件
    cp -r "$SOURCE_DIR" "$TARGET_DIR"
    echo "✅ 已复制 prules skill 到: $TARGET_DIR"
elif [[ $REPLY == "2" ]]; then
    # 创建符号链接
    ln -s "$SOURCE_DIR" "$TARGET_DIR"
    echo "✅ 已创建符号链接: $TARGET_DIR -> $SOURCE_DIR"
else
    echo "❌ 无效选择"
    exit 1
fi

echo ""
echo "🎉 安装完成！"
echo ""
echo "现在你可以在目标项目中使用 /prules 命令了"
