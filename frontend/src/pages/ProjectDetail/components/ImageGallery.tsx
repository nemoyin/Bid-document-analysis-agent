/**
 * 图片相似对比展示组件
 * 并排展示相似图片及相似度分数。
 */
import React, { useState } from 'react';
import { Card, Tag, Typography, Progress, Row, Col, Empty, Modal, Image, Space, Button } from 'antd';
import { SwapOutlined } from '@ant-design/icons';
import type { ImageSimilarityResult } from '../../../types';

const { Text } = Typography;

/** 后端图片预览 API */
const IMAGE_PREVIEW_API = `${window.location.origin}/api/v1/images/preview`;

/** 将文件系统路径转为预览 URL */
const imageUrl = (filePath: string): string =>
  `${IMAGE_PREVIEW_API}?path=${encodeURIComponent(filePath)}`;

interface ImageGalleryProps {
  images: ImageSimilarityResult[];
  loading?: boolean;
}

const ImageGallery: React.FC<ImageGalleryProps> = ({ images, loading }) => {
  const [compareItem, setCompareItem] = useState<ImageSimilarityResult | null>(null);

  if (!images || images.length === 0) {
    return (
      <Card loading={loading}>
        <Empty description="暂无图片相似数据" />
      </Card>
    );
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        {images.map((img) => {
          const score = Number(img.similarity_score ?? 0);
          const color = score >= 85 ? '#fa541c' : score >= 70 ? '#faad14' : '#52c41a';
          const docShort = img.document_id.slice(0, 8);
          const hasSimilarPath = !!img.similar_image_path;

          return (
            <Col key={img.id} xs={24} sm={12} lg={8}>
              <Card
                size="small"
                title={
                  <div style={{ fontSize: 12 }}>
                    <Text code>{docShort}...</Text>
                    <span style={{ margin: '0 4px' }}>↔</span>
                    <Text code>
                      {img.similar_image_id ? img.similar_image_id.slice(0, 8) + '...' : '未知'}
                    </Text>
                  </div>
                }
                extra={
                  hasSimilarPath ? (
                    <Button
                      type="link"
                      size="small"
                      icon={<SwapOutlined />}
                      onClick={() => setCompareItem(img)}
                    >
                      对比
                    </Button>
                  ) : img.image_path ? (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => window.open(imageUrl(img.image_path), '_blank')}
                    >
                      预览
                    </Button>
                  ) : null
                }
              >
                <div style={{ textAlign: 'center', padding: '8px 0' }}>
                  <Progress
                    type="circle"
                    percent={score}
                    size={80}
                    strokeColor={color}
                    format={(p) => `${p?.toFixed(1)}%`}
                  />
                </div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>
                  <div>哈希: <Text code>{img.image_hash?.slice(0, 12)}...</Text></div>
                  <div>算法: {img.hash_algorithm}</div>
                  {img.page_number && <div>页码: {img.page_number}</div>}
                  {/* 缩略图预览 */}
                  {img.image_path && (
                    <div style={{ marginTop: 8, textAlign: 'center' }}>
                      <Image
                        src={imageUrl(img.image_path)}
                        alt="图片缩略图"
                        width={120}
                        height={80}
                        style={{ objectFit: 'cover', borderRadius: 4, border: '1px solid #eee' }}
                        fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIwIiBoZWlnaHQ9IjgwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMjAiIGhlaWdodD0iODAiIGZpbGw9IiNmNWY1ZjUiLz48dGV4dCB4PSI2MCIgeT0iNDUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiNjY2MiIGZvbnQtc2l6ZT0iMTIiPuWbvueJh+ivt+WPluWksei0pTwvdGV4dD48L3N2Zz4="
                      />
                    </div>
                  )}
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* 并排对比弹窗 */}
      <Modal
        open={!!compareItem}
        onCancel={() => setCompareItem(null)}
        footer={null}
        width={900}
        title={
          <Space>
            <Text strong>图片相似度对比</Text>
            {compareItem && (
              <Tag color={Number(compareItem.similarity_score ?? 0) >= 85 ? 'red' : 'orange'}>
                相似度: {Number(compareItem.similarity_score ?? 0).toFixed(1)}%
              </Tag>
            )}
          </Space>
        }
        destroyOnClose
      >
        {compareItem && (
          <div>
            <Row gutter={24}>
              <Col span={12}>
                <Card
                  size="small"
                  title={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      文档A - 第{compareItem.page_number || '?'}页
                    </Text>
                  }
                  bodyStyle={{ padding: 8, textAlign: 'center' }}
                >
                  <Image
                    src={imageUrl(compareItem.image_path)}
                    alt="文档A图片"
                    style={{ maxWidth: '100%', maxHeight: 400, objectFit: 'contain' }}
                    fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2ZhZmFmYSIvPjx0ZXh0IHg9IjIwMCIgeT0iMTU1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjE2Ij7lm77niYflj4rkuI3liLDor7flj5bkuK3vvIzor7flhYjnoazkv53mlofmoaPmnYPpmZDliLA8L3RleHQ+PC9zdmc+"
                  />
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>
                      路径: {compareItem.image_path.split(/[/\\]/).pop()}
                    </Text>
                  </div>
                </Card>
              </Col>
              <Col span={12}>
                <Card
                  size="small"
                  title={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      文档B（相似图片）
                    </Text>
                  }
                  bodyStyle={{ padding: 8, textAlign: 'center' }}
                >
                  {compareItem.similar_image_path ? (
                    <>
                      <Image
                        src={imageUrl(compareItem.similar_image_path)}
                        alt="文档B相似图片"
                        style={{ maxWidth: '100%', maxHeight: 400, objectFit: 'contain' }}
                        fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2ZhZmFmYSIvPjx0ZXh0IHg9IjIwMCIgeT0iMTU1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjE2Ij7lm77niYflj4rkuI3liLDor7flj5bkuK3vvIzor7flhYjnoazkv53mlofmoaPmnYPpmZDliLA8L3RleHQ+PC9zdmc+"
                      />
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 11, wordBreak: 'break-all' }}>
                          路径: {compareItem.similar_image_path.split(/[/\\]/).pop()}
                        </Text>
                      </div>
                    </>
                  ) : (
                    <div style={{ padding: 40, color: '#999' }}>
                      <Text type="secondary">相似图片路径不可用</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        请重新运行分析以获取对比图片路径
                      </Text>
                    </div>
                  )}
                </Card>
              </Col>
            </Row>

            {/* 底部信息 */}
            <div style={{
              marginTop: 16, padding: '12px 16px', background: '#fafafa',
              borderRadius: 6, fontSize: 12,
            }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Text type="secondary">哈希值: </Text>
                  <Text code style={{ fontSize: 11 }}>{compareItem.image_hash?.slice(0, 24)}...</Text>
                </Col>
                <Col span={8}>
                  <Text type="secondary">算法: </Text>
                  <Text>{compareItem.hash_algorithm}</Text>
                </Col>
                <Col span={8}>
                  <Text type="secondary">相似文档ID: </Text>
                  <Text code style={{ fontSize: 11 }}>
                    {compareItem.similar_image_id?.slice(0, 12) || '-'}...
                  </Text>
                </Col>
              </Row>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ImageGallery;
