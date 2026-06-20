/**
 * Dashboard 仪表盘页面
 * 统计数据总览：任务数、报告数、风险分布、趋势图、分析耗时等
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Row, Col, Statistic, Typography, Spin, Table, Tag, message, Breadcrumb } from 'antd';
import {
  FolderOutlined, FileTextOutlined, FilePdfOutlined,
  ThunderboltOutlined, ClockCircleOutlined, CheckCircleOutlined,
  CloseCircleOutlined, BarChartOutlined, HomeOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import * as echarts from 'echarts';

const { Title } = Typography;
const API_BASE = `${window.location.origin}/api/v1`;

interface DashboardStats {
  task_count: number;
  report_count: number;
  document_count: number;
  risk_distribution: Record<string, number>;
  monthly_trend: { month: string; count: number }[];
  analysis_stats: {
    total: number;
    completed: number;
    failed: number;
    avg_duration_seconds: number;
    success_rate: number;
  };
  analysis_monthly_trend: { month: string; count: number }[];
}

const RISK_COLORS: Record<string, string> = {
  LOW: '#52c41a', MODERATE: '#faad14', HIGH: '#fa541c', CRITICAL: '#f5222d', NONE: '#d9d9d9',
};
const RISK_LABELS: Record<string, string> = {
  LOW: '低风险', MODERATE: '中风险', HIGH: '高风险', CRITICAL: '严重风险', NONE: '未分析',
};

/** 轻量 ECharts 包装组件，避免第三方库兼容问题 */
const ChartBox: React.FC<{ option: any; style?: React.CSSProperties }> = ({ option, style }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }
    chartRef.current.setOption(option, true);
  }, [option]);

  useEffect(() => {
    const handleResize = () => chartRef.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chartRef.current?.dispose();
    };
  }, []);

  return <div ref={containerRef} style={{ width: '100%', height: 300, ...style }} />;
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/stats`);
      const json = await res.json();
      if (json.code === 0) {
        setStats(json.data);
      } else {
        message.error(json.message || '加载失败');
      }
    } catch (err: any) {
      message.error(err.message || '加载统计数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, []);

  if (loading || !stats) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  // ── 预计算图表所需数据 ──
  const trendMonths = stats.monthly_trend.map(t => t.month);
  const trendTaskCounts = stats.monthly_trend.map(t => t.count);
  const trendMap: Record<string, number> = {};
  stats.analysis_monthly_trend.forEach(t => { trendMap[t.month] = t.count; });
  const trendAnalysisCounts = stats.monthly_trend.map(t => trendMap[t.month] || 0);
  const pieData = Object.entries(stats.risk_distribution).map(([k, v]) => ({
    name: RISK_LABELS[k] || k,
    value: v,
    itemStyle: { color: RISK_COLORS[k] || '#999' },
  }));

  // ── 图表 option（纯数据对象，无函数） ──
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['新建任务', '分析次数'], bottom: 0 },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category' as const, data: trendMonths, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value' as const, minInterval: 1 },
    series: [
      { name: '新建任务', type: 'bar', data: trendTaskCounts, itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] } },
      { name: '分析次数', type: 'line', smooth: true, data: trendAnalysisCounts, itemStyle: { color: '#fa8c16' }, lineStyle: { width: 2 } },
    ],
  };

  const pieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'], label: { formatter: '{b}\n{d}%' }, data: pieData }],
  };

  const durationLabel = stats.analysis_stats.avg_duration_seconds > 60
    ? `${(stats.analysis_stats.avg_duration_seconds / 60).toFixed(1)} 分钟`
    : `${stats.analysis_stats.avg_duration_seconds} 秒`;

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Breadcrumb items={[{ title: <><HomeOutlined /> 首页</> }, { title: '数据仪表盘' }]} style={{ marginBottom: 16 }} />
      <Title level={4} style={{ marginBottom: 20 }}><BarChartOutlined style={{ marginRight: 8 }} />数据仪表盘</Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {[
          { title: '总任务数', value: stats.task_count, icon: <FolderOutlined />, color: '#1890ff', link: '/projects' },
          { title: '分析报告', value: stats.report_count, icon: <FilePdfOutlined />, color: '#722ed1', link: '/reports' },
          { title: '标书文件', value: stats.document_count, icon: <FileTextOutlined />, color: '#13c2c2' },
          { title: '分析总次数', value: stats.analysis_stats.total, icon: <ThunderboltOutlined />, color: '#fa8c16' },
        ].map((item, i) => (
          <Col xs={12} sm={6} key={i}>
            <Card hoverable={!!item.link} onClick={item.link ? () => navigate(item.link) : undefined}
              style={{ cursor: item.link ? 'pointer' : 'default' }}>
              <Statistic title={item.title} value={item.value} prefix={item.icon} valueStyle={{ color: item.color }} />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={14}>
          <Card title="📈 月度趋势（近6个月）"><ChartBox option={trendOption} /></Card>
        </Col>
        <Col xs={24} md={10}>
          <Card title="🎯 风险等级分布"><ChartBox option={pieOption} /></Card>
        </Col>
      </Row>

      {/* 明细 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={14}>
          <Card title="⚙️ 分析性能统计">
            <Row gutter={[16, 16]}>
              {[
                { label: '总分析次数', value: stats.analysis_stats.total, icon: <ThunderboltOutlined /> },
                { label: '已完成', value: stats.analysis_stats.completed, icon: <CheckCircleOutlined />, color: '#52c41a' },
                { label: '失败', value: stats.analysis_stats.failed, icon: <CloseCircleOutlined />, color: '#f5222d' },
                { label: '成功率', value: `${stats.analysis_stats.success_rate}%`, icon: <BarChartOutlined />, color: '#1890ff' },
                { label: '平均耗时', value: durationLabel, icon: <ClockCircleOutlined /> },
              ].map((item, i) => (
                <Col span={i >= 3 ? 12 : 8} key={i}>
                  <Card size="small" style={{ textAlign: 'center', background: '#fafafa' }}>
                    <div style={{ fontSize: 20, marginBottom: 4, color: item.color || '#666' }}>{item.icon}</div>
                    <div style={{ fontSize: 12, color: '#999' }}>{item.label}</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: item.color || '#333' }}>{item.value}</div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={10}>
          <Card title="📋 风险等级明细">
            <Table dataSource={pieData.map(d => ({ ...d, count: d.value }))} rowKey="name" pagination={false} size="small"
              columns={[
                { title: '等级', dataIndex: 'name', key: 'name', render: (label: string, record: any) => (
                  <Tag color={record.itemStyle?.color}>{label}</Tag>
                )},
                { title: '项目数', dataIndex: 'count', key: 'count', align: 'center' as const },
                { title: '占比', key: 'pct', align: 'center' as const, render: (_: any, record: any) =>
                  `${stats.task_count > 0 ? (record.count / stats.task_count * 100).toFixed(1) : '0'}%`
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
