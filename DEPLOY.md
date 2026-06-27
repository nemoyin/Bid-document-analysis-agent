# BASS-MVP Docker 部署指引

> 投标标书智能分析监督系统 · Bid Analysis Supervision System

---

## 一、镜像文件说明

| 文件 | 大小 | 说明 |
|------|------|------|
| `docker-images/bass-mvp-backend.tar` | ~681 MB | 后端 API 服务（FastAPI + Uvicorn） |
| `docker-images/bass-mvp-frontend.tar` | ~29 MB | 前端 Web 服务（Nginx + 静态文件） |
| `docker-compose.yml` | — | 容器编排配置 |
| `nginx.conf` | — | 前端 Nginx 配置（已内置在前端镜像中） |

---

## 二、环境要求

- **Docker** ≥ 20.10
- **Docker Compose** ≥ 2.0
- 可用磁盘空间：≥ 5 GB
- 操作系统：Linux（推荐）/ Windows / macOS

---

## 三、快速部署

### 3.1 加载镜像

```bash
# 将 docker-images/ 目录拷贝到服务器，然后加载镜像
docker load -i docker-images/bass-mvp-backend.tar
docker load -i docker-images/bass-mvp-frontend.tar
```

### 3.2 配置环境变量（可选）

创建 `.env` 文件，配置 Gitee AI API Key：

```bash
# Gitee AI Embedding API Key（必填，否则文本相似度分析不可用）
GITEE_AI_API_KEY=your_api_key_here
```

### 3.3 启动服务

```bash
# 启动所有服务（后台运行）
docker compose -p bass-mvp up -d

# 查看运行状态
docker compose -p bass-mvp ps

# 查看日志
docker compose -p bass-mvp logs -f
```

### 3.4 停止服务

```bash
docker compose -p bass-mvp down
```

---

## 四、端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| `8083` | 后端 API | FastAPI 服务，同时提供 `/api/docs` Swagger 文档 |
| `5873` | 前端页面 | Nginx 静态文件服务，自动代理 API 到后端 |

---

## 五、访问地址

| 地址 | 说明 |
|------|------|
| `http://<服务器IP>:5873` | 前端管理页面 |
| `http://<服务器IP>:8083/api/docs` | API Swagger 文档 |
| `http://<服务器IP>:8083/api/v1/health` | 健康检查接口 |

---

## 六、目录结构

```
bass-mvp/
├── docker-compose.yml          # 容器编排配置
├── docker-images/              # 镜像导出文件
│   ├── bass-mvp-backend.tar
│   └── bass-mvp-frontend.tar
├── .env                        # 环境变量配置（可选）
└── bass_data/                  # 持久化数据（自动创建）
    ├── bass.db                 # SQLite 数据库
    ├── uploads/                # 上传文件
    ├── chromadb/               # 向量数据库
    ├── reports/                # 分析报告
    └── logs/                   # 日志文件
```

---

## 七、常用命令

```bash
# 查看服务状态
docker compose -p bass-mvp ps

# 查看后端日志
docker logs bass-backend -f --tail 50

# 查看前端日志
docker logs bass-frontend -f --tail 50

# 重启服务
docker compose -p bass-mvp restart

# 停止并删除所有数据（危险操作）
docker compose -p bass-mvp down -v
```

---

## 八、自定义端口

修改 `docker-compose.yml` 中的端口映射：

```yaml
services:
  backend:
    ports:
      - "<自定义端口>:8083"    # 例如 "9090:8083"

  frontend:
    ports:
      - "<自定义端口>:80"      # 例如 "9091:80"
```

修改后重启：

```bash
docker compose -p bass-mvp up -d
```

---

## 九、数据备份

```bash
# 备份数据目录
tar -czf bass-data-backup-$(date +%Y%m%d).tar.gz bass_data/

# 恢复数据
tar -xzf bass-data-backup-XXXXXXXX.tar.gz
```

---

## 十、升级指南

```bash
# 1. 停止旧版本
docker compose -p bass-mvp down

# 2. 加载新镜像
docker load -i docker-images/bass-mvp-backend.tar
docker load -i docker-images/bass-mvp-frontend.tar

# 3. 启动新版本
docker compose -p bass-mvp up -d

# 4. 验证
curl http://localhost:8083/api/v1/health
```

---

## 十一、常见问题

### Q1: 后端容器一直重启/unhealthy？

```bash
# 查看详细错误日志
docker logs bass-backend --tail 100

# 常见原因：
# 1. 数据库文件权限不足 → chmod 777 bass_data/
# 2. 端口冲突 → 检查 8083/5873 是否被占用
# 3. Gitee AI API Key 未配置 → 检查 .env
```

### Q2: 如何启用 Gitee AI Embedding？

创建 `.env` 文件，添加 API Key：

```bash
GITEE_AI_API_KEY=your_key_here
```

然后重启服务。

### Q3: 上传文件提示大小限制？

默认限制 100MB。如需调整，修改 `docker-compose.yml` 中后端的 `MAX_FILE_SIZE` 环境变量（单位：字节）：

```yaml
environment:
  MAX_FILE_SIZE: 209715200   # 200MB
```

### Q4: 如何切换到 PostgreSQL？

修改 `docker-compose.yml` 中后端的 `DATABASE_URL`：

```yaml
environment:
  DATABASE_URL: postgresql+asyncpg://user:password@host:5432/bass_mvp
```

---

## 十二、架构图

```
┌──────────────────────────────────────────────────┐
│              浏览器 :5873                          │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│           Nginx (bass-frontend) :80                │
│   /api → proxy → backend:8083                     │
│   /*   → 静态文件 SPA                              │
└──────────────────────┬───────────────────────────┘
                       │ /api /ws
┌──────────────────────▼───────────────────────────┐
│        FastAPI (bass-backend) :8083               │
│   SQLite + ChromaDB (内置)                         │
└──────────────────────────────────────────────────┘
```

---

> 技术支持：查看 `README.md` 了解系统功能详情
