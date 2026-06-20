# Bid Analysis Supervision System

> Bid Analysis Supervision System — AI-powered bid document analysis for detecting collusion, bid rigging, and affiliated bidding patterns.

[English](#english) | [中文](#中文)

---

## English

### Overview

**BASS-MVP** is an AI-powered bid document analysis platform designed to automatically parse, compare, and analyze bidding documents from multiple vendors. By detecting abnormal similarities in text, images, tables, and error patterns, it identifies potential bid rigging, collusion, and affiliated bidding behaviors, generating actionable supervisory leads and comprehensive risk assessment reports.

### Key Features

| Module | Description |
|--------|-------------|
| **Multi-format Upload** | Supports PDF, DOC, DOCX, and ZIP batch uploads (20+ files per project) |
| **Intelligent Parsing** | Extracts text, metadata, images, and tables; OCR for scanned PDFs via PaddleOCR |
| **Text Similarity Analysis** | Gitee AI Embedding API (Qwen3-Embedding-8B) + Cosine Similarity for full-text and chapter-level comparison |
| **Image Similarity Detection** | Multi-hash fusion (pHash / dHash / aHash) to identify same-source images across bids |
| **Error Consistency Check** | Detects identical typos, grammar errors, and omissions shared across different bidders' documents |
| **Risk Scoring Engine** | Six-dimensional weighted scoring (0–100) with automatic risk level classification |
| **Similarity Matrix** | N×N matrix heatmap visualization of pairwise similarity between all bidders |
| **Report Generation** | Exportable risk analysis reports in PDF and Word formats with online preview |

### Risk Scoring Model

| Dimension | Weight | Score Range |
|-----------|--------|-------------|
| Text Similarity | 30% | 0–30 |
| Directory Structure Similarity | 15% | 0–15 |
| Image Similarity | 15% | 0–15 |
| Table Similarity | 10% | 0–10 |
| Typo Consistency | 20% | 0–20 |
| Metadata Consistency | 10% | 0–10 |

**Risk Levels**: Low (0–30) · Medium (31–60) · High (61–80) · Critical (81–100)

### Tech Stack

#### Frontend
![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.2-3178C6?logo=typescript)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?logo=vite)
![Ant Design](https://img.shields.io/badge/Ant_Design-5.12-0170FE?logo=ant-design)

- **Framework**: React 18 + TypeScript + Vite 5
- **UI Library**: Ant Design 5 + ProComponents
- **State Management**: Zustand + Immer
- **Charts**: ECharts 5 (similarity matrix, risk trends)
- **Preview**: PDF.js + Mammoth (DOCX)

#### Backend
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7.2-DC382D?logo=redis)

- **Framework**: FastAPI + Uvicorn (async)
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 ORM
- **Vector Database**: ChromaDB 0.4 (embedded, <100K vectors)
- **Task Queue**: Celery + Redis + Flower
- **Embedding**: Gitee AI API (Qwen3-Embedding-8B, 768-dim)

#### Document Processing
- **Parsing**: PyMuPDF, PyPDF2, pdfplumber, python-docx
- **OCR**: PaddleOCR 3.0 (scanned PDFs)
- **Text Analysis**: jieba (segmentation), pycorrector (typo detection), scikit-learn
- **Image Hashing**: imagehash (pHash / dHash / aHash), OpenCV

### Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                 │
│   Project Analysis │ Document Compare │ Report   │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────┐
│                API Gateway (FastAPI)              │
│    Upload  │  Analysis  │  Report  │  Query      │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Business Services                    │
│  Parser │ Text/Image/Error Analyzer │ Scorer     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│                 Data Layer                        │
│  PostgreSQL │ ChromaDB (Vector) │ Redis (Cache)  │
└─────────────────────────────────────────────────┘
```

### Project Structure

```
bass-mvp/
├── frontend/                # React + TypeScript frontend
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   │   ├── upload/      # File upload, drag-and-drop
│   │   │   ├── analysis/    # SimilarityMatrix, RiskScoreChart
│   │   │   ├── report/      # ReportPreview, ReportDownload
│   │   │   └── layout/      # AppLayout, Sidebar, Header
│   │   ├── pages/           # Page-level components
│   │   │   ├── ProjectAnalysis/
│   │   │   └── ReportView/
│   │   ├── services/        # API client, WebSocket
│   │   ├── store/           # Zustand state management
│   │   └── hooks/           # Custom React hooks
│   ├── vite.config.ts
│   └── package.json
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/          # RESTful API endpoints
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Business logic
│   │   │   ├── parser/      # Document parsing engine
│   │   │   ├── analyzer/    # Text/Image/Error analysis
│   │   │   ├── embedding/   # Gitee AI + ChromaDB
│   │   │   ├── scoring/     # Risk scoring model
│   │   │   └── report/      # PDF/Word generation
│   │   ├── tasks/           # Celery async tasks
│   │   ├── db/              # Database session & migrations
│   │   └── vector_db/       # ChromaDB client
│   ├── tests/
│   ├── requirements.txt
│   └── docker/
├── docs/                    # Documentation
├── test_data/               # Sample test fixtures
├── PRD-投标标书智能分析监督系统.md
├── 架构设计-投标标书智能分析监督系统.md
├── Dockerfile
└── projects.yaml
```

### Getting Started

#### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **PostgreSQL** 16+
- **Redis** 7.2+
- **Docker** & **Docker Compose** (optional)

#### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Gitee AI API key and database credentials

# Start services (PostgreSQL + Redis via Docker)
cd docker
docker-compose -f docker-compose.dev.yml up -d

# Run database migrations
cd ..
alembic upgrade head

# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info &

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# → http://localhost:5173
```

#### Docker Deployment

```bash
docker-compose up -d
# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Flower Monitor: http://localhost:5555
```

### API Documentation

Once the backend is running, interactive API docs are available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

#### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/upload/{project_id}` | Upload bid files |
| `POST` | `/api/v1/analysis/{project_id}/start` | Start analysis task |
| `GET` | `/api/v1/analysis/{project_id}/status` | Check analysis progress |
| `GET` | `/api/v1/analysis/{project_id}/similarity-matrix` | Get similarity matrix |
| `GET` | `/api/v1/analysis/{project_id}/errors` | Get error consistency results |
| `GET` | `/api/v1/analysis/{project_id}/images` | Get image similarity results |
| `POST` | `/api/v1/reports/{project_id}/generate` | Generate risk report |
| `GET` | `/api/v1/reports/{report_id}/download` | Download report file |
| `WS` | `/ws/analysis/{project_id}` | Real-time progress stream |

### MVP Scope

**Included (P0)**:
- ✅ Multi-format file upload (PDF/DOC/DOCX/ZIP)
- ✅ Document parsing with OCR
- ✅ Text similarity analysis (embedding + cosine)
- ✅ Image similarity detection (multi-hash)
- ✅ Error consistency analysis
- ✅ Risk scoring and classification
- ✅ PDF/Word report generation

**Deferred (P1/P2)**:
- ❌ Template reuse analysis
- ❌ Table similarity analysis
- ❌ File metadata analysis
- ❌ Side-by-side document comparison view
- ❌ Dashboard homepage
- ❌ Case management & workflow engine

### License

This project is for internal use. All rights reserved.

---

## 中文

### 项目概述

**投标标书智能分析监督系统 (BASS-MVP)** 是一个基于人工智能的投标文件分析平台。通过对多个投标人的标书进行自动解析和多维度比对，发现文本相似、图片同源、错别字一致等围标串标异常特征，自动生成风险评分和监督线索报告。

### 核心功能

