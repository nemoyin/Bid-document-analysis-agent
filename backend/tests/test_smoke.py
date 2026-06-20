"""
冒烟测试 (Smoke Tests) - 投标标书智能分析监督系统
快速验证核心按项目ID关联的接口全部能返回 2xx，不返回 500。

覆盖：
- 项目详情 GET /api/v1/projects/{id}
- 项目文档列表 GET /api/v1/projects/{id}/documents
- 项目分析任务列表 GET /api/v1/projects/{id}/analysis/tasks
- 项目报告列表 GET /api/v1/projects/{id}/reports
- 分析任务详情 GET /api/v1/analysis/tasks/{id}
- 分析任务相似度 GET /api/v1/analysis/tasks/{id}/similarity
- 健康检查 GET /api/v1/health

设计原则：
- 不依赖外网（不调用 Gitee AI Embedding）
- 不依赖真实文档上传
- 每个用例 < 1s
- 失败即视为 500-class 故障回归
"""
import uuid
import pytest
import httpx

BASE_URL = "http://localhost:8006/api/v1"


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def client():
    with httpx.Client(timeout=15) as c:
        yield c


@pytest.fixture
def project(client):
    """创建一个真实项目供冒烟测试使用"""
    resp = client.post(
        f"{BASE_URL}/projects",
        json={"name": "SMOKE-PROJECT", "description": "smoke test fixture"},
    )
    assert resp.status_code == 200, f"create project failed: {resp.text}"
    pid = resp.json()["data"]["id"]
    yield pid
    # 清理
    client.delete(f"{BASE_URL}/projects/{pid}")


# ============================================================
# 冒烟测试：所有核心 GET 端点不能 500
# ============================================================

class TestSmokeProjectEndpoints:
    """项目维度冒烟：所有按 project_id 查询的端点不能 500"""

    def test_health_ok(self, client):
        """GET /health 必须 200"""
        r = client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_get_project_detail_no_500(self, client, project):
        """GET /projects/{id} 详情 (用户报告 500 的接口)"""
        r = client.get(f"{BASE_URL}/projects/{project}")
        # 关键断言：不能 5xx
        assert r.status_code < 500, f"5xx returned: {r.status_code} {r.text}"
        # 正常应该是 200
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["id"] == project

    def test_list_project_documents_no_500(self, client, project):
        """GET /projects/{id}/documents 文档列表"""
        r = client.get(f"{BASE_URL}/projects/{project}/documents")
        assert r.status_code < 500, f"5xx: {r.status_code} {r.text}"
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert "items" in data["data"]

    def test_list_project_analysis_tasks_no_500(self, client, project):
        """GET /analysis/tasks?project_id= 项目分析任务"""
        r = client.get(f"{BASE_URL}/analysis/tasks", params={"project_id": project})
        assert r.status_code < 500, f"5xx: {r.status_code} {r.text}"
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0

    def test_list_project_reports_no_500(self, client, project):
        """GET /projects/{id}/reports 项目报告列表"""
        r = client.get(f"{BASE_URL}/projects/{project}/reports")
        assert r.status_code < 500, f"5xx: {r.status_code} {r.text}"
        # 422 是因为缺 task_id，不是 5xx
        assert r.status_code in (200, 422)

    def test_get_project_report_data_no_500(self, client, project):
        """GET /projects/{id}/reports/data 报告数据"""
        r = client.get(
            f"{BASE_URL}/projects/{project}/reports/data",
            params={"task_id": str(uuid.uuid4())},
        )
        assert r.status_code < 500, f"5xx: {r.status_code} {r.text}"


# ============================================================
# 冒烟测试：分析任务端点
# ============================================================

class TestSmokeAnalysisEndpoints:
    """分析任务维度冒烟"""

    def test_create_task_no_500(self, client, project):
        """POST /analysis/tasks 创建任务"""
        r = client.post(
            f"{BASE_URL}/analysis/tasks",
            json={"project_id": project, "task_type": "full_analysis"},
        )
        assert r.status_code < 500, f"5xx: {r.status_code} {r.text}"
        assert r.status_code == 200
        task_id = r.json()["data"]["id"]

        # 详情
        r2 = client.get(f"{BASE_URL}/analysis/tasks/{task_id}")
        assert r2.status_code < 500
        assert r2.status_code == 200

        # 相似度
        r3 = client.get(f"{BASE_URL}/analysis/tasks/{task_id}/similarity")
        assert r3.status_code < 500
        assert r3.status_code == 200

    def test_list_all_analysis_tasks_no_500(self, client):
        """GET /analysis/tasks 全量任务"""
        r = client.get(f"{BASE_URL}/analysis/tasks")
        assert r.status_code < 500
        assert r.status_code == 200


# ============================================================
# 冒烟测试：404 路径
# ============================================================

class TestSmokeNotFound:
    """不存在资源必须返回 404，不能 500"""

    def test_project_not_found_returns_404(self, client):
        """不存在的项目 ID 必须 404，不能 500"""
        fake = str(uuid.uuid4())
        r = client.get(f"{BASE_URL}/projects/{fake}")
        assert r.status_code == 404, f"expected 404, got {r.status_code}"

    def test_task_not_found_returns_404(self, client):
        """不存在的任务 ID 必须 404，不能 500"""
        fake = str(uuid.uuid4())
        r = client.get(f"{BASE_URL}/analysis/tasks/{fake}")
        assert r.status_code == 404, f"expected 404, got {r.status_code}"

    def test_document_not_found_returns_404(self, client, project):
        """不存在的文档 ID 必须 404"""
        fake = str(uuid.uuid4())
        r = client.get(f"{BASE_URL}/projects/{project}/documents/{fake}")
        assert r.status_code == 404


# ============================================================
# 冒烟测试：响应格式一致性
# ============================================================

class TestSmokeResponseFormat:
    """所有 2xx 响应必须是统一信封 {code, message, data}"""

    def test_envelope_on_list(self, client):
        r = client.get(f"{BASE_URL}/projects")
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"code", "message", "data"}

    def test_envelope_on_detail(self, client, project):
        r = client.get(f"{BASE_URL}/projects/{project}")
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) >= {"code", "message", "data"}
        assert d["code"] == 0
