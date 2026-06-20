/**
 * 首页 — 系统功能介绍 & 6维度风险等级介绍
 */
import React from 'react';
import { Card, Row, Col, Typography, Tag, Divider, Space } from 'antd';
import {
  FileTextOutlined, BarChartOutlined, PictureOutlined,
  TableOutlined, AlertOutlined, DatabaseOutlined,
  ThunderboltOutlined, SafetyOutlined, SearchOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Paragraph, Text } = Typography;

const dimensions = [
  {
    icon: <FileTextOutlined style={{ fontSize: 28, color: '#1890ff' }} />,
    title: '文本相似度分析',
    weight: '权重 30%',
    desc: '基于 ChromaDB 向量数据库 + Gitee AI Embedding，对投标文件进行全文语义比对。将文档分块后计算余弦相似度，识别高相似段落，检测不同投标文件之间是否存在大段雷同内容。',
    signals: ['全文语义高度相似', '多处段落逐字雷同', '技术方案大面积重合'],
    color: '#1890ff',
  },
  {
    icon: <MenuOutlined style={{ fontSize: 28, color: '#722ed1' }} />,
    title: '目录结构相似度',
    weight: '权重 15%',
    desc: '提取文档章节标题序列（如"第X章"、"X.X"等编号），使用最长公共子序列(LCS)算法比对标题文本和层级结构的匹配程度。高相似度可能表明使用了相同的投标模板。',
    signals: ['章节结构高度一致', '标题编号体系相同', '附录布局雷同'],
    color: '#722ed1',
  },
  {
    icon: <PictureOutlined style={{ fontSize: 28, color: '#eb2f96' }} />,
    title: '图片相似度分析',
    weight: '权重 15%',
    desc: '采用三哈希融合算法（pHash + aHash + dHash）对文档中提取的图片进行指纹比对。识别不同投标文件中的相同图片、相似图表，检测图片复用和篡改情况。',
    signals: ['图片指纹完全匹配', '图表数据高度相似', '组织机构图雷同'],
    color: '#eb2f96',
  },
  {
    icon: <TableOutlined style={{ fontSize: 28, color: '#fa8c16' }} />,
    title: '表格相似度分析',
    weight: '权重 10%',
    desc: '比对文档中表格的结构（表头、行列数）和单元格内容。综合计算表头 Jaccard 相似度(40%)、行列结构匹配(20%)和单元格内容重叠(40%)。',
    signals: ['报价明细表高度一致', '技术参数表行数相同', '相同位置表格内容重叠'],
    color: '#fa8c16',
  },
  {
    icon: <AlertOutlined style={{ fontSize: 28, color: '#f5222d' }} />,
    title: '错别字一致性检测',
    weight: '权重 20%',
    desc: '基于 pycorrector 深度学习模型 + jieba 分词，检测投标文件中的错别字和术语错误。重点关注不同投标文件中的共享错误 — 如果多份标书存在相同的错别字，是围标串标的重要线索。',
    signals: ['多文档存在相同错别字', '专业术语拼写一致错误', '数字序号连续出错'],
    color: '#f5222d',
  },
  {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
    title: '元数据一致性分析',
    weight: '权重 10%',
    desc: '提取并比对投标文件的文件属性元数据（作者、创建者、生成软件、公司、标题、修改者等）。如果不同企业的标书具有相同的元数据字段，强烈暗示标书出自同一来源。',
    signals: ['作者/创建者字段相同', '生成软件版本一致', '公司元数据字段匹配'],
    color: '#52c41a',
  },
];

const riskLevels = [
  { level: 'LOW', label: '低风险', range: '0-30分', color: '#52c41a', desc: '未发现明显异常，投标文件间差异合理，建议归档备查。' },
  { level: 'MODERATE', label: '中风险', range: '31-60分', color: '#faad14', desc: '存在一定程度相似，建议人工抽查确认合理性。' },
  { level: 'HIGH', label: '高风险', range: '61-85分', color: '#fa541c', desc: '存在明显相似度，建议人工复核是否涉嫌围标。' },
  { level: 'CRITICAL', label: '严重风险', range: '86-100分', color: '#f5222d', desc: '存在严重相似度，强烈建议启动围标串标调查程序。' },
];