| 功能模块 | 说明 |
|----------|------|
| **多格式上传** | 支持 PDF、DOC、DOCX、ZIP 批量上传（单项目支持 20+ 文件） |
| **智能解析** | 提取文本、元数据、图片、表格；扫描件自动 OCR（PaddleOCR） |
| **文本相似度** | Gitee AI Embedding API (Qwen3-Embedding-8B) + 余弦相似度，支持全文/章节/段落级比对 |
| **图片同源检测** | pHash / dHash / aHash 三哈希融合判断，识别不同标书中的相同图片 |
| **错别字一致性** | 自动识别并比对不同标书中的相同错别字、语病、漏字错误 |
| **风险评分模型** | 六维度加权评分（0–100 分），自动划分风险等级 |
| **相似度矩阵** | N×N 矩阵热力图可视化展示企业间相似度 |
| **报告生成** | 支持 PDF / Word 格式导出，在线预览 |

### 风险评分模型

| 评分维度 | 权重 | 分值范围 |
|----------|------|----------|
| 文本相似度 | 30% | 0–30 |
| 目录结构相似 | 15% | 0–15 |
| 图片相似 | 15% | 0–15 |
| 表格相似 | 10% | 0–10 |
| 错别字一致 | 20% | 0–20 |
| 元数据一致 | 10% | 0–10 |

**风险等级**: 低风险 (0–30) · 中风险 (31–60) · 高风险 (61–80) · 严重风险 (81–100)

### 技术栈

#### 前端
![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.2-3178C6?logo=typescript)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?logo=vite)
![Ant Design](https://img.shields.io/badge/Ant_Design-5.12-0170FE?logo=ant-design)

- **核心框架**: React 18 + TypeScript + Vite 5
- **UI 组件库**: Ant Design 5 + ProComponents
- **状态管理**: Zustand + Immer
- **图表可视化**: ECharts 5（相似度矩阵、风险趋势图）
- **文档预览**: PDF.js + Mammoth (DOCX)

#### 后端
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7.2-DC382D?logo=redis)

- **核心框架**: FastAPI + Uvicorn（异步高性能）
- **关系数据库**: PostgreSQL 16 + SQLAlchemy 2.0 ORM
- **向量数据库**: ChromaDB 0.4（内置服务，MVP 阶段 <10 万条向量）
- **异步任务**: Celery + Redis + Flower 监控
- **Embedding**: Gitee AI API (Qwen3-Embedding-8B, 768 维)

#### 文档处理
- **解析引擎**: PyMuPDF, PyPDF2, pdfplumber, python-docx
- **OCR 识别**: PaddleOCR 3.0（扫描版 PDF）
- **文本分析**: jieba 分词, pycorrector 错别字检测, scikit-learn
- **图片哈希**: imagehash (pHash / dHash / aHash), OpenCV

### 系统架构

```
┌─────────────────────────────────────────────────┐
│                   前端层 (React)                   │
│     项目分析  │  标书对比  │  报告预览            │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────┐
│                API 网关层 (FastAPI)                │
│    上传  │  分析  │  报告  │  查询               │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│               业务逻辑层 (Services)                │
│  解析器  │  文本/图片/错误分析器  │  评分引擎     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│                 数据持久层                         │
│  PostgreSQL  │  ChromaDB (向量)  │  Redis (缓存)  │
└─────────────────────────────────────────────────┘
```

### 项目结构

