#!/bin/bash
# ============================================================
# AI 论坛世界引擎 - 启动脚本
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从 .env.example 复制..."
    cp .env.example .env
    echo "📝 请编辑 .env 文件填入你的 API 密钥，然后重新运行此脚本"
    exit 1
fi

# 创建数据目录
mkdir -p data/avatars data/post_images data/news_images

echo "🚀 启动 AI 论坛世界引擎..."
echo ""

# 启动方式选择
if [ "$1" = "dev" ]; then
    echo "📦 开发模式启动..."
    echo ""

    # 启动数据库
    echo "🐘 启动 PostgreSQL..."
    docker compose up postgres -d

    # 等待数据库就绪
    echo "⏳ 等待数据库就绪..."
    sleep 3

    # 启动后端
    echo "🐍 启动后端（conda ai-forum）..."
    conda run -n ai-forum --no-banner \
        uvicorn app.main:app --reload --port 8000 --app-dir backend &
    BACKEND_PID=$!
    echo "   后端 PID: $BACKEND_PID"

    # 启动前端
    if [ -d "frontend/node_modules" ]; then
        echo "⚛️  启动前端..."
        cd frontend && npm run dev &
        FRONTEND_PID=$!
        echo "   前端 PID: $FRONTEND_PID"
        cd ..
    else
        echo "⚠️  前端未安装依赖，跳过。请先运行: cd frontend && npm install"
    fi

    echo ""
    echo "✅ 开发模式已启动"
    echo "   后端 API:  http://localhost:8000/docs"
    echo "   前端:      http://localhost:3000"
    echo ""
    echo "按 Ctrl+C 停止所有服务"

    # 等待中断
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose stop postgres; echo '已停止'" INT TERM
    wait

else
    echo "🐳 Docker Compose 生产模式启动..."
    echo ""
    docker compose up -d --build
    echo ""
    echo "✅ 所有服务已启动"
    echo "   论坛地址:  http://localhost"
    echo "   后端 API:  http://localhost:8000/docs"
    echo "   健康检查:  http://localhost:8000/api/health"
    echo ""
    echo "📊 查看日志: docker compose logs -f"
    echo "🛑 停止服务: ./stop.sh"
fi
