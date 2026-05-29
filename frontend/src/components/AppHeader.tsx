import { Layout, Menu, Button } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  NodeIndexOutlined,
  DatabaseOutlined,
  SettingOutlined,
  BarChartOutlined,
  SunOutlined,
  MoonOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { useThemeStore } from '@/store/themeStore';
import { useLanguage } from '@/i18n/useLanguage';

const { Header } = Layout;

const menuItems = [
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: '总览',
  },
  {
    key: '/workflows',
    icon: <NodeIndexOutlined />,
    label: '工作流',
  },
  {
    key: '/knowledge',
    icon: <DatabaseOutlined />,
    label: '知识库',
  },
  {
    key: '/monitoring',
    icon: <BarChartOutlined />,
    label: '监控',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '设置',
  },
];

export default function AppHeader() {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, toggle } = useThemeStore();
  const { currentLang, switchLanguage } = useLanguage();

  const selectedKey = location.pathname.startsWith('/workflows')
    ? '/workflows'
    : location.pathname.startsWith('/dashboard')
    ? '/dashboard'
    : location.pathname.startsWith('/monitoring')
    ? '/monitoring'
    : location.pathname;

  return (
    <Header
      style={{
        display: 'flex',
        alignItems: 'center',
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-color)',
        height: 56,
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Brand logo */}
      <div
        style={{
          color: '#4f6ef7',
          fontSize: 20,
          fontWeight: 700,
          marginRight: 40,
          letterSpacing: 1,
          userSelect: 'none',
          cursor: 'default',
        }}
      >
        KNOT
      </div>

      {/* Navigation */}
      <Menu
        mode="horizontal"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{
          flex: 1,
          minWidth: 0,
          borderBottom: 'none',
          background: 'transparent',
        }}
      />

      {/* Theme toggle */}
      <Button
        type="text"
        icon={mode === 'light' ? <MoonOutlined /> : <SunOutlined />}
        onClick={() => toggle()}
        style={{ color: 'var(--text-secondary, #5a6170)' }}
      />

      {/* Language switcher */}
      <Button
        type="text"
        icon={<GlobalOutlined />}
        onClick={() => switchLanguage(currentLang === 'zh' ? 'en' : 'zh')}
        style={{ color: 'var(--text-secondary, #5a6170)', marginLeft: 4 }}
      >
        {currentLang === 'zh' ? 'EN' : '中'}
      </Button>
    </Header>
  );
}
