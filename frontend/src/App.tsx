import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import AppHeader from '@/components/AppHeader';
import WorkflowList from '@/pages/WorkflowList';
import WorkflowEditor from '@/pages/WorkflowEditor';

const { Content } = Layout;

export default function App() {
  return (
    <Layout style={{ height: '100%' }}>
      <AppHeader />
      <Content>
        <Routes>
          <Route path="/" element={<Navigate to="/workflows" replace />} />
          <Route path="/workflows" element={<WorkflowList />} />
          <Route path="/workflows/:id" element={<WorkflowEditor />} />
        </Routes>
      </Content>
    </Layout>
  );
}
