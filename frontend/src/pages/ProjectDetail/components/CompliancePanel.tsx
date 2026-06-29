import React from 'react';
import { Card, Table, Tag, Progress, Descriptions, Empty, Typography, Button, Space } from 'antd';
import { SafetyOutlined } from '@ant-design/icons';
import type { ComplianceAnalysis } from '@/types';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '@/types';

const { Text } = Typography;

interface Props {
  analysis: ComplianceAnalysis | null;
  loading: boolean;
  onStart: () => void;
}

const CompliancePanel: React.FC<Props> = ({ analysis, loading, onStart }) => {
  if (!analysis) {
    return (
      <Card>
        <Empty description="暂无合规审查数据">
          <Button type="primary" onClick={onStart} loading={loading} icon={<SafetyOutlined />}>
            开始合规审查
          </Button>
        </Empty>
      </Card>
    );
  }

  if (analysis.status === 'pending' || analysis.status === 'analyzing') {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Progress type="circle" percent={analysis.progress} />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">正在审查招标文件合规性...</Text>
          </div>
        </div>
      </Card>
    );
  }

  if (analysis.status === 'failed') {
    return (
      <Card>
        <Empty description={`审查失败: ${analysis.error_message || '未知错误'}`}>
          <Button onClick={onStart} icon={<SafetyOutlined />}>重试</Button>
        </Empty>
      </Card>
    );
  }

  const riskColor = analysis.risk_level ? RISK_LEVEL_COLORS[analysis.risk_level.toUpperCase()] : '#999';
  const riskLabel = analysis.risk_level ? RISK_LEVEL_LABELS[analysis.risk_level.toUpperCase()] : '-';

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={4} size="small" bordered>
          <Descriptions.Item label="合规评分">
            <Progress type="circle" percent={analysis.compliance_score ?? 0} size={60}
              strokeColor={analysis.compliance_score != null && analysis.compliance_score >= 85 ? '#52c41a'
                : analysis.compliance_score != null && analysis.compliance_score >= 60 ? '#faad14'
                : '#f5222d'} />
          </Descriptions.Item>
          <Descriptions.Item label="风险等级">
            <Tag color={riskColor} style={{ fontSize: 16, padding: '4px 12px' }}>{riskLabel}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="审查条款">{analysis.clause_count} 条</Descriptions.Item>
          <Descriptions.Item label="违规条款">
            <Space>
              <Tag color="red">{analysis.clauses?.filter(c => c.risk_level === 'red').length || 0} 严重</Tag>
              <Tag color="gold">{analysis.clauses?.filter(c => c.risk_level === 'yellow').length || 0} 疑似</Tag>
              <Tag color="green">{analysis.clauses?.filter(c => c.risk_level === 'green').length || 0} 合规</Tag>
            </Space>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="条款审查清单" bodyStyle={{ padding: 0 }}>
        <Table
          dataSource={analysis.clauses || []}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, size: 'small' }}
          size="small"
          columns={[
            {
              title: '风险', dataIndex: 'risk_level', key: 'risk', width: 60,
              render: (v: string) => {
                const colors: Record<string, string> = { red: '#f5222d', yellow: '#faad14', green: '#52c41a' };
                const labels: Record<string, string> = { red: '🔴', yellow: '🟡', green: '🟢' };
                return <Tag color={colors[v]}>{labels[v] || v}</Tag>;
              },
            },
            {
              title: '条款原文', dataIndex: 'original_text', key: 'text', ellipsis: true,
            },
            {
              title: '类型', dataIndex: 'clause_type', key: 'type', width: 100,
              render: (v: string) => <Tag>{v}</Tag>,
            },
            {
              title: '命中规则', key: 'rules', width: 200,
              render: (_: any, record: any) => {
                const rules = record.matched_rules || [];
                if (rules.length === 0) return <Tag color="green">合规</Tag>;
                return (
                  <Space size={4} wrap>
                    {rules.map((r: any) => (
                      <Tag key={r.rule_id} color={r.risk === 'red' ? 'red' : 'orange'}>
                        {r.rule_name}
                      </Tag>
                    ))}
                  </Space>
                );
              },
            },
            {
              title: '说明', key: 'reason', width: 150, ellipsis: true,
              render: (_: any, record: any) => {
                const rules = record.matched_rules || [];
                if (rules.length === 0) return '';
                return <Text type="danger" style={{ fontSize: 12 }}>{rules[0]?.reason}</Text>;
              },
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default CompliancePanel;
