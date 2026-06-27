/** API response wrapper */
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HealthCheck {
  status: string;
  version: string;
  debug: boolean;
  chroma_initialized: boolean;
}

/** 项目 */
export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  file_count: number;
  risk_level: string | null;
  average_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateRequest {
  name: string;
  description?: string;
}

export interface ProjectUpdateRequest {
  name?: string;
  description?: string;
  status?: string;
}

/** 投标文档 */
export interface BidDocument {
  id: string;
  project_id: string;
  filename: string;
  file_path: string;
  file_size: number | null;
  file_type: string | null;
  status: string;
  parse_status: string | null;
  content_text: string | null;
  page_count: number | null;
  file_metadata: Record<string, any> | null;
  extracted_images: any[] | null;
  parsed_at: string | null;
  created_at: string;
  updated_at: string;
}

export enum ParseStatus {
  UPLOADED = 'uploaded',
  PARSING = 'parsing',
  PARSED = 'parsed',
  FAILED = 'failed',
}

/** 风险等级 */
export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export const RISK_LEVEL_COLORS: Record<string, string> = {
  LOW: '#52c41a',
  MODERATE: '#faad14',
  HIGH: '#fa541c',
  CRITICAL: '#f5222d',
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  LOW: '低风险',
  MODERATE: '中风险',
  HIGH: '高风险',
  CRITICAL: '严重风险',
};

/** 单个维度的进度 */
export interface ProgressDimension {
  status: 'pending' | 'running' | 'completed';
  completed: number;
  total: number;
}

/** 6维度详细进度 */
export interface ProgressDetail {
  current_dimension: string | null;
  dimensions: Record<string, ProgressDimension>;
  issues_found: number;
  overall_progress?: number;
}

/** 6维度元数据 */
export interface DimensionMeta {
  key: string;
  label: string;
  icon: string;
  weight: number;
}

export const DIMENSION_META: DimensionMeta[] = [
  { key: 'text_similarity',      label: '文本相似度',   icon: '📝', weight: 30 },
  { key: 'structure_similarity', label: '目录结构相似', icon: '📑', weight: 15 },
  { key: 'image_similarity',     label: '图片相似度',   icon: '🖼️', weight: 15 },
  { key: 'table_similarity',     label: '表格相似度',   icon: '📊', weight: 10 },
  { key: 'error_consistency',    label: '错别字一致性', icon: '✏️', weight: 20 },
  { key: 'metadata_consistency', label: '元数据一致性', icon: '📋', weight: 10 },
];

/** 分析任务 */
export interface AnalysisTask {
  id: string;
  project_id: string;
  status: string;
  task_type: string;
  progress: number;
  progress_detail: ProgressDetail | null;
  total_comparisons: number;
  completed_comparisons: number;
  issues_found: number;
  estimated_seconds: number | null;
  total_duration_ms: number | null;
  error_message: string | null;
  risk_score: number | null;
  risk_level: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  dimension_scores?: {
    text_score: number;
    structure_score: number;
    image_score: number;
    table_score: number;
    error_score: number;
    metadata_score: number;
  } | null;
}

export interface AnalysisTaskCreateRequest {
  project_id: string;
  task_type: string;
}

/** 文本相似度结果 */
export interface SimilarityResult {
  id: string;
  task_id: string;
  doc1_id: string;
  doc2_id: string;
  full_text_similarity: number | null;
  technical_similarity: number | null;
  business_similarity: number | null;
  structure_similarity: number | null;
  table_similarity: number | null;
  metadata_consistency: number | null;
  details: any | null;
}

/** 错误检测结果 */
export interface ErrorDetectionResult {
  id: string;
  task_id: string;
  document_id: string;
  error_type: string;
  original_text: string;
  corrected_text: string | null;
  position: any | null;
  error_hash: string | null;
  is_shared: boolean | null;
  shared_document_ids: any | null;
}

/** 图片相似结果 */
export interface ImageSimilarityResult {
  id: string;
  task_id: string;
  document_id: string;
  image_hash: string;
  image_path: string;
  similar_image_path?: string | null;
  page_number: number | null;
  hash_algorithm: string;
  similar_image_id: string | null;
  similarity_score: number | null;
}

/** 分析任务详情（含各项结果） */
export interface AnalysisTaskDetail extends AnalysisTask {
  similarity_results: SimilarityResult[];
  error_detection_results: ErrorDetectionResult[];
  image_similarity_results: ImageSimilarityResult[];
}
