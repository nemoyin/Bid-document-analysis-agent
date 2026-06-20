/**
 * 分析报告列表页面
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, Table, Tag, Typography, Breadcrumb, Button, message, Empty, Space, Popconfirm } from 'antd';
import { FileTextOutlined, HomeOutlined, EyeOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../../services/api';
import type { Project } from '../../types';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '../../types';

const { Title } = Typography;

const ReportList: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const result = await projectApi.list({ page_size: 50 });
      // 只显示有分析结果（有风险等级）的项目
      setProjects((result.items || []).filter(p => p.risk_level));
    } catch (err: any) {
      message.error(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadProjects(); }, []);

  const handleDelete = async (id: string, name: string) => {
    try {
      await projectApi.delete(id);
      message.success(`报告 "${name}" 已删除`);
      loadProjects();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  const columns = [
    { title: '项目名称', dataIndex: 'name', key: 'name' },
    { title: '风险等级', dataIndex: 'risk_level', key: 'risk_level', width: 120,
      render: (level: string | null) =>
        level ? (
          <Tag color={RISK_LEVEL_COLORS[level] || '#999'}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: RISK_LEVEL_COLORS[level] || '#999', marginRight: 4,
            }} />
            {RISK_LEVEL_LABELS[level] || level}
          </Tag>
        ) : '-',
    },
    { title: '平均评分', dataIndex: 'average_score', key: 'average_score', width: 100,
      render: (s: number | string | null) => s !== null && s !== undefined ? `${Number(s).toFixed(1)}分` : '-',
    },
    { title: '标书数', dataIndex: 'file_count', key: 'file_count', width: 80 },
    {
      title: '操作', key: 'actions', width: 200,
      render: (_: any, record: Project) => (
        <Space>
          <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.id}/report`)}>
            查看报告
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除任务 "${record.name}" 吗？将同时删除所有关联数据。`}
            onConfirm={() => handleDelete(record.id, record.name)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Breadcrumb items={[{ title: <><HomeOutlined /> 首页</> }, { title: '分析报告' }]} style={{ marginBottom: 16 }} />
      <Title level={4}><FileTextOutlined /> 分析报告</Title>
      <Card>
        {projects.length > 0 ? (
          <Table dataSource={projects} rowKey="id" loading={loading} columns={columns} pagination={false} />
        ) : (
          !loading && <Empty description="暂无已分析的项目报告" />
        )}
      </Card>
    </div>
  );
};

export default ReportList;
