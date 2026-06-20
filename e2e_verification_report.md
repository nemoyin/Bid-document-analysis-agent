# BASS-MVP 端到端主流程验证报告

**测试时间**: 2026-06-13 03:14 ~ 03:23  
**测试环境**: 后端 http://localhost:8006, 前端 http://localhost:5273  
**测试数据**: QA-E2E-TEST 项目 / 1个PDF投标文件

---

## 验证结果汇总

| 步骤 | 操作 | 结果 | 备注 |
|------|------|------|------|
| 1 | 健康检查 `GET /api/v1/health` | ✅ PASS | code=0, status=healthy, chroma_initialized=true |
| 2 | 创建项目 `POST /api/v1/projects` | ✅ PASS | 返回项目ID, name, status=active |
| 3 | 上传文件 `POST .../documents/upload` | ✅ PASS | 975 bytes PDF, status=uploaded |
| 4 | 触发解析 `POST .../documents/{id}/parse` | ✅ PASS | 后台异步完成, status=parsed, page_count=1 |
| 5 | 创建分析任务 `POST /api/v1/analysis/tasks` | ✅ PASS | status=completed, risk_score=0, risk_level=low |
| 6 | 获取分析结果 (similarity/errors/images) | ✅ PASS | 空数组（单文档场景正常） |
| 7a | 报告数据 `GET .../reports/data` | ✅ PASS | 返回项目名+风险评分+统计 |
| **7b** | **报告下载 Word 格式** | **⚠️ FIXED** | **原500→修复后200 OK** |
| 8 | 前端页面 `http://localhost:5273/` | ✅ PASS | 首页200, 项目详情页200 |

## 发现的问题与修复

### 🔴 Blocker (已修复): Word 报告下载 500

**症状**: 下载 Word 报告时 HTTP 500，后端日志报错:
```
'latin-1' codec can't encode characters in position 34-37: ordinal not in range(256)
```

**根因**: `reports.py` 中的 `Content-Disposition` 头直接使用中文文件名（`QA-E2E-TEST_分析报告_20260613.docx`），FastAPI 的 `Response` 默认以 latin-1 编码响应头，中文字符无法被 latin-1 编码。

**修复**: 改用 RFC 5987 标准，在 `Content-Disposition` 中使用 `filename*=UTF-8''{percent_encoded_filename}`，通过 `urllib.parse.quote()` 对文件名进行百分号编码。

**涉及文件**: `backend/app/api/v1/reports.py`

### 🟡 次要发现: 文本相似度阶段 numpy 布尔值异常

**日志**: `[阶段3/5] 文本相似度分析失败: The truth value of an array with more than one element is ambiguous`

**说明**: 单文档场景下不影响整体流程（异常被 Orchestrator 捕获，任务正常完成）。但多文档对比分析时需关注此 issue，可能影响相似度计算的准确性。

---

## 结论

**主流程基本 PASS**，8项核心步骤全部可通过。

- 唯一 Blocker（Word 报告中文编码崩溃）已在本次验证中 **定位并修复**
- 建议后续修复 `text_similarity.py` 中的 numpy 数组布尔值判断问题
- 建议补充多文档场景的 E2E 覆盖测试
