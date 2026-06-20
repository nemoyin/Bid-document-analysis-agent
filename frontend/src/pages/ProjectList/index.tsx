/**
 * 任务列表页面
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, Table, Button, Tag, Typography, Breadcrumb, Space, Modal, Input, message, Popconfirm } from 'antd';
import { PlusOutlined, FolderOutlined, HomeOutlined, DeleteOutlined, ExclamationCircleOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../../services/api';
import type { Project } from '../../types';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '../../types';

const { Title } = Typography;

const ProjectList: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const result = await projectApi.list({ page_size: 50 });
      setProjects(result.items || []);
    } catch (err: any) {
      message.error(err.message || '加载任务列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadProjects(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const project = await projectApi.create({ name: newName.trim() });
      message.success('任务创建成功');
      setModalOpen(false);
      setNewName('');
      navigate(`/projects/${project.id}`);
    } catch (err: any) {
      message.error(err.message || '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    try {
      await projectApi.delete(id);
      message.success(`任务 "${name}" 已删除`);
      loadProjects();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  const columns = [
    { title: '任务名称', dataIndex: 'name', key: 'name',
      render: (name: string, record: Project) => (
        <a onClick={() => navigate(`/projects/${record.id}`)}>
          <FolderOutlined style={{ marginRight: 8 }} />{name}
        </a>
      ),
    },
    { title: '标书数量', dataIndex: 'file_count', key: 'file_count', width: 100 },
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
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: any, record: Project) => (
        <Space>
          <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/projects/${record.id}`)}>查看</Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除任务 "${record.name}" 吗？将同时删除所有关联文档和分析结果。`}
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
      <Breadcrumb items={[{ title: <><HomeOutlined /> 首页</> }, { title: '任务列表' }]} style={{ marginBottom: 16 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>任务列表</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建任务</Button>
      </div>
      <Card>
        <Table
          dataSource={projects}
          rowKey="id"
          loading={loading}
          columns={columns}
          pagination={{ pageSize: 20 }}
        />
      </Card>
      <Modal
        title="新建任务"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); setNewName(''); }}
        confirmLoading={creating}
      >
        <Input
          placeholder="输入任务名称"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onPressEnter={handleCreate}
        />
      </Modal>
    </div>
  );
};

export default ProjectList;
