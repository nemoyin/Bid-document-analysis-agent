# ============================================================
# Stage 1: 构建前端
# ============================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund

COPY frontend/ ./
RUN npx vite build

# ============================================================
# Stage 2: 运行后端 + 前端静态文件
# ============================================================
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（PyMuPDF、opencv 等需要）
RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0t64 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        wget && \
    rm -rf /var/lib/apt/lists/*

# 复制后端代码
COPY backend/ ./backend/
WORKDIR /app/backend

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制前端构建产物到 data/frontend-dist
COPY --from=frontend-builder /app/frontend/dist /app/backend/data/frontend-dist

# 创建数据目录
RUN mkdir -p data/uploads data/chromadb data/reports data/logs

# 暴露端口
EXPOSE 8000

# 环境变量
ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite+aiosqlite:///./data/bass.db
ENV FRONTEND_DIST_DIR=/app/backend/data/frontend-dist
ENV PORT=8000
ENV WORKERS=2
ENV LOG_LEVEL=info

CMD uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers ${WORKERS} \
    --log-level ${LOG_LEVEL} \
    --no-access-log
