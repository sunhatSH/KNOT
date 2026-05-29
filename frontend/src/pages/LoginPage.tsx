import { useNavigate, Link } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, Alert } from 'antd';
import { UserOutlined, LockOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';

const { Title, Text } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, loading, error, clearError } = useAuthStore();
  const [form] = Form.useForm();

  const handleSubmit = async (values: { username: string; password: string }) => {
    clearError();
    try {
      await login(values.username, values.password);
      navigate('/workflows', { replace: true });
    } catch {
      // error is handled in store
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-page)',
        padding: 24,
      }}
    >
      <Card
        style={{
          width: 400,
          maxWidth: '100%',
          borderRadius: 8,
          border: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
        }}
      >
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              background: '#4f6ef7',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <NodeIndexOutlined style={{ fontSize: 28, color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: 0, color: 'var(--text-primary)' }}>
            登录 KNOT
          </Title>
          <Text type="secondary" style={{ fontSize: 14 }}>
            智能工作流编排平台
          </Text>
        </div>

        {/* Error alert */}
        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            closable
            onClose={clearError}
            style={{ marginBottom: 20, borderRadius: 6 }}
          />
        )}

        {/* Login form */}
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: '#999' }} />}
              placeholder="用户名"
              style={{
                background: 'var(--bg-page)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-primary)',
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#999' }} />}
              placeholder="密码"
              style={{
                background: 'var(--bg-page)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-primary)',
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, fontSize: 16, borderRadius: 6 }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        {/* Register link */}
        <div style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 14 }}>
            没有账号？{' '}
            <Link
              to="/register"
              style={{ color: '#4f6ef7' }}
              onClick={clearError}
            >
              立即注册
            </Link>
          </Text>
        </div>
      </Card>
    </div>
  );
}
