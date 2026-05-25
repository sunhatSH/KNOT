import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import { NodeIndexOutlined, DatabaseOutlined, SettingOutlined } from '@ant-design/icons';

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

  return (
    <Header style={{ display: 'flex', alignItems: 'center' }}>
      <div style={{ color: '#fff', fontSize: 18, fontWeight: 'bold', marginRight: 40 }}>
        KNOT
      </div>
      <Menu
        theme="dark"
        mode="horizontal"
        selectedKeys={[location.pathname.startsWith('/workflows') ? '/workflows' : location.pathname]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  );
}
