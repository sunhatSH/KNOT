import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Layout } from 'antd';
import AppHeader from '@/components/AppHeader';
import WorkflowList from '@/pages/WorkflowList';
import WorkflowEditor from '@/pages/WorkflowEditor';
import ExecutionDetail from '@/pages/ExecutionDetail';
import KnowledgePage from '@/pages/KnowledgePage';
import SettingsPage from '@/pages/SettingsPage';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import { useAuthStore } from '@/store/authStore';

const { Content } = Layout;

/** Wraps routes that require authentication. Redirects to /login if not authenticated. */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  // Fetch user info on mount if token exists but user is not yet loaded
  useEffect(() => {
    if (token && !user) {
      useAuthStore.getState().fetchUser();
    }
  }, [token, user]);

  // Determine if we're on an auth page (hide header)
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register';

  return (
    <Layout style={{ height: '100%' }}>
      {!isAuthPage && <AppHeader />}
      <Content>
        <Routes>
          {/* Public auth routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Redirect root to workflows */}
          <Route path="/" element={<Navigate to="/workflows" replace />} />

          {/* Protected routes */}
          <Route
            path="/workflows"
            element={
              <ProtectedRoute>
                <WorkflowList />
              </ProtectedRoute>
            }
          />
          <Route
            path="/workflows/:id"
            element={
              <ProtectedRoute>
                <WorkflowEditor />
              </ProtectedRoute>
            }
          />
          <Route
            path="/executions/:id"
            element={
              <ProtectedRoute>
                <ExecutionDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/knowledge"
            element={
              <ProtectedRoute>
                <KnowledgePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />

          {/* Catch-all: redirect to workflows */}
          <Route path="*" element={<Navigate to="/workflows" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
