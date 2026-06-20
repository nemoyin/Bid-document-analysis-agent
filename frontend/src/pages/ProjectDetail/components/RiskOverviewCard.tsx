/**
 * 风险评分概览卡片
 */
import React from 'react';
import { Card, Progress, Tag, Typography, Spin } from 'antd';
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '../../../types';

const { Text } = Typography;

interface RiskOverviewCardProps {
  riskScore?: number;
  riskLevel?: string | null;
  loading?: boolean;
}

const RiskOverviewCard: React.FC<RiskOverviewCardProps> = ({ riskScore, riskLevel, loading }) => {
  if (loading) {
    return (
      <Card title="综合风险评分">
        <Spin />
      </Card>
    );
  }

  // riskScore 后端已返回 0-100 的值，直接使用
  const score = riskScore !== undefined && riskScore !== null ? Math.round(riskScore) : 0;
  const level = riskLevel || 'LOW';
  const color = RISK_LEVEL_COLORS[level] || '#999';

  return (
    <Card title="综合风险评分">
      <div style={{ textAlign: 'center', padding: '16px 0' }}>
        <Progress
          type="dashboard"
          percent={score}
          size={160}
          strokeColor={color}
          format={p => `${p}分`}
        />
        <div style={{ marginTop: 12 }}>
          <Tag color={color} style={{ fontSize: 14, padding: '4px 12px' }}>
            {RISK_LEVEL_LABELS[level] || level}
          </Tag>
        </div>
      </div>
    </Card>
  );
};

export default RiskOverviewCard;
