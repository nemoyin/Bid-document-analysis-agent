/**
 * 应用布局组件
 * 包含侧边栏导航和内容区域。
 */
import React, { useState } from 'react';
import { Layout, Menu, Typography } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  FolderOutlined,
  FileTextOutlined,
  SettingOutlined,
  BarChartOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: '系统首页' },
    { key: '/dashboard', icon: <BarChartOutlined />, label: '数据仪表盘' },
    { key: '/projects', icon: <FolderOutlined />, label: '任务列表' },
    { key: '/reports', icon: <FileTextOutlined />, label: '分析报告' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  const selectedKey = '/' + location.pathname.split('/')[1];

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        style={{ overflow: 'auto', height: '100vh', position: 'sticky', top: 0, left: 0 }}
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Title level={4} style={{ color: '#fff', margin: 0, fontSize: collapsed ? 14 : 16 }}>
            {collapsed ? 'BASS' : '投标分析系统'}
          </Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout style={{ overflow: 'hidden' }}>
        <Header style={{
          background: '#fff', padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex', alignItems: 'center',
        }}>
          <BarChartOutlined style={{ fontSize: 20, marginRight: 8 }} />
          <span style={{ fontSize: 16, fontWeight: 500 }}>投标标书智能分析监督系统</span>
        </Header>
        <Content style={{
          margin: 16, padding: 16,
          overflow: 'auto',
          height: 'calc(100vh - 64px)',
          background: '#f5f5f5',
          borderRadius: 8,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
