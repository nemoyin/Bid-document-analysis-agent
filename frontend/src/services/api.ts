/**
 * API 客户端封装
 * 基于 fetch 的统一请求层，自动处理响应格式和错误。
 */

import type { ApiResponse, Project, BidDocument, AnalysisTask, AnalysisTaskDetail, SimilarityResult, ErrorDetectionResult, ImageSimilarityResult, PaginatedResponse, HealthCheck, ProjectCreateRequest, ProjectUpdateRequest, AnalysisTaskCreateRequest } from '../types';

// ============================================================
// 基础配置
// ============================================================

/**
 * API 基础路径
 * 使用 window.location.origin 确保请求始终发到当前源（避免环境变量被 MSYS2 路径转换破坏）
 */
const API_BASE = `${window.location.origin}/api/v1`;

/**
 * 通用请求函数
 */
async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem('auth_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // 对于 FormData，不设置 Content-Type（浏览器自动设置）
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${response.status}: ${errorText}`);
  }

  const result: ApiResponse<T> = await response.json();

  if (result.code !== 0) {
    throw new Error(result.message || '请求失败');
  }

  return result.data;
}

// ============================================================
// 健康检查
// ============================================================

export const healthApi = {
  check: () => request<HealthCheck>('/health'),
};

// ============================================================
// 项目 API
// ============================================================

export const projectApi = {
  /** 获取项目列表 */
  list: (params?: { page?: number; page_size?: number; search?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    if (params?.search) query.set('search', params.search);
    if (params?.status) query.set('status', params.status);
    const qs = query.toString();
    return request<PaginatedResponse<Project>>(`/projects${qs ? `?${qs}` : ''}`);
  },

  /** 获取项目详情 */
  get: (id: string) => request<Project>(`/projects/${id}`),

  /** 创建项目 */
  create: (data: ProjectCreateRequest) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /** 更新项目 */
  update: (id: string, data: ProjectUpdateRequest) =>
    request<Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 删除项目 */
  delete: (id: string) =>
    request<null>(`/projects/${id}`, { method: 'DELETE' }),
};

// ============================================================
// 文档 API
// ============================================================

export const documentApi = {
  /** 上传文档 */
  upload: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<BidDocument>(
      `/projects/${projectId}/documents/upload`,
      { method: 'POST', body: formData },
    );
  },

  /** 获取文档列表 */
  list: (projectId: string) =>
    request<PaginatedResponse<BidDocument>>(`/projects/${projectId}/documents`),

  /** 获取文档详情 */
  get: (projectId: string, docId: string) =>
    request<BidDocument>(`/projects/${projectId}/documents/${docId}`),

  /** 删除文档 */
  delete: (projectId: string, docId: string) =>
    request<null>(`/projects/${projectId}/documents/${docId}`, { method: 'DELETE' }),

  /** 触发解析 */
  triggerParse: (projectId: string, docId: string) =>
    request<BidDocument>(`/projects/${projectId}/documents/${docId}/parse`, { method: 'POST' }),

  /** 解析状态 */
  getParseStatus: (projectId: string, docId: string) =>
    request<BidDocument>(`/projects/${projectId}/documents/${docId}/parse-status`),
};

// ============================================================
// 分析任务 API
// ============================================================

export const analysisApi = {
  /** 创建并启动分析任务 */
  create: (data: AnalysisTaskCreateRequest) =>
    request<AnalysisTask>('/analysis/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /** 获取任务列表 */
  list: (params?: { project_id?: string; status?: string; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    if (params?.project_id) query.set('project_id', params.project_id);
    if (params?.status) query.set('status', params.status);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    return request<PaginatedResponse<AnalysisTask>>(`/analysis/tasks${qs ? `?${qs}` : ''}`);
  },

  /** 获取任务详情（含所有结果，数据量大） */
  getDetail: (taskId: string) =>
    request<AnalysisTaskDetail>(`/analysis/tasks/${taskId}`),

  /** 获取任务进度（仅进度字段，轻量，适合轮询） */
  getProgress: (taskId: string) =>
    request<AnalysisTask>(`/analysis/tasks/${taskId}?progress_only=true`),

  /** 获取相似度结果 */
  getSimilarityResults: (taskId: string) =>
    request<SimilarityResult[]>(`/analysis/tasks/${taskId}/similarity`),

  /** 获取错误检测结果 */
  getErrorResults: (taskId: string) =>
    request<ErrorDetectionResult[]>(`/analysis/tasks/${taskId}/errors`),

  /** 获取图片相似结果 */
  getImageResults: (taskId: string) =>
    request<ImageSimilarityResult[]>(`/analysis/tasks/${taskId}/images`),
};

// ============================================================
// 报告 API
// ============================================================

export const reportApi = {
  /** 生成并下载报告 */
  download: (projectId: string, taskId: string, format: 'pdf' | 'word') => {
    window.open(`${API_BASE}/projects/${projectId}/reports?task_id=${taskId}&format=${format}`, '_blank');
  },

  /** 获取报告数据 */
  getReportData: (projectId: string, taskId: string) =>
    request<any>(`/projects/${projectId}/reports/data?task_id=${taskId}`),
};
