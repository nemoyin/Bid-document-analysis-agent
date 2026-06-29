/**
 * 项目详情页面（核心页面）
 * 包含文档管理、分析总览、文本相似度、目录结构、图片相似、表格相似、错误检测、元数据一致性 8 个 Tab。
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Tabs, Card, Table, Button, Upload, Tag, Progress, Typography,
  message, Breadcrumb, Space, Empty, Spin, List, Tooltip, Descriptions,
} from 'antd';
import {
  UploadOutlined, PlayCircleOutlined, FileTextOutlined,
  BarChartOutlined, PictureOutlined, AlertOutlined,
  ReloadOutlined, DownloadOutlined, HomeOutlined, LoadingOutlined,
  MenuOutlined, TableOutlined, DatabaseOutlined,
  ToolOutlined, SafetyOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { projectApi, documentApi, analysisApi, complianceApi } from '../../services/api';
import type { Project, BidDocument, AnalysisTask, AnalysisTaskDetail, ComplianceAnalysis } from '../../types';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '../../types';
import RiskOverviewCard from './components/RiskOverviewCard';
import SimilarityTable from './components/SimilarityTable';
import ImageGallery from './components/ImageGallery';
import AnalysisProgressPanel from './components/AnalysisProgressPanel';
import CompliancePanel from './components/CompliancePanel';
import styles from './index.module.css';

const { Title, Text } = Typography;

const ProjectDetail: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<BidDocument[]>([]);
  const [tasks, setTasks] = useState<AnalysisTask[]>([]);
  const [activeTask, setActiveTask] = useState<AnalysisTaskDetail | null>(null);
  // V2.0: 合规审查
  const [complianceAnalysis, setComplianceAnalysis] = useState<ComplianceAnalysis | null>(null);
  const [loadingCompliance, setLoadingCompliance] = useState(false);
  const [loadingProject, setLoadingProject] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsingDocId, setParsingDocId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── 数据加载 ──

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const p = await projectApi.get(projectId);
      setProject(p);
    } catch (err: any) {
      message.error(err.message || '加载项目失败');
    } finally {
      setLoadingProject(false);
    }
  }, [projectId]);

  const loadDocuments = useCallback(async () => {
    if (!projectId) return;
    setLoadingDocs(true);
    try {
      const result = await documentApi.list(projectId);
      setDocuments(result.items || []);
    } catch { /* ignore */ } finally {
      setLoadingDocs(false);
    }
  }, [projectId]);

  const loadTasks = useCallback(async () => {
    if (!projectId) return;
    setLoadingTasks(true);
    try {
      const result = await analysisApi.list({ project_id: projectId });
      setTasks(result.items || []);
      if (result.items && result.items.length > 0) {
        const latest = result.items[0];
        if (latest.status === 'completed' || latest.status === 'failed') {
          loadActiveTask(latest.id);
        }
      }
    } catch { /* ignore */ } finally {
      setLoadingTasks(false);
    }
  }, [projectId]);

  const loadActiveTask = useCallback(async (taskId?: string) => {
    if (!taskId) {
      if (tasks.length > 0) taskId = tasks[0].id;
      else return;
    }
    try {
      const detail = await analysisApi.getDetail(taskId);
      setActiveTask(detail);
    } catch { /* ignore */ }
  }, [tasks]);

  useEffect(() => {
    loadProject();
    loadDocuments();
    loadTasks();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId]);

  // ── 文档上传 ──

  const handleUpload = async (file: File) => {
    if (!projectId) return;
    setUploading(true);
    try {
      await documentApi.upload(projectId, file);
      message.success(`文件 "${file.name}" 上传成功`);
      loadDocuments();
    } catch (err: any) {
      message.error(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  // ── 触发文档解析 ──

  const handleParse = async (docId: string) => {
    if (!projectId) return;
    setParsingDocId(docId);
    try {
      await documentApi.triggerParse(projectId, docId);
      message.success('解析任务已提交');
      const poll = setInterval(async () => {
        try {
          const doc = await documentApi.getParseStatus(projectId, docId);
          if (doc.parse_status === 'completed' || doc.parse_status === 'failed') {
            clearInterval(poll);
            setParsingDocId(null);
            loadDocuments();
            if (doc.parse_status === 'completed') message.success('文档解析完成');
          }
        } catch { clearInterval(poll); setParsingDocId(null); }
      }, 2000);
    } catch (err: any) {
      message.error(err.message || '触发解析失败');
      setParsingDocId(null);
    }
  };

  // ── 启动分析 ──

  const startAnalysis = async () => {
    if (!projectId) return;
    setAnalyzing(true);
    try {
      const task = await analysisApi.create({
        project_id: projectId,
        task_type: 'full_analysis',
      });
      message.success('分析任务已启动');
      loadTasks();

      if (pollRef.current) clearInterval(pollRef.current);

      // 轮询重试计数 + 最大轮询时长保护（30 分钟）
      let retryCount = 0;
      const MAX_RETRIES = 5;
      const pollStart = Date.now();
      const MAX_POLL_MS = 30 * 60 * 1000;

      pollRef.current = setInterval(async () => {
        // 客户端超时保护：防止服务端卡住时前端计时器永远运行
        if (Date.now() - pollStart > MAX_POLL_MS) {
          if (pollRef.current) clearInterval(pollRef.current);
          setAnalyzing(false);
          message.error('分析超时（超过30分钟），请检查后端日志或减少文件数量后重试');
          return;
        }
        try {
          // 使用轻量进度接口轮询
          const progress = await analysisApi.getProgress(task.id);
          setActiveTask(progress as AnalysisTaskDetail);
          retryCount = 0; // 成功后重置重试计数

          if (progress.status === 'completed' || progress.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            setAnalyzing(false);
            // 任务结束后加载完整详情（含结果列表）
            try {
              const detail = await analysisApi.getDetail(task.id);
              setActiveTask(detail);
            } catch { /* 结果加载失败不影响进度展示 */ }
            loadTasks();
            loadProject();
            if (progress.status === 'completed') message.success('分析完成');
            else message.error(`分析失败: ${progress.error_message || '未知错误'}`);
          }
        } catch {
          retryCount++;
          if (retryCount >= MAX_RETRIES) {
            if (pollRef.current) clearInterval(pollRef.current);
            setAnalyzing(false);
            message.warning('进度轮询中断（网络异常），请手动刷新查看状态');
          }
        }
      }, 1500);
    } catch (err: any) {
      message.error(err.message || '启动分析失败');
      setAnalyzing(false);
    }
  };

  // ── 文档解析状态 Tag ──

  const renderParseStatus = (status: string | null | undefined) => {
    const s = status || 'uploaded';
    const config: Record<string, { color: string; text: string }> = {
      uploaded: { color: 'default', text: '未解析' },
      parsing: { color: 'processing', text: '解析中' },
      completed: { color: 'success', text: '已解析' },
      failed: { color: 'error', text: '解析失败' },
    };
    const cfg = config[s] || { color: 'default', text: s };
    return <Tag color={cfg.color} className={styles.parseTag}>{cfg.text}</Tag>;
  };

  // ── 加载状态 ──

  if (loadingProject) {
    return <div className={styles.emptyState}><Spin size="large" /></div>;
  }

  if (!project) {
    return (
      <div className={styles.emptyState}>
        <Empty description="项目不存在" />
        <Button type="primary" onClick={() => navigate('/projects')}>返回项目列表</Button>
      </div>
    );
  }

  // ── 解析6维度评分 ──
  // 优先使用后端已解析的 dimension_scores 字段，兼容旧版从 error_message 解析
  let textScore = 0;
  let structureScore = 0;
  let imageScore = 0;
  let tableScore = 0;
  let errorScore = 0;
  let metadataScore = 0;
  try {
    const dims = activeTask?.dimension_scores;
    if (dims && typeof dims === 'object') {
      textScore = dims.text_score || 0;
      structureScore = dims.structure_score || 0;
      imageScore = dims.image_score || 0;
      tableScore = dims.table_score || 0;
      errorScore = dims.error_score || 0;
      metadataScore = dims.metadata_score || 0;
    } else if (activeTask?.error_message) {
      const dim = JSON.parse(activeTask.error_message);
      textScore = dim.text_score || 0;
      structureScore = dim.structure_score || 0;
      imageScore = dim.image_score || 0;
      tableScore = dim.table_score || 0;
      errorScore = dim.error_score || 0;
      metadataScore = dim.metadata_score || 0;
    }
  } catch { /* ignore */ }

  // ── V2.0: 合规审查 ──

  const pollCompliance = (analysisId: string) => {
    const timer = setInterval(async () => {
      try {
        const result = await complianceApi.getResult(analysisId);
        setComplianceAnalysis(result);
        if (result.status === 'completed' || result.status === 'failed') {
          clearInterval(timer);
          setLoadingCompliance(false);
        }
      } catch {
        clearInterval(timer);
        setLoadingCompliance(false);
      }
    }, 2000);
  };

  const startComplianceAnalysis = async () => {
    if (!projectId) return;
    const parsedDocs = documents.filter(d => d.parse_status === 'completed');
    if (parsedDocs.length === 0) {
      message.warning('请先上传并解析招标文件');
      return;
    }
    setLoadingCompliance(true);
    try {
      const result = await complianceApi.start(projectId, parsedDocs[0].id);
      setComplianceAnalysis(result);
      pollCompliance(result.id);
    } catch {
      message.error('启动合规审查失败');
      setLoadingCompliance(false);
    }
  };

  // ── Tab 配置 ──

  const tabItems = [
    {
      key: 'documents',
      label: <span><FileTextOutlined /> 文档管理</span>,
      children: (
        <div>
          <div className={styles.uploadSection}>
            <Upload.Dragger
              accept=".pdf,.docx,.doc"
              multiple
              showUploadList={false}
              beforeUpload={(file) => { handleUpload(file); return false; }}
              disabled={uploading}
            >
              <p className="ant-upload-drag-icon"><UploadOutlined /></p>
              <p className="ant-upload-text">{uploading ? '上传中...' : '点击或拖拽文件到此区域上传'}</p>
              <p className="ant-upload-hint">支持 PDF、DOCX、DOC 格式，单文件最大 100MB</p>
            </Upload.Dragger>
          </div>
          <Card title={`已上传文档 (${documents.length})`} bodyStyle={{ padding: 0 }}>
            <Table
              dataSource={documents}
              rowKey="id"
              loading={loadingDocs}
              pagination={false}
              size="small"
              columns={[
                { title: '文件名', dataIndex: 'filename', key: 'filename' },
                {
                  title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100,
                  render: (size: number) => {
                    if (!size) return '-';
                    if (size < 1024) return `${size} B`;
                    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
                    return <span className={styles.fileSize}>{(size / 1024 / 1024).toFixed(1)} MB</span>;
                  },
                },
                {
                  title: '解析状态', dataIndex: 'parse_status', key: 'parse_status', width: 100,
                  render: (v: string | null) => renderParseStatus(v),
                },
                {
                  title: '操作', key: 'actions', width: 100, align: 'center',
                  render: (_: any, record: BidDocument) => {
                    const status = record.parse_status || 'uploaded';
                    const isParsing = status === 'parsing';
                    const isCompleted = status === 'completed';
                    const isLoading = parsingDocId === record.id;
                    return (
                      <Button
                        type="link" size="small"
                        icon={isLoading ? <LoadingOutlined /> : undefined}
                        disabled={isParsing || isCompleted || isLoading}
                        loading={isLoading}
                        onClick={() => handleParse(record.id)}
                      >
                        {isCompleted ? '已解析' : isLoading ? '解析中' : '解析'}
                      </Button>
                    );
                  },
                },
              ]}
            />
          </Card>
        </div>
      ),
    },
    {
      key: 'overview',
      label: <span><BarChartOutlined /> 分析总览</span>,
      children: (
        <div>
          <div className={styles.progressSection}>
            <Space>
              <Button
                type="primary" size="large" icon={<PlayCircleOutlined />}
                onClick={startAnalysis} loading={analyzing}
                className={styles.analyzeButton}
              >
                {analyzing ? '分析中...' : '启动全面分析'}
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => { loadTasks(); loadProject(); }}>刷新</Button>
            </Space>
            {(analyzing || activeTask?.status === 'completed' || activeTask?.status === 'failed') && (
              <Card size="small" style={{ marginTop: 16 }}>
                <AnalysisProgressPanel
                  activeTask={activeTask}
                  analyzing={analyzing}
                  onStartAnalysis={startAnalysis}
                />
              </Card>
            )}
          </div>

          <div className={styles.overviewGrid}>
            <RiskOverviewCard
              riskScore={activeTask?.risk_score !== null && activeTask?.risk_score !== undefined
                ? activeTask.risk_score : undefined}
              riskLevel={activeTask?.risk_level}
              loading={loadingTasks}
            />
            <Card title="各维度评分（满分100分）">
              {loadingTasks ? <Spin /> : (
                <Descriptions column={1} size="small" colon={false}>
                  <Descriptions.Item label="📝 文本相似度 (30分)">
                    <Text strong style={{ color: textScore >= 0.8 ? '#f5222d' : textScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(textScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="📑 目录结构相似 (15分)">
                    <Text strong style={{ color: structureScore >= 0.8 ? '#f5222d' : structureScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(structureScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="🖼️ 图片相似度 (15分)">
                    <Text strong style={{ color: imageScore >= 0.8 ? '#f5222d' : imageScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(imageScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="📊 表格相似度 (10分)">
                    <Text strong style={{ color: tableScore >= 0.8 ? '#f5222d' : tableScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(tableScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="✏️ 错别字一致性 (20分)">
                    <Text strong style={{ color: errorScore >= 0.8 ? '#f5222d' : errorScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(errorScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="📋 元数据一致性 (10分)">
                    <Text strong style={{ color: metadataScore >= 0.8 ? '#f5222d' : metadataScore >= 0.5 ? '#fa541c' : '#52c41a' }}>
                      {(metadataScore * 100).toFixed(1)}分
                    </Text>
                  </Descriptions.Item>
                </Descriptions>
              )}
            </Card>
          </div>

          <Card title="分析任务历史" style={{ marginTop: 16 }} bodyStyle={{ padding: 0 }}>
            <List
              dataSource={tasks}
              loading={loadingTasks}
              renderItem={(task) => (
                <List.Item key={task.id} onClick={() => loadActiveTask(task.id)} style={{ cursor: 'pointer', padding: '12px 24px' }}>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag>{task.task_type === 'full_analysis' ? '全面分析' : task.task_type}</Tag>
                        <Tag color={task.status === 'completed' ? 'success' : task.status === 'failed' ? 'error' : task.status === 'analyzing' ? 'processing' : 'default'}>
                          {task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : task.status === 'analyzing' ? '分析中' : '待处理'}
                        </Tag>
                      </Space>
                    }
                    description={
                      <Text type="secondary">
                        进度: {task.progress}% |
                        {task.risk_level && ` 风险: ${RISK_LEVEL_LABELS[task.risk_level] || task.risk_level}`}
                        {task.completed_at && ` | ${new Date(task.completed_at).toLocaleString('zh-CN')}`}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      ),
    },
    {
      key: 'similarity',
      label: <span><FileTextOutlined /> 文本相似度</span>,
      children: (
        <SimilarityTable
          results={activeTask?.similarity_results || []}
          loading={loadingTasks}
        />
      ),
    },
    {
      key: 'images',
      label: <span><PictureOutlined /> 图片相似</span>,
      children: (
        <ImageGallery
          images={activeTask?.image_similarity_results || []}
          loading={loadingTasks}
        />
      ),
    },
    {
      key: 'errors',
      label: <span><AlertOutlined /> 错误检测</span>,
      children: (
        <Card title="错别字与一致性问题" bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={activeTask?.error_detection_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            size="small"
            columns={[
              {
                title: '类型', dataIndex: 'error_type', key: 'error_type', width: 100,
                render: (type: string) => {
                  const colorMap: Record<string, string> = { typo: 'red', term: 'orange', number: 'purple', format: 'blue' };
                  const labelMap: Record<string, string> = { typo: '错别字', term: '术语', number: '数字', format: '格式' };
                  return <Tag color={colorMap[type] || 'default'}>{labelMap[type] || type}</Tag>;
                },
              },
              {
                title: '原始文本', dataIndex: 'original_text', key: 'original_text', ellipsis: true,
                render: (text: string) => (
                  <Tooltip title={text}>
                    <Text delete style={{ color: '#ff4d4f' }}>
                      {text.length > 60 ? `${text.slice(0, 60)}...` : text}
                    </Text>
                  </Tooltip>
                ),
              },
              {
                title: '建议修正', dataIndex: 'corrected_text', key: 'corrected_text', ellipsis: true,
                render: (text: string | null) =>
                  text ? <Text style={{ color: '#52c41a' }}>{text.length > 60 ? `${text.slice(0, 60)}...` : text}</Text> : '-',
              },
              {
                title: '跨文档', dataIndex: 'is_shared', key: 'is_shared', width: 80, align: 'center',
                render: (shared: boolean | null) => shared ? <Tag color="volcano">共享</Tag> : null,
              },
            ]}
          />
        </Card>
      ),
    },
    {
      key: 'structure',
      label: <span><MenuOutlined /> 目录结构</span>,
      children: (
        <Card title="目录结构相似度分析" bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={activeTask?.similarity_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={false}
            size="small"
            columns={[
              {
                title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '目录结构相似度', dataIndex: 'structure_similarity', key: 'structure_similarity', width: 180,
                render: (val: number | null) => {
                  if (val === null || val === undefined) return <Tag>未分析</Tag>;
                  const score = Number(val);
                  const color = score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';
                  return (
                    <Progress percent={score} size="small" strokeColor={color}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 150 }} />
                  );
                },
              },
              {
                title: '全文相似度', dataIndex: 'full_text_similarity', key: 'full_text_similarity', width: 120,
                render: (val: number | null) => val !== null ? `${Number(val).toFixed(1)}%` : '-',
              },
              {
                title: '说明', key: 'note',
                render: (_: any, record: any) => {
                  const s = record.structure_similarity;
                  if (s === null || s === undefined) return <Text type="secondary">需重新分析</Text>;
                  const n = Number(s);
                  if (n >= 80) return <Tag color="red">高度雷同</Tag>;
                  if (n >= 50) return <Tag color="orange">部分相似</Tag>;
                  if (n >= 30) return <Tag color="yellow">略有相似</Tag>;
                  return <Tag color="green">差异较大</Tag>;
                },
              },
            ]}
          />
          <div style={{ padding: 16, background: '#fafafa' }}>
            <Text type="secondary">
              💡 目录结构相似度通过提取文档中的章节标题序列（如"第X章"、"X.X"编号），
              使用最长公共子序列(LCS)算法比对标题文本和层级结构的匹配程度。
              高相似度可能表明使用了相同的投标模板。
            </Text>
          </div>
        </Card>
      ),
    },
    {
      key: 'tables',
      label: <span><TableOutlined /> 表格相似</span>,
      children: (
        <Card title="表格相似度分析" bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={activeTask?.similarity_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={false}
            size="small"
            columns={[
              {
                title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '表格相似度', dataIndex: 'table_similarity', key: 'table_similarity', width: 180,
                render: (val: number | null) => {
                  if (val === null || val === undefined) return <Tag>未分析</Tag>;
                  const score = Number(val);
                  const color = score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';
                  return (
                    <Progress percent={score} size="small" strokeColor={color}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 150 }} />
                  );
                },
              },
              {
                title: '全文相似度', dataIndex: 'full_text_similarity', key: 'full_text_similarity', width: 120,
                render: (val: number | null) => val !== null ? `${Number(val).toFixed(1)}%` : '-',
              },
              {
                title: '说明', key: 'note',
                render: (_: any, record: any) => {
                  const s = record.table_similarity;
                  if (s === null || s === undefined) return <Text type="secondary">需重新分析</Text>;
                  const n = Number(s);
                  if (n >= 80) return <Tag color="red">表格高度一致</Tag>;
                  if (n >= 50) return <Tag color="orange">部分表格相似</Tag>;
                  if (n >= 30) return <Tag color="yellow">略有相似</Tag>;
                  return <Tag color="green">表格差异较大</Tag>;
                },
              },
            ]}
          />
          <div style={{ padding: 16, background: '#fafafa' }}>
            <Text type="secondary">
              💡 表格相似度分析比对文档中的表格结构（表头、行列数）和单元格内容。
              综合计算表头Jaccard相似度(40%)、行列结构匹配(20%)和单元格内容重叠(40%)。
              需要在文档解析后才能获取表格数据。
            </Text>
          </div>
        </Card>
      ),
    },
    {
      key: 'metadata',
      label: <span><DatabaseOutlined /> 元数据一致性</span>,
      children: (
        <Card title="元数据一致性分析" bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={activeTask?.similarity_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={false}
            size="small"
            columns={[
              {
                title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '元数据一致性', dataIndex: 'metadata_consistency', key: 'metadata_consistency', width: 180,
                render: (val: number | null) => {
                  if (val === null || val === undefined) return <Tag>未分析</Tag>;
                  const score = Number(val);
                  const color = score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';
                  return (
                    <Progress percent={score} size="small" strokeColor={color}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 150 }} />
                  );
                },
              },
              {
                title: '全文相似度', dataIndex: 'full_text_similarity', key: 'full_text_similarity', width: 120,
                render: (val: number | null) => val !== null ? `${Number(val).toFixed(1)}%` : '-',
              },
              {
                title: '匹配字段', key: 'matched_fields', width: 180,
                render: (_: any, record: any) => {
                  const meta = record.details?.metadata_comparison;
                  if (!meta || !meta.matched_fields) return <Text type="secondary">需重新分析</Text>;
                  const fields = meta.matched_fields as string[];
                  if (fields.length === 0) return <Tag color="green">无匹配</Tag>;
                  const labels: Record<string, string> = {
                    author: '作者', creator: '创建者', producer: '软件',
                    title: '标题', company: '公司', last_modified_by: '修改者',
                  };
                  return (
                    <Space size={4} wrap>
                      {fields.map(f => (
                        <Tag key={f} color="red">{labels[f] || f}</Tag>
                      ))}
                    </Space>
                  );
                },
              },
              {
                title: '说明', key: 'note', width: 100,
                render: (_: any, record: any) => {
                  const s = record.metadata_consistency;
                  if (s === null || s === undefined) return <Text type="secondary">需重新分析</Text>;
                  const n = Number(s);
                  if (n >= 50) return <Tag color="red">⚠ 元数据异常一致</Tag>;
                  if (n >= 30) return <Tag color="orange">部分字段相同</Tag>;
                  return <Tag color="green">元数据正常</Tag>;
                },
              },
            ]}
          />
          <div style={{ padding: 16, background: '#fafafa' }}>
            <Text type="secondary">
              💡 元数据一致性分析比对文档的文件属性（作者、创建者、生成软件、公司、标题、修改者）。
              如果不同企业的标书具有相同的作者或创建软件，可能是围标串标的重要线索。
            </Text>
          </div>
        </Card>
      ),
    },
    // ── V1.1：模板复用 Tab ──
    {
      key: 'template-reuse',
      label: <span><ToolOutlined /> 模板复用</span>,
      children: (
        <Card title="模板复用分析" bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={activeTask?.template_reuse_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={false}
            size="small"
            locale={{ emptyText: <Empty description="暂无模板复用数据（需使用 DOCX/PDF 文件触发分析）" /> }}
            columns={[
              {
                title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '模板复用度', dataIndex: 'reuse_score', key: 'reuse_score', width: 180,
                render: (val: number | null) => {
                  if (val === null || val === undefined) return <Tag>未分析</Tag>;
                  const score = Number(val);
                  const color = score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';
                  return (
                    <Progress percent={score} size="small" strokeColor={color}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 150 }} />
                  );
                },
              },
              {
                title: '样式匹配', dataIndex: 'style_match_score', key: 'style_match', width: 100,
                render: (v: number | null) => v !== null ? `${Number(v).toFixed(1)}%` : '-',
              },
              {
                title: '布局匹配', dataIndex: 'layout_match_score', key: 'layout_match', width: 100,
                render: (v: number | null) => v !== null ? `${Number(v).toFixed(1)}%` : '-',
              },
              {
                title: '标题匹配', dataIndex: 'heading_match_score', key: 'heading_match', width: 100,
                render: (v: number | null) => v !== null ? `${Number(v).toFixed(1)}%` : '-',
              },
              {
                title: '说明', key: 'note', width: 120,
                render: (_: any, record: any) => {
                  const s = record.reuse_score;
                  if (s === null || s === undefined) return <Text type="secondary">需重新分析</Text>;
                  const n = Number(s);
                  if (n >= 80) return <Tag color="red">⚠ 高度复用</Tag>;
                  if (n >= 50) return <Tag color="orange">疑似复用</Tag>;
                  return <Tag color="green">模板独立</Tag>;
                },
              },
            ]}
          />
          <div style={{ padding: 16, background: '#fafafa' }}>
            <Text type="secondary">
              💡 模板复用分析检测不同标书的文档模板相似度（字体样式、页边距布局、标题结构、分节方式）。
              高度复用意味着多家投标人可能使用了相同的文档模板或由同一人制作标书。
            </Text>
          </div>
        </Card>
      ),
    },
    // ── V1.1：电子签名 Tab ──
    {
      key: 'electronic-signatures',
      label: <span><SafetyOutlined /> 电子签名</span>,
      children: (
        <Card title="电子标书特征检测" bodyStyle={{ padding: 0 }}>
          <div style={{ padding: '12px 16px', background: '#fff2f0', borderBottom: '1px solid #ffccc7' }}>
            <Text style={{ color: '#cf1322' }}>
              🛡️ 电子签名证据为 <Text strong>L1 级直接证据</Text>（可直接认定围串标）。
              匹配项（✓）越多，围串标嫌疑越大。
            </Text>
          </div>
          <Table
            dataSource={activeTask?.electronic_signature_results || []}
            rowKey="id"
            loading={loadingTasks}
            pagination={false}
            size="small"
            locale={{ emptyText: <Empty description="暂无电子签名数据（需在文档上传时捕获IP，且文档需含元数据）" /> }}
            columns={[
              {
                title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
                render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
              },
              {
                title: '综合得分', dataIndex: 'signature_score', key: 'signature_score', width: 150,
                render: (val: number | null) => {
                  if (val === null || val === undefined) return <Tag>未分析</Tag>;
                  const score = Number(val);
                  const color = score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';
                  return (
                    <Progress percent={score} size="small" strokeColor={color}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 120 }} />
                  );
                },
              },
              {
                title: 'MAC', dataIndex: 'mac_match', key: 'mac', width: 60,
                render: (v: boolean | null) => {
                  if (v === null) return <Tag>?</Tag>;
                  return v ? <Tag color="red">✓</Tag> : <Tag color="green">✗</Tag>;
                },
              },
              {
                title: 'IP', dataIndex: 'ip_match', key: 'ip', width: 60,
                render: (v: boolean | null) => {
                  if (v === null) return <Tag>?</Tag>;
                  return v ? <Tag color="red">✓</Tag> : <Tag color="green">✗</Tag>;
                },
              },
              {
                title: '创建者', dataIndex: 'creator_match', key: 'creator', width: 70,
                render: (v: boolean | null) => {
                  if (v === null) return <Tag>?</Tag>;
                  return v ? <Tag color="red">✓</Tag> : <Tag color="green">✗</Tag>;
                },
              },
              {
                title: '软件', dataIndex: 'software_match', key: 'software', width: 60,
                render: (v: boolean | null) => {
                  if (v === null) return <Tag>?</Tag>;
                  return v ? <Tag color="red">✓</Tag> : <Tag color="green">✗</Tag>;
                },
              },
              {
                title: '匹配项', key: 'matched', width: 120,
                render: (_: any, record: any) => {
                  const items: string[] = [];
                  if (record.mac_match) items.push('MAC');
                  if (record.ip_match) items.push('IP');
                  if (record.creator_match) items.push('创建者');
                  if (record.software_match) items.push('软件');
                  if (items.length === 0) return <Text type="secondary">无匹配</Text>;
                  return <Space size={4}>{items.map(i => <Tag key={i} color="red">{i}</Tag>)}</Space>;
                },
              },
            ]}
          />
          <div style={{ padding: 16, background: '#fafafa' }}>
            <Text type="secondary">
              💡 电子标书特征检测比对MAC地址（同一台电脑制作）、上传IP（同一网络）、文件创建者（同一人编辑）、编辑软件。
              MAC或IP匹配属于L1级直接证据，可直接认定围标嫌疑。
            </Text>
          </div>
        </Card>
      ),
    },
    // ── V2.0：合规审查 Tab ──
    {
      key: 'compliance',
      label: <span><SafetyOutlined /> 合规审查</span>,
      children: (
        <CompliancePanel
          analysis={complianceAnalysis}
          loading={loadingCompliance}
          onStart={startComplianceAnalysis}
        />
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <Breadcrumb items={[
        { title: <a onClick={() => navigate('/projects')}><HomeOutlined /> 项目列表</a> },
        { title: project.name },
      ]} style={{ marginBottom: 16 }} />

      <div className={styles.headerSection}>
        <Space align="center" size="large">
          <Title level={4} style={{ margin: 0 }}>{project.name}</Title>
          {project.risk_level && (
            <Tag color={RISK_LEVEL_COLORS[project.risk_level] || '#999'}>
              {RISK_LEVEL_LABELS[project.risk_level] || project.risk_level}
            </Tag>
          )}
          <Text type="secondary">
            {documents.length} 个文档 | 创建于 {new Date(project.created_at).toLocaleDateString('zh-CN')}
          </Text>
        </Space>
        {project.description && <div style={{ marginTop: 8 }}><Text type="secondary">{project.description}</Text></div>}
      </div>

      <div style={{ marginBottom: 16 }}>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => navigate(`/projects/${projectId}/report`)}
          disabled={!activeTask || activeTask.status !== 'completed'}
        >查看分析报告</Button>
      </div>

      <Card className={styles.tabsCard}>
        <Tabs defaultActiveKey="documents" items={tabItems} />
      </Card>
    </div>
  );
};

export default ProjectDetail;
