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
# Stage 2: 后端服务
# ============================================================
FROM python:3.12-slim-bookworm

WORKDIR /app

# 安装编译工具 + 系统库（pycairo/pymupdf/opencv 依赖）
# 使用阿里云镜像避免 deb.debian.org 502 问题
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc g++ make pkg-config \
        libcairo2-dev \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
        wget curl && \
    rm -rf /var/lib/apt/lists/*

# 先安装 Python 依赖（利用 Docker 缓存，只有 requirements.txt 变化才重建此层）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 再复制后端代码（代码变化不会导致 pip install 重新执行）
COPY backend/ /app/backend/
WORKDIR /app/backend

# 清理编译工具（减小镜像体积）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get remove -y gcc g++ make pkg-config libcairo2-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist /app/backend/data/frontend-dist

# 创建数据目录
RUN mkdir -p data/uploads data/chromadb data/reports data/logs

EXPOSE 8083

ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite+aiosqlite:///./data/bass.db
ENV FRONTEND_DIST_DIR=/app/backend/data/frontend-dist
ENV PORT=8083
ENV WORKERS=2
ENV LOG_LEVEL=INFO
ENV HOST=0.0.0.0

CMD ["sh", "-c", "exec uvicorn app.main:app \
    --host ${HOST:-0.0.0.0} \
    --port ${PORT:-8083} \
    --workers ${WORKERS:-2} \
    --log-level $(echo ${LOG_LEVEL:-INFO} | tr '[:upper:]' '[:lower:]') \
    --no-access-log"]
