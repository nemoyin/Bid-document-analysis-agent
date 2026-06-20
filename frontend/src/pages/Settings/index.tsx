/**
 * 系统设置页面
 * 可配置分析权重和风险等级阈值。
 */
import React, { useState, useEffect } from 'react';
import { Card, Typography, Breadcrumb, Spin, Space, Row, Col, Form, InputNumber, Button, message, Tag, Descriptions } from 'antd';
import { SettingOutlined, HomeOutlined, SaveOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title } = Typography;

const API_BASE = `${window.location.origin}/api/v1`;

interface AnalysisConfig {
  text_similarity_weight: number;
  image_similarity_weight: number;
  error_consistency_weight: number;
  similarity_threshold: number;
  chunk_size: number;
  max_file_size_mb: number;
}

interface RiskThresholds {
  low: number;
  medium: number;
  high: number;
}

interface SettingsData {
  analysis: AnalysisConfig;
  risk_thresholds: RiskThresholds;
}

const defaultSettings: SettingsData = {
  analysis: {
    text_similarity_weight: 0.4,
    image_similarity_weight: 0.25,
    error_consistency_weight: 0.35,
    similarity_threshold: 0.8,
    chunk_size: 512,
    max_file_size_mb: 50,
  },
  risk_thresholds: {
    low: 0.3,
    medium: 0.6,
    high: 0.85,
  },
};

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<SettingsData>(defaultSettings);
  const [analysisForm] = Form.useForm();
  const [riskForm] = Form.useForm();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/settings`);
      const data = await resp.json();
      if (data.code === 0 && data.data) {
        setSettings(data.data);
        analysisForm.setFieldsValue(data.data.analysis);
        riskForm.setFieldsValue(data.data.risk_thresholds);
      }
    } catch {
      analysisForm.setFieldsValue(defaultSettings.analysis);
      riskForm.setFieldsValue(defaultSettings.risk_thresholds);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAnalysis = async (values: AnalysisConfig) => {
    setSaving(true);
    try {
      const resp = await fetch(`${API_BASE}/settings/analysis`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const data = await resp.json();
      if (data.code === 0) {
        message.success('分析配置保存成功');
      } else {
        message.error(data.message || '保存失败');
      }
    } catch (err: any) {
      message.error(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRisk = async (values: RiskThresholds) => {
    setSaving(true);
    try {
      const resp = await fetch(`${API_BASE}/settings/risk-thresholds`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const data = await resp.json();
      if (data.code === 0) {
        message.success('风险阈值保存成功');
      } else {
        message.error(data.message || '保存失败');
      }
    } catch (err: any) {
      message.error(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div>
      <Breadcrumb items={[{ title: <><HomeOutlined /> 首页</> }, { title: '系统设置' }]} style={{ marginBottom: 16 }} />
      <Title level={4}><SettingOutlined /> 系统设置</Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="分析权重配置">
            <Form form={analysisForm} layout="vertical" onFinish={handleSaveAnalysis}>
              <Form.Item label="文本相似度权重" name="text_similarity_weight">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="图片相似度权重" name="image_similarity_weight">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="错误一致性权重" name="error_consistency_weight">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="相似度阈值" name="similarity_threshold">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="文本分块大小" name="chunk_size">
                <InputNumber min={128} max={2048} step={64} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="最大文件大小(MB)" name="max_file_size_mb">
                <InputNumber min={1} max={200} style={{ width: '100%' }} />
              </Form.Item>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>保存</Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="风险等级阈值">
            <Form form={riskForm} layout="vertical" onFinish={handleSaveRisk}>
              <Form.Item label="低风险上限" name="low">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="中风险上限" name="medium">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="高风险上限" name="high">
                <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
              </Form.Item>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>保存</Button>
            </Form>
          </Card>
          <Card title="当前配置摘要" style={{ marginTop: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="文本:图片:错误权重">
                {settings.analysis.text_similarity_weight} : {settings.analysis.image_similarity_weight} : {settings.analysis.error_consistency_weight}
              </Descriptions.Item>
              <Descriptions.Item label="相似度阈值">{settings.analysis.similarity_threshold}</Descriptions.Item>
              <Descriptions.Item label="风险阈值">{settings.risk_thresholds.low} / {settings.risk_thresholds.medium} / {settings.risk_thresholds.high}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Settings;
