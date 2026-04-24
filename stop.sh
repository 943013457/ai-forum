#!/bin/bash
# ============================================================
# AI 论坛世界引擎 - 停止脚本
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 停止 AI 论坛世界引擎..."
echo ""

if [ "$1" = "dev" ]; then
    echo "📦 停止开发模式服务..."

    # 停止后端
    pkill -f "uvicorn app.main:app" 2>/dev/null && echo "   ✅ 后端已停止" || echo "   ⚠️  后端未运行"

    # 停止前端
    pkill -f "vite" 2>/dev/null && echo "   ✅ 前端已停止" || echo "   ⚠️  前端未运行"

    # 停止数据库
    docker compose stop postgres
    echo "   ✅ 数据库已停止"

elif [ "$1" = "clean" ]; then
    echo "🧹 完全清理（停止并删除容器、卷）..."
    docker compose down -v
    echo "   ✅ 容器和卷已删除"

else
    echo "🐳 停止 Docker Compose 服务..."
    docker compose down
    echo "   ✅ 所有容器已停止"
fi

echo ""
echo "✅ 完成"
echo ""
echo "用法:"
echo "  ./stop.sh         停止生产模式（保留数据）"
echo "  ./stop.sh dev     停止开发模式"
echo "  ./stop.sh clean   停止并删除所有数据（⚠️ 不可恢复）"
