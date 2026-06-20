/**
 * 风险报告预览页面
 * 展示6维度分析报告详情。
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Typography, Breadcrumb, Button, Spin, Descriptions, Tag, Table, message, Space, Progress } from 'antd';
import { HomeOutlined, DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { projectApi, analysisApi } from '../../services/api';
import type { Project, AnalysisTask, AnalysisTaskDetail } from '../../types';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '../../types';

const { Title, Text } = Typography;

/** 安全转数字 */
const toNum = (v: any): number => {
  if (v === null || v === undefined) return 0;
  const n = Number(v);
  return isNaN(n) ? 0 : n;
};

/** 安全格式化百分比 */
const fmtPct = (v: any): string => {
  const n = toNum(v);
  return n > 0 ? `${n.toFixed(1)}%` : '-';
};

/** 分数颜色 */
const scoreColor = (score: number) =>
  score >= 80 ? '#f5222d' : score >= 50 ? '#fa541c' : score >= 30 ? '#faad14' : '#52c41a';

const ReportView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [taskDetail, setTaskDetail] = useState<AnalysisTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const p = await projectApi.get(projectId);
      setProject(p);
      const tasks = await analysisApi.list({ project_id: projectId });
      const completedTask = tasks.items?.find(t => t.status === 'completed');
      if (completedTask) {
        const detail = await analysisApi.getDetail(completedTask.id);
        setTaskDetail(detail);
      }
    } catch (err: any) {
      message.error(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, []);

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (!project) {
    return <Card>项目不存在</Card>;
  }

  const riskScore = toNum(taskDetail?.risk_score);
  const riskLevel = taskDetail?.risk_level || 'LOW';

  // 解析6维度评分
  const dims = taskDetail?.dimension_scores;
  const textScore = dims?.text_score || 0;
  const structureScore = dims?.structure_score || 0;
  const imageScore = dims?.image_score || 0;
  const tableScore = dims?.table_score || 0;
  const errorScore = dims?.error_score || 0;
  const metadataScore = dims?.metadata_score || 0;

  const errorCols = [
    {
      title: '类型', dataIndex: 'error_type', key: 'error_type', width: 80,
      render: (type: string) => {
        const colorMap: Record<string, string> = { typo: 'red', term: 'orange', number: 'purple', format: 'blue' };
        const labelMap: Record<string, string> = { typo: '错别字', term: '术语', number: '数字', format: '格式' };
        return <Tag color={colorMap[type] || 'default'}>{labelMap[type] || type}</Tag>;
      },
    },
    {
      title: '原始文本', dataIndex: 'original_text', key: 'original_text', ellipsis: true,
      render: (text: string) => text ? (
        <Text delete style={{ color: '#ff4d4f' }}>
          {text.length > 60 ? `${text.slice(0, 60)}...` : text}
        </Text>
      ) : '-',
    },
    {
      title: '建议修正', dataIndex: 'corrected_text', key: 'corrected_text', ellipsis: true,
      render: (text: string | null) =>
        text ? <Text style={{ color: '#52c41a' }}>{text.length > 60 ? `${text.slice(0, 60)}...` : text}</Text> : '-',
    },
    {
      title: '跨文档', dataIndex: 'is_shared', key: 'is_shared', width: 80, align: 'center' as const,
      render: (shared: boolean | null) => shared ? <Tag color="volcano">共享</Tag> : null,
    },
  ];

  return (
    <div>
      <Breadcrumb items={[
        { title: <><HomeOutlined /> 首页</> },
        { title: <a onClick={() => navigate('/projects')}>项目列表</a> },
        { title: '分析报告' },
      ]} style={{ marginBottom: 16 }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/projects/${projectId}`)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{project.name} - 分析报告</Title>
        </Space>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={() => {
            if (taskDetail) {
              window.open(`${window.location.origin}/api/v1/projects/${projectId}/reports?task_id=${taskDetail.id}&format=pdf`, '_blank');
            }
          }}>下载 PDF</Button>
          <Button icon={<DownloadOutlined />} onClick={() => {
            if (taskDetail) {
              window.open(`${window.location.origin}/api/v1/projects/${projectId}/reports?task_id=${taskDetail.id}&format=word`, '_blank');
            }
          }}>下载 Word</Button>
        </Space>
      </div>

      {/* 项目基本信息 */}
      <Card title="一、项目基本信息" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="项目名称">{project.name}</Descriptions.Item>
          <Descriptions.Item label="标书数量">{project.file_count}</Descriptions.Item>
          <Descriptions.Item label="风险等级">
            <Tag color={RISK_LEVEL_COLORS[riskLevel]}>{RISK_LEVEL_LABELS[riskLevel]}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="综合评分">{riskScore.toFixed(1)}分</Descriptions.Item>
          <Descriptions.Item label="分析时间" span={2}>
            {taskDetail?.completed_at ? new Date(taskDetail.completed_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 6维度评分总览 */}
      <Card title="二、各维度评分总览" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small" colon={false}>
          <Descriptions.Item label="📝 文本相似度 (30分)">
            <Text strong style={{ color: scoreColor(textScore * 100) }}>
              {(textScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="📑 目录结构相似 (15分)">
            <Text strong style={{ color: scoreColor(structureScore * 100) }}>
              {(structureScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="🖼️ 图片相似度 (15分)">
            <Text strong style={{ color: scoreColor(imageScore * 100) }}>
              {(imageScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="📊 表格相似度 (10分)">
            <Text strong style={{ color: scoreColor(tableScore * 100) }}>
              {(tableScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="✏️ 错别字一致性 (20分)">
            <Text strong style={{ color: scoreColor(errorScore * 100) }}>
              {(errorScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="📋 元数据一致性 (10分)">
            <Text strong style={{ color: scoreColor(metadataScore * 100) }}>
              {(metadataScore * 100).toFixed(1)}分
            </Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 文本与结构相似度明细 */}
      {taskDetail?.similarity_results && taskDetail.similarity_results.length > 0 && (
        <Card title="三、文档相似度明细" style={{ marginBottom: 16 }}>
          <Table
            dataSource={taskDetail.similarity_results}
            rowKey="id"
            columns={[
              {
                title: '文档对', key: 'pair',
                render: (_: any, r: any) => (
                  <Text code>{String(r.doc1_id || '').slice(0, 8)} ↔ {String(r.doc2_id || '').slice(0, 8)}</Text>
                ),
              },
              {
                title: '全文相似度', dataIndex: 'full_text_similarity', key: 'full_text',
                render: (v: any) => {
                  const n = toNum(v);
                  return n > 0 ? (
                    <Progress percent={n} size="small" strokeColor={scoreColor(n)}
                      format={p => `${Number(p ?? 0).toFixed(1)}%`} style={{ width: 120 }} />
                  ) : '-';
                },
              },
              {
                title: '目录结构', dataIndex: 'structure_similarity', key: 'structure',
                render: (v: any) => fmtPct(v),
              },
              {
                title: '表格相似', dataIndex: 'table_similarity', key: 'table',
                render: (v: any) => fmtPct(v),
              },
              {
                title: '元数据一致性', dataIndex: 'metadata_consistency', key: 'metadata',
                render: (v: any) => {
                  const n = toNum(v);
                  if (n <= 0) return '-';
                  const meta = (r: any) => r.details?.metadata_comparison;
                  return (
                    <span>
                      <Text style={{ color: n >= 50 ? '#f5222d' : '#52c41a' }}>{n.toFixed(1)}%</Text>
                    </span>
                  );
                },
              },
            ]}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {/* 图片相似 */}
      {taskDetail?.image_similarity_results && taskDetail.image_similarity_results.length > 0 && (
        <Card title="四、图片相似分析" style={{ marginBottom: 16 }}>
          {taskDetail.image_similarity_results.map(img => (
            <div key={img.id} style={{ marginBottom: 8 }}>
              <Text strong>图片相似度: </Text>
              <Text style={{ color: '#fa541c' }}>{toNum(img.similarity_score).toFixed(1)}%</Text>
              <Text type="secondary"> (算法: {img.hash_algorithm})</Text>
            </div>
          ))}
        </Card>
      )}

      {/* 错误检测 */}
      {taskDetail?.error_detection_results && taskDetail.error_detection_results.length > 0 && (
        <Card title="五、错误检测结果">
          <Table
            dataSource={taskDetail.error_detection_results}
            rowKey="id"
            columns={errorCols}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {!taskDetail && (
        <Card>
          <Text type="secondary">暂无分析数据，请先对项目执行全面分析。</Text>
        </Card>
      )}
    </div>
  );
};

export default ReportView;
