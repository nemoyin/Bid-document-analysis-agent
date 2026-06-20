/**
 * 文本相似度结果表格
 * 展示文档之间的相似度分数和详细片段。
 */
import React, { useState } from 'react';
import { Card, Table, Tag, Typography, Empty, Progress, Modal, List, Tooltip } from 'antd';
import type { SimilarityResult } from '../../../types';

const { Text } = Typography;

interface SimilarityTableProps {
  results: SimilarityResult[];
  loading?: boolean;
}

interface ChunkPair {
  score: number;
  doc1_chunk: string;
  doc2_chunk: string;
  doc1_page?: number;
  doc2_page?: number;
}

const SimilarityTable: React.FC<SimilarityTableProps> = ({ results, loading }) => {
  const [detailModal, setDetailModal] = useState<SimilarityResult | null>(null);

  if (!results || results.length === 0) {
    return (
      <Card loading={loading}>
        <Empty description="暂无文本相似度数据，请先启动分析" />
      </Card>
    );
  }

  /** 根据分数返回颜色 */
  const scoreColor = (score: number) =>
    score >= 85 ? '#f5222d' : score >= 70 ? '#fa541c' : score >= 50 ? '#faad14' : '#52c41a';

  const columns = [
    {
      title: '文档A', dataIndex: 'doc1_id', key: 'doc1_id', width: 120, ellipsis: true,
      render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
    },
    {
      title: '文档B', dataIndex: 'doc2_id', key: 'doc2_id', width: 120, ellipsis: true,
      render: (id: string) => <Text code>{id.slice(0, 8)}...</Text>,
    },
    {
      title: '全文相似度', dataIndex: 'full_text_similarity', key: 'full_text_similarity', width: 160,
      render: (val: number | null) => {
        if (val === null || val === undefined) return '-';
        const score = Number(val);
        return (
          <Progress
            percent={score}
            size="small"
            strokeColor={scoreColor(score)}
            format={p => `${Number(p ?? 0).toFixed(1)}%`}
            style={{ width: 140 }}
          />
        );
      },
    },
    {
      title: '高相似片段数', key: 'high_pairs', width: 120, align: 'center' as const,
      render: (_: any, record: SimilarityResult) => {
        const count = record.details?.high_similarity_pairs;
        if (count === undefined || count === null) return '-';
        return (
          <Tag color={count > 5 ? 'red' : count > 2 ? 'orange' : 'green'}>
            {count} 段
          </Tag>
        );
      },
    },
    {
      title: '总片段数', key: 'total_pairs', width: 100, align: 'center' as const,
      render: (_: any, record: SimilarityResult) => {
        const count = record.details?.total_pairs;
        return count !== undefined && count !== null ? `${count} 段` : '-';
      },
    },
    {
      title: '商务相似度', dataIndex: 'business_similarity', key: 'business_similarity', width: 100,
      render: (val: number | null) => val !== null ? `${Number(val).toFixed(1)}%` : '-',
    },
    {
      title: '技术相似度', dataIndex: 'technical_similarity', key: 'technical_similarity', width: 100,
      render: (val: number | null) => val !== null ? `${Number(val).toFixed(1)}%` : '-',
    },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: any, record: SimilarityResult) => (
        <a onClick={() => setDetailModal(record)}>查看详情</a>
      ),
    },
  ];

  /** 展开行：显示前几条高相似片段 */
  const expandedRowRender = (record: SimilarityResult) => {
    const topPairs: ChunkPair[] = record.details?.top_pairs || [];
    if (topPairs.length === 0) {
      return <Text type="secondary">暂无片段明细</Text>;
    }

    const displayPairs = topPairs.slice(0, 5);

    return (
      <div style={{ padding: '8px 0' }}>
        <Text strong style={{ marginBottom: 8, display: 'block' }}>
          高相似片段预览（共 {topPairs.length} 条，显示前 {displayPairs.length} 条）
        </Text>
        <List
          size="small"
          dataSource={displayPairs}
          renderItem={(pair: ChunkPair, idx: number) => (
            <List.Item style={{ padding: '8px 0' }}>
              <div style={{ width: '100%' }}>
                <div style={{ marginBottom: 4 }}>
                  <Tag color="blue">#{idx + 1}</Tag>
                  <Text strong style={{ fontSize: 13 }}>
                    相似度: {(pair.score * 100).toFixed(1)}%
                  </Text>
                  {pair.doc1_page && (
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      文档A 第{pair.doc1_page}页
                    </Text>
                  )}
                  {pair.doc2_page && (
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      文档B 第{pair.doc2_page}页
                    </Text>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div style={{ flex: 1, background: '#fafafa', padding: 8, borderRadius: 4, maxHeight: 80, overflow: 'auto' }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>文档A片段:</Text>
                    <br />
                    <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>
                      {pair.doc1_chunk?.length > 200
                        ? pair.doc1_chunk.slice(0, 200) + '...'
                        : pair.doc1_chunk}
                    </Text>
                  </div>
                  <div style={{ flex: 1, background: '#fafafa', padding: 8, borderRadius: 4, maxHeight: 80, overflow: 'auto' }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>文档B片段:</Text>
                    <br />
                    <Text style={{ fontSize: 12, wordBreak: 'break-all' }}>
                      {pair.doc2_chunk?.length > 200
                        ? pair.doc2_chunk.slice(0, 200) + '...'
                        : pair.doc2_chunk}
                    </Text>
                  </div>
                </div>
              </div>
            </List.Item>
          )}
        />
        {topPairs.length > 5 && (
          <a onClick={() => setDetailModal(record)} style={{ marginTop: 8, display: 'inline-block' }}>
            查看全部 {topPairs.length} 条片段 →
          </a>
        )}
      </div>
    );
  };

  return (
    <Card title="文本相似度分析结果" bodyStyle={{ padding: 0 }}>
      <Table
        dataSource={results}
        rowKey="id"
        loading={loading}
        columns={columns}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          rowExpandable: (record) =>
            !!(record.details?.top_pairs && record.details.top_pairs.length > 0),
        }}
      />
      {/* 详情弹窗：展示全部相似片段明细 */}
      <Modal
        title="相似度详细结果"
        open={!!detailModal}
        onCancel={() => setDetailModal(null)}
        footer={null}
        width={800}
      >
        {detailModal && (
          <div>
            <p><Text strong>文档A ID：</Text><Text code>{detailModal.doc1_id}</Text></p>
            <p><Text strong>文档B ID：</Text><Text code>{detailModal.doc2_id}</Text></p>
            <p>
              <Text strong>全文相似度：</Text>
              <Text style={{ color: '#f5222d', fontSize: 18 }}>
                {Number(detailModal.full_text_similarity ?? 0).toFixed(1)}%
              </Text>
            </p>
            {detailModal.details && (
              <>
                <p>
                  <Text strong>总片段数：</Text>{detailModal.details.total_pairs || 0}
                  <span style={{ marginLeft: 16 }} />
                  <Text strong>高相似片段数：</Text>
                  <Tag color="red">{detailModal.details.high_similarity_pairs || 0}</Tag>
                </p>
              </>
            )}
            {detailModal.details?.top_pairs && (
              <>
                <p><Text strong>高相似片段明细 (Top {detailModal.details.top_pairs.length})：</Text></p>
                <List
                  size="small"
                  dataSource={detailModal.details.top_pairs}
                  renderItem={(pair: ChunkPair, idx: number) => (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <span>
                            <Tag color="blue">#{idx + 1}</Tag>
                            相似度: {(pair.score * 100).toFixed(1)}%
                            {pair.doc1_page && <Text type="secondary" style={{ marginLeft: 8 }}>A页{pair.doc1_page}</Text>}
                            {pair.doc2_page && <Text type="secondary" style={{ marginLeft: 8 }}>B页{pair.doc2_page}</Text>}
                          </span>
                        }
                        description={
                          <div style={{ display: 'flex', gap: 12 }}>
                            <div style={{ flex: 1 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>文档A:</Text>
                              <div style={{
                                fontSize: 12, background: '#fff7e6', padding: '6px 8px',
                                borderRadius: 4, maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
                              }}>
                                {pair.doc1_chunk || '(空)'}
                              </div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>文档B:</Text>
                              <div style={{
                                fontSize: 12, background: '#e6f7ff', padding: '6px 8px',
                                borderRadius: 4, maxHeight: 120, overflow: 'auto', whiteSpace: 'pre-wrap',
                              }}>
                                {pair.doc2_chunk || '(空)'}
                              </div>
                            </div>
                          </div>
                        }
                      />
                    </List.Item>
                  )}
                />
              </>
            )}
          </div>
        )}
      </Modal>
    </Card>
  );
};

export default SimilarityTable;
