#!/bin/bash
set -e

# 投标标书智能分析监督系统 - Docker 启动脚本

echo "================================================"
echo "  BASS-MVP 后端服务启动"
echo "================================================"

# 确保数据目录存在
mkdir -p /app/data/chromadb
mkdir -p /app/data/uploads
mkdir -p /app/data/logs

echo "数据目录初始化完成"

# 检查必要的环境变量
if [ -z "$GITEE_AI_API_KEY" ]; then
    echo "警告: GITEE_AI_API_KEY 未设置，Embedding 功能将不可用"
fi

echo "Gitee AI Base URL: ${GITEE_AI_BASE_URL:-https://ai.gitee.com/v1}"
echo "ChromaDB 路径: ${CHROMA_DB_PATH:-/app/data/chromadb}"
echo "上传目录: ${UPLOAD_DIR:-/app/data/uploads}"

# 启动 FastAPI 应用
echo "启动 Uvicorn 服务器..."
exec uvicorn app.main:app \
    --host ${HOST:-0.0.0.0} \
    --port ${PORT:-8000} \
    --workers ${WORKERS:-4} \
    --loop asyncio \
    --log-level ${LOG_LEVEL:-info}
