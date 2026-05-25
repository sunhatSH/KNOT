import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  NodeIndexOutlined,
  DatabaseOutlined,
  SettingOutlined,
} from '@ant-design/icons';

const { Header } = Layout;

const menuItems = [
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
    key: '/settings',
    icon: <SettingOutlined />,
    label: '设置',
  },
];

export default function AppHeader() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = location.pathname.startsWith('/workflows')
    ? '/workflows'
    : location.pathname;

  return (
    <Header
      style={{
        display: 'flex',
        alignItems: 'center',
        background: '#fff',
        borderBottom: '1px solid #e8eaf0',
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
    </Header>
  );
}
