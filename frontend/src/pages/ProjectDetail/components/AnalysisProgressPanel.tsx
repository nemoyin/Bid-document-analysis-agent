import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Progress, Card, Badge, Tag, Row, Col } from 'antd';
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  EllipsisOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { AnalysisTaskDetail, ProgressDetail } from '@/types';
import { DIMENSION_META, RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from '@/types';
import styles from './AnalysisProgressPanel.module.css';

interface Props {
  activeTask: AnalysisTaskDetail | null;
  analyzing: boolean;
  onStartAnalysis: () => void;
}

const AnalysisProgressPanel: React.FC<Props> = ({ activeTask, analyzing }) => {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 卡死检测：如果超过阈值时间无进度变化，标记为疑似卡死
  const lastProgressRef = useRef<number>(0);
  const stuckTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [maybeStuck, setMaybeStuck] = useState(false);
  const STUCK_THRESHOLD_MS = 5 * 60 * 1000; // 5分钟无进度变化即警告

  const isRunning = activeTask?.status === 'analyzing';
  const isCompleted = activeTask?.status === 'completed';
  const isFailed = activeTask?.status === 'failed';

  // 卡死检测逻辑
  useEffect(() => {
    if (isRunning) {
      const currentProgress = activeTask?.progress ?? 0;
      if (currentProgress !== lastProgressRef.current) {
        lastProgressRef.current = currentProgress;
        setMaybeStuck(false);
        // 重置卡死检测定时器
        if (stuckTimerRef.current) clearTimeout(stuckTimerRef.current);
        stuckTimerRef.current = setTimeout(() => {
          setMaybeStuck(true);
        }, STUCK_THRESHOLD_MS);
      }
      // 首次挂载时启动定时器
      if (!stuckTimerRef.current) {
        lastProgressRef.current = currentProgress;
        stuckTimerRef.current = setTimeout(() => {
          setMaybeStuck(true);
        }, STUCK_THRESHOLD_MS);
      }
    } else {
      setMaybeStuck(false);
      if (stuckTimerRef.current) {
        clearTimeout(stuckTimerRef.current);
        stuckTimerRef.current = null;
      }
    }
    return () => {
      if (stuckTimerRef.current) clearTimeout(stuckTimerRef.current);
    };
  }, [isRunning, activeTask?.progress]);

  // 解析 progress_detail
  const detail: ProgressDetail | null = useMemo(() => {
    if (!activeTask?.progress_detail) return null;
    return activeTask.progress_detail;
  }, [activeTask?.progress_detail]);

  // 计时器：运行中基于 started_at 差值计算（不受浏览器节流影响），完成后使用持久化值
  useEffect(() => {
    if (isRunning && activeTask?.started_at) {
      const start = new Date(activeTask.started_at).getTime();
      const tick = () => {
        setElapsed(Math.floor((Date.now() - start) / 1000));
      };
      tick(); // 立即执行一次
      timerRef.current = setInterval(tick, 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    } else if (isCompleted && activeTask?.total_duration_ms) {
      setElapsed(Math.floor(activeTask.total_duration_ms / 1000));
    } else {
      setElapsed(0);
    }
  }, [isRunning, isCompleted, activeTask?.started_at, activeTask?.total_duration_ms]);

  // 格式化秒数为 mm:ss
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // 格式化预计剩余
  const formatETA = (sec: number | null | undefined) => {
    if (sec === null || sec === undefined) return '--';
    if (sec <= 0) return '< 1分钟';
    const m = Math.ceil(sec / 60);
    return `~${m} 分钟`;
  };

  // 获取当前维度信息
  const currentDimKey = detail?.current_dimension;
  const currentDimMeta = DIMENSION_META.find((d) => d.key === currentDimKey);
  const currentDimInfo = currentDimKey ? detail?.dimensions?.[currentDimKey] : null;

  // 已发现问题数
  const issuesCount = activeTask?.issues_found ?? detail?.issues_found ?? 0;

  // 加权总进度
  const overallPercent = isCompleted ? 100 : (activeTask?.progress ?? 0);

  // ETA
  const eta = activeTask?.estimated_seconds ?? null;

  // 风险等级颜色
  const riskColor = activeTask?.risk_level
    ? RISK_LEVEL_COLORS[activeTask.risk_level] || '#8c8c8c'
    : '#8c8c8c';

  if (!activeTask && !analyzing) {
    return null;
  }

  return (
    <div className={styles.panel}>
      {/* ===== 总进度条 ===== */}
      <div className={styles.overallSection}>
        <div className={styles.overallHeader}>
          <span className={styles.overallLabel}>
            {isRunning ? '分析中...' : isCompleted ? '分析完成' : isFailed ? '分析失败' : '等待开始'}
          </span>
          <span className={styles.overallPercent}>{overallPercent}%</span>
        </div>
        <Progress
          percent={overallPercent}
          status={isFailed ? 'exception' : isCompleted ? 'success' : 'active'}
          strokeColor={
            isFailed ? '#f5222d'
            : isCompleted ? riskColor
            : '#1677ff'
          }
          showInfo={false}
          strokeWidth={8}
        />
        {/* 卡死警告 */}
        {isRunning && maybeStuck && (
          <div style={{
            marginTop: 8, padding: '8px 12px',
            background: '#fff7e6', border: '1px solid #ffd591',
            borderRadius: 6, fontSize: 13, color: '#d46b08',
          }}>
            ⚠️ 分析已持续 {formatTime(elapsed)}，进度长时间未更新。
            可能是任务处理较慢或发生异常，请耐心等待或刷新页面。
          </div>
        )}
      </div>

      {/* ===== 指标卡片行 ===== */}
      <Row gutter={12} className={styles.metricsRow}>
        {/* 当前维度 */}
        <Col span={8}>
          <Card size="small" className={styles.metricCard}>
            <div className={styles.metricTitle}>
              <SyncOutlined spin={isRunning} /> 当前维度
            </div>
            <div className={styles.metricValue}>
              {isRunning && currentDimMeta ? (
                <>
                  <span>{currentDimMeta.icon}</span>
                  <span>{currentDimMeta.label}</span>
                  {currentDimInfo && (
                    <span className={styles.metricSub}>
                      ({currentDimInfo.completed}/{currentDimInfo.total})
                    </span>
                  )}
                </>
              ) : isCompleted ? (
                <span style={{ color: '#52c41a' }}>
                  <CheckCircleOutlined /> 全部完成
                </span>
              ) : <span>--</span>}
            </div>
          </Card>
        </Col>

        {/* 已发现问题 */}
        <Col span={8}>
          <Card size="small" className={styles.metricCard}>
            <div className={styles.metricTitle}>
              <ExclamationCircleOutlined /> 已发现问题
            </div>
            <div className={styles.metricValue}>
              <Badge
                count={issuesCount}
                showZero
                overflowCount={999}
                color={issuesCount > 0 ? '#f5222d' : '#52c41a'}
                style={{ fontSize: 18 }}
              />
            </div>
          </Card>
        </Col>

        {/* 计时器 + ETA */}
        <Col span={8}>
          <Card size="small" className={styles.metricCard}>
            <div className={styles.metricTitle}>
              <ClockCircleOutlined /> {isCompleted ? '总耗时' : '计时 / 预计'}
            </div>
            <div className={styles.metricValue}>
              <span className={styles.timer}>{formatTime(elapsed)}</span>
              {isRunning && eta !== null && (
                <span className={styles.eta}>{formatETA(eta)}</span>
              )}
              {isCompleted && (
                <Tag color="success" style={{ marginLeft: 8 }}>已完成</Tag>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* ===== 6维度卡片网格 ===== */}
      <div className={styles.dimensionGrid}>
        {DIMENSION_META.map((dim) => {
          const dimInfo = detail?.dimensions?.[dim.key];
          const status = dimInfo?.status || 'pending';
          const completed = dimInfo?.completed || 0;
          const total = dimInfo?.total || 0;
          const dimPercent = total > 0 ? Math.round((completed / total) * 100) : 0;

          let statusIcon: React.ReactNode;
          let statusColor: string;
          if (status === 'completed') {
            statusIcon = <CheckCircleOutlined />;
            statusColor = '#52c41a';
          } else if (status === 'running') {
            statusIcon = <SyncOutlined spin />;
            statusColor = '#1677ff';
          } else {
            statusIcon = <EllipsisOutlined />;
            statusColor = '#d9d9d9';
          }

          return (
            <Card
              key={dim.key}
              size="small"
              className={`${styles.dimCard} ${status === 'running' ? styles.dimCardActive : ''}`}
            >
              <div className={styles.dimHeader}>
                <span>
                  <span style={{ marginRight: 4 }}>{dim.icon}</span>
                  <span className={styles.dimLabel}>{dim.label}</span>
                </span>
                <span style={{ color: statusColor }}>{statusIcon}</span>
              </div>
              <div className={styles.dimProgress}>
                <Progress
                  percent={dimPercent}
                  size="small"
                  status={status === 'completed' ? 'success' : status === 'running' ? 'active' : 'normal'}
                  strokeColor={statusColor}
                  showInfo={false}
                />
              </div>
              <div className={styles.dimFooter}>
                <span className={styles.dimStats}>
                  {status === 'pending' ? '等待中' : `${completed}/${total}`}
                </span>
                <Tag
                  color={status === 'completed' ? 'success' : status === 'running' ? 'processing' : 'default'}
                  style={{ fontSize: 10, lineHeight: '16px' }}
                >
                  {dim.weight}分
                </Tag>
              </div>
            </Card>
          );
        })}
      </div>

      {/* ===== 完成后显示风险评分 ===== */}
      {isCompleted && activeTask?.risk_score !== null && (
        <div className={styles.riskSummary}>
          <span>
            风险评分: <strong style={{ color: riskColor }}>{activeTask.risk_score?.toFixed(1)}</strong> / 100
          </span>
          <Tag color={RISK_LEVEL_COLORS[activeTask.risk_level || '']}>
            {RISK_LEVEL_LABELS[activeTask.risk_level || ''] || activeTask.risk_level}
          </Tag>
        </div>
      )}
    </div>
  );
};

export default AnalysisProgressPanel;
