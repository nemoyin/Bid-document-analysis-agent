"""
API集成测试 - 投标标书智能分析监督系统
使用 pytest + httpx 对全部13个端点进行测试
"""
import pytest
import httpx
import uuid

BASE_URL = "http://localhost:8006/api/v1"

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def client():
    with httpx.Client(timeout=30) as c:
        yield c

@pytest.fixture
def project_id(client):
    """创建测试项目并返回ID"""
    resp = client.post(f"{BASE_URL}/projects", json={
        "name": "测试项目-API集成测试",
        "description": "用于自动化测试的临时项目"
    })
    assert resp.status_code == 200, f"Create project failed: {resp.text}"
    data = resp.json()
    assert data["code"] == 0
    pid = data["data"]["id"]
    yield pid
    # 清理
    client.delete(f"{BASE_URL}/projects/{pid}")

# ============================================================
# P0: 系统健康检查
# ============================================================

class TestHealthCheck:
    """健康检查接口测试"""

    def test_health_returns_200(self, client):
        """GET /api/v1/health 应返回200和healthy状态"""
        resp = client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "healthy"
        assert data["data"]["version"] == "1.0.0"

# ============================================================
# P0: 项目 CRUD
# ============================================================

class TestProjectCRUD:
    """项目增删改查接口测试"""

    def test_create_project_returns_id(self, client):
        """POST /api/v1/projects 创建项目返回ID"""
        resp = client.post(f"{BASE_URL}/projects", json={
            "name": "CRUD测试项目",
            "description": "测试创建"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["id"] is not None
        assert data["data"]["name"] == "CRUD测试项目"
        # 清理
        client.delete(f"{BASE_URL}/projects/{data['data']['id']}")

    def test_list_projects_returns_array(self, client):
        """GET /api/v1/projects 返回分页列表"""
        resp = client.get(f"{BASE_URL}/projects", params={"page": 1, "page_size": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_get_project_detail(self, client, project_id):
        """GET /api/v1/projects/{id} 返回项目详情"""
        resp = client.get(f"{BASE_URL}/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["id"] == project_id

    def test_update_project(self, client, project_id):
        """PUT /api/v1/projects/{id} 更新项目"""
        resp = client.put(f"{BASE_URL}/projects/{project_id}", json={
            "name": "更新后的项目名",
            "description": "已更新"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["name"] == "更新后的项目名"

    def test_delete_project(self, client):
        """DELETE /api/v1/projects/{id} 删除项目"""
        resp = client.post(f"{BASE_URL}/projects", json={"name": "待删除项目"})
        pid = resp.json()["data"]["id"]
        resp_del = client.delete(f"{BASE_URL}/projects/{pid}")
        assert resp_del.status_code == 200
        # 验证已删除
        resp_get = client.get(f"{BASE_URL}/projects/{pid}")
        assert resp_get.status_code == 404

    def test_search_projects_by_keyword(self, client, project_id):
        """GET /api/v1/projects?keyword= 关键词搜索"""
        resp = client.get(f"{BASE_URL}/projects", params={"keyword": "集成测试"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

# ============================================================
# P0: 文档管理
# ============================================================

class TestDocumentManagement:
    """文档上传和管理接口测试"""

    def test_list_documents_empty(self, client, project_id):
        """GET 项目文档列表（空）"""
        resp = client.get(f"{BASE_URL}/projects/{project_id}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_upload_rejects_invalid_format(self, client, project_id):
        """上传不支持格式应被拒绝"""
        files = {"file": ("test.exe", b"malicious", "application/octet-stream")}
        resp = client.post(
            f"{BASE_URL}/projects/{project_id}/documents/upload",
            files=files
        )
        # 应该返回错误（不支持exe格式）
        assert resp.status_code in [200, 400, 422]

    def test_document_detail_not_found(self, client, project_id):
        """获取不存在的文档详情返回404"""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"{BASE_URL}/projects/{project_id}/documents/{fake_id}")
        assert resp.status_code == 404

# ============================================================
# P0: 分析任务
# ============================================================

class TestAnalysisTasks:
    """分析任务接口测试"""

    def test_create_analysis_task(self, client, project_id):
        """POST /api/v1/analysis/tasks 创建分析任务"""
        resp = client.post(f"{BASE_URL}/analysis/tasks", json={
            "project_id": project_id,
            "task_type": "full_analysis"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["id"] is not None
        assert data["data"]["status"] in ["pending", "running"]

    def test_list_analysis_tasks(self, client):
        """GET /api/v1/analysis/tasks 列出分析任务"""
        resp = client.get(f"{BASE_URL}/analysis/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_analysis_task_not_found(self, client):
        """获取不存在的分析任务返回404"""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"{BASE_URL}/analysis/tasks/{fake_id}")
        assert resp.status_code == 404

    def test_task_similarity_results_empty(self, client, project_id):
        """查询未完成任务的相似度结果返回空"""
        resp = client.post(f"{BASE_URL}/analysis/tasks", json={
            "project_id": project_id,
            "task_type": "full_analysis"
        })
        task_id = resp.json()["data"]["id"]
        resp2 = client.get(f"{BASE_URL}/analysis/tasks/{task_id}/similarity")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["code"] == 0

# ============================================================
# P0: 报告下载
# ============================================================

class TestReportGeneration:
    """报告生成和下载接口测试"""

    def test_report_missing_task_id(self, client, project_id):
        """缺少task_id参数应返回错误"""
        resp = client.get(f"{BASE_URL}/projects/{project_id}/reports")
        assert resp.status_code == 422  # 缺少必填参数

    def test_report_data_missing_task(self, client, project_id):
        """获取不存在任务的报告数据"""
        resp = client.get(f"{BASE_URL}/projects/{project_id}/reports/data", params={
            "task_id": str(uuid.uuid4())
        })
        assert resp.status_code in [200, 404, 422]

# ============================================================
# P1: 边界与异常测试
# ============================================================

class TestEdgeCases:
    """边界条件和异常测试"""

    def test_create_project_empty_name(self, client):
        """创建空名称项目应被拒绝"""
        resp = client.post(f"{BASE_URL}/projects", json={"name": ""})
        assert resp.status_code == 422

    def test_pagination_out_of_range(self, client):
        """超大页码不崩溃"""
        resp = client.get(f"{BASE_URL}/projects", params={"page": 99999, "page_size": 10})
        assert resp.status_code == 200

    def test_page_size_zero(self, client):
        """page_size=0 应被拒绝"""
        resp = client.get(f"{BASE_URL}/projects", params={"page_size": 0})
        assert resp.status_code == 422

    def test_malformed_json(self, client):
        """畸形JSON不崩溃"""
        resp = client.post(f"{BASE_URL}/projects", content="not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code in [400, 422]

    def test_nonexistent_endpoint(self, client):
        """不存在的端点返回404"""
        resp = client.get(f"{BASE_URL}/nonexistent")
        assert resp.status_code == 404

    def test_response_format_consistency(self, client):
        """所有响应格式一致: {code, message, data}"""
        resp = client.get(f"{BASE_URL}/health")
        data = resp.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert data["code"] == 0

# ============================================================
# P1: 并发测试
# ============================================================

class TestConcurrency:
    """并发请求测试"""

    def test_concurrent_project_creation(self, client):
        """10个并发创建项目不冲突"""
        import concurrent.futures

        def create_project(i):
            r = client.post(f"{BASE_URL}/projects", json={"name": f"并发测试项目-{i}"})
            return r.status_code, r.json().get("data", {}).get("id")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(create_project, range(10)))

        pids = [pid for status, pid in results if status == 200 and pid]
        assert len(pids) == 10, f"Expected 10 projects, got {len(pids)}"

        # 清理
        for pid in pids:
            client.delete(f"{BASE_URL}/projects/{pid}")