```
bass-mvp/
├── frontend/                # React + TypeScript 前端
│   ├── src/
│   │   ├── components/      # 可复用 UI 组件
│   │   │   ├── upload/      # 文件上传、拖拽上传
│   │   │   ├── analysis/    # 相似度矩阵、风险评分图表
│   │   │   ├── report/      # 报告预览、报告下载
│   │   │   └── layout/      # 应用布局、侧边栏、顶栏
│   │   ├── pages/           # 页面级组件
│   │   │   ├── ProjectAnalysis/  # 项目分析页
│   │   │   └── ReportView/       # 报告查看页
│   │   ├── services/        # API 客户端、WebSocket
│   │   ├── store/           # Zustand 状态管理
│   │   └── hooks/           # 自定义 React Hooks
│   ├── vite.config.ts
│   └── package.json
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # RESTful API 接口
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── schemas/         # Pydantic 数据校验
│   │   ├── services/        # 业务逻辑层
│   │   │   ├── parser/      # 文档解析引擎
│   │   │   ├── analyzer/    # 文本/图片/错误分析
│   │   │   ├── embedding/   # Gitee AI + ChromaDB
│   │   │   ├── scoring/     # 风险评分模型
│   │   │   └── report/      # PDF/Word 报告生成
│   │   ├── tasks/           # Celery 异步任务
│   │   ├── db/              # 数据库会话与迁移
│   │   └── vector_db/       # ChromaDB 客户端
│   ├── tests/               # 测试用例
│   ├── requirements.txt
│   └── docker/
├── docs/                    # 项目文档
├── test_data/               # 测试数据
├── PRD-投标标书智能分析监督系统.md    # 产品需求文档
├── 架构设计-投标标书智能分析监督系统.md  # 架构设计文档
├── Dockerfile
└── projects.yaml
```

### 快速开始

#### 环境要求

- **Python** 3.10+
- **Node.js** 18+
- **PostgreSQL** 16+
- **Redis** 7.2+
- **Docker** & **Docker Compose**（可选）

#### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Gitee AI API Key 和数据库连接信息

# 启动依赖服务（PostgreSQL + Redis）
cd docker
docker-compose -f docker-compose.dev.yml up -d

# 执行数据库迁移
cd ..
alembic upgrade head

# 启动 Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info &

# 启动 API 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
# → http://localhost:5173
```

#### Docker 部署

```bash
docker-compose up -d
# 前端: http://localhost
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
# Flower 监控: http://localhost:5555
```

### API 接口文档

后端启动后，可通过以下地址访问交互式 API 文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

#### 核心接口

| 方法 | 接口 | 说明 |
|------|------|------|
| `POST` | `/api/v1/upload/{project_id}` | 上传投标文件 |
| `POST` | `/api/v1/analysis/{project_id}/start` | 启动分析任务 |
| `GET` | `/api/v1/analysis/{project_id}/status` | 查询分析进度 |
| `GET` | `/api/v1/analysis/{project_id}/similarity-matrix` | 获取相似度矩阵 |
| `GET` | `/api/v1/analysis/{project_id}/errors` | 获取错误一致性结果 |
| `GET` | `/api/v1/analysis/{project_id}/images` | 获取图片相似度结果 |
| `POST` | `/api/v1/reports/{project_id}/generate` | 生成风险报告 |
| `GET` | `/api/v1/reports/{report_id}/download` | 下载报告文件 |
| `WS` | `/ws/analysis/{project_id}` | 实时分析进度推送 |

### MVP 范围

**本期实现 (P0)**:
- ✅ 多格式文件上传（PDF/DOC/DOCX/ZIP）
- ✅ 文档解析与 OCR 识别
- ✅ 文本相似度分析（Embedding + 余弦相似度）
- ✅ 图片同源检测（多哈希融合）
- ✅ 错别字一致性分析
- ✅ 风险评分与等级分类
- ✅ PDF/Word 报告生成与在线预览

**后续版本 (P1/P2)**:
- ❌ 模板复用分析
- ❌ 表格相似分析
- ❌ 文件元数据分析
- ❌ 标书左右对比视图
- ❌ 首页仪表盘
- ❌ 案件管理与工作流引擎

### 术语说明

| 术语 | 定义 |
|------|------|
| 围标 | 多个投标人事先串通，轮流中标或抬高标价的行为 |
| 串标 | 投标人与招标人串通，泄露标底或其他投标人信息的行为 |
| 陪标 | 投标人受雇于其他投标人，以陪衬身份参与投标的行为 |
| 关联投标 | 存在关联关系（如母子公司、同一实际控制人）的投标人同时参与同一项目投标 |
| Embedding | 将文本转换为向量表示的技术，用于计算语义相似度 |
| Cosine Similarity | 余弦相似度，衡量两个向量方向上的相似性 |

### 许可证

本项目为内部使用。保留所有权利。