const Home: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* ── Hero 区域 ── */}
      <Card
        style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          marginBottom: 24,
          border: 'none',
        }}
        bodyStyle={{ padding: '48px 40px' }}
      >
        <Row align="middle" gutter={40}>
          <Col flex="auto">
            <Title level={1} style={{ color: '#fff', marginBottom: 8, fontSize: 36 }}>
              <ThunderboltOutlined /> 投标标书智能分析监督系统
            </Title>
            <Title level={4} style={{ color: 'rgba(255,255,255,0.85)', fontWeight: 400, marginBottom: 24 }}>
              Bidding Analysis & Supervision System (BASS)
            </Title>
            <Paragraph style={{ color: 'rgba(255,255,255,0.75)', fontSize: 15, lineHeight: 1.8 }}>
              基于 AI 大模型的投标文件智能分析平台，覆盖<Text style={{ color: '#fff', fontWeight: 600 }}>文本相似度、目录结构、图片相似、表格相似、错别字一致性、元数据一致性</Text>六大维度，
              自动化检测投标文件中的围标串标风险线索，为采购监督管理提供数据支撑。
            </Paragraph>
          </Col>
          <Col>
            <SafetyOutlined style={{ fontSize: 100, color: 'rgba(255,255,255,0.3)' }} />
          </Col>
        </Row>
      </Card>

      {/* ── 核心功能 ── */}
      <Title level={3} style={{ marginBottom: 20 }}>
        <SearchOutlined /> 核心功能
      </Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
        {[
          { icon: <FileTextOutlined />, title: '投标文件管理', desc: '支持 PDF/DOCX/DOC 格式上传和解析，自动提取文本、图片、表格内容' },
          { icon: <BarChartOutlined />, title: '六维度分析', desc: '从文本、结构、图片、表格、错别字、元数据六个维度综合评估风险' },
          { icon: <AlertOutlined />, title: '风险评分', desc: '基于加权评分模型自动计算综合风险分数并划分风险等级' },
          { icon: <FileTextOutlined />, title: '报告导出', desc: '支持 PDF 和 Word 格式报告下载，包含详细分析明细和综合建议' },
        ].map((f, i) => (
          <Col xs={24} sm={12} md={6} key={i}>
            <Card hoverable style={{ height: '100%', textAlign: 'center' }}>
              <div style={{ fontSize: 36, color: '#1890ff', marginBottom: 12 }}>{f.icon}</div>
              <Title level={5}>{f.title}</Title>
              <Text type="secondary">{f.desc}</Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Divider />

      {/* ── 六维度详解 ── */}
      <Title level={3} style={{ marginBottom: 20 }}>
        <BarChartOutlined /> 六维度分析详解
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 24, fontSize: 14 }}>
        综合分析评分 = 文本相似度(30%) + 目录结构(15%) + 图片相似(15%) + 表格相似(10%) + 错别字一致性(20%) + 元数据一致性(10%)
      </Paragraph>
      <Row gutter={[16, 16]}>
        {dimensions.map((dim, i) => (
          <Col xs={24} md={12} key={i}>
            <Card
              hoverable
              style={{ height: '100%', borderLeft: `4px solid ${dim.color}` }}
              bodyStyle={{ padding: 20 }}
            >
              <Space align="start">
                {dim.icon}
                <div>
                  <Title level={5} style={{ marginBottom: 4 }}>
                    {dim.title}
                    <Tag color={dim.color} style={{ marginLeft: 8 }}>{dim.weight}</Tag>
                  </Title>
                  <Paragraph style={{ marginBottom: 12, color: '#555', lineHeight: 1.7 }}>
                    {dim.desc}
                  </Paragraph>
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>⚠ 风险信号：</Text>
                    <div style={{ marginTop: 4 }}>
                      {dim.signals.map((s, j) => (
                        <Tag key={j} style={{ marginBottom: 4 }}>{s}</Tag>
                      ))}
                    </div>
                  </div>
                </div>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Divider />

      {/* ── 风险等级 ── */}
      <Title level={3} style={{ marginBottom: 20 }}>
        <SafetyOutlined /> 风险等级说明
      </Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 40 }}>
        {riskLevels.map((r) => (
          <Col xs={24} sm={12} md={6} key={r.level}>
            <Card hoverable style={{ borderTop: `3px solid ${r.color}`, height: '100%' }}>
              <Tag color={r.color} style={{ fontSize: 14, padding: '2px 12px', marginBottom: 8 }}>
                {r.label}
              </Tag>
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                评分范围：{r.range}
              </Text>
              <Paragraph style={{ color: '#555', fontSize: 13, lineHeight: 1.6 }}>
                {r.desc}
              </Paragraph>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
};

export default Home;
