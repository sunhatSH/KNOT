import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, Alert } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';

const { Title, Text } = Typography;

interface RegisterFormValues {
  username: string;
  password: string;
  confirmPassword: string;
  email?: string;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, loading, error, clearError } = useAuthStore();
  const [form] = Form.useForm<RegisterFormValues>();
  const [registered, setRegistered] = useState(false);

  const handleSubmit = async (values: RegisterFormValues) => {
    clearError();
    try {
      await register(values.username, values.password, values.email || undefined);
      setRegistered(true);
    } catch {
      // error is handled in store
    }
  };

  // Success state
  if (registered) {
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
            textAlign: 'center',
          }}
        >
          <div style={{ padding: '24px 0' }}>
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 32,
                background: '#52c41a',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
              }}
            >
              <UserOutlined style={{ fontSize: 32, color: '#fff' }} />
            </div>
            <Title level={3} style={{ margin: '0 0 8px', color: 'var(--text-primary)' }}>
              注册成功
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 24, fontSize: 14 }}>
              你的账号已创建，现在可以登录使用 KNOT
            </Text>
            <Button
              type="primary"
              size="large"
              onClick={() => navigate('/login')}
              style={{ height: 44, fontSize: 16, borderRadius: 6, padding: '0 32px' }}
            >
              前往登录
            </Button>
          </div>
        </Card>
      </div>
    );
  }

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
            注册 KNOT
          </Title>
          <Text type="secondary" style={{ fontSize: 14 }}>
            创建你的账号
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

        {/* Register form */}
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少 3 个字符' },
            ]}
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
            name="email"
            rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
          >
            <Input
              prefix={<MailOutlined style={{ color: '#999' }} />}
              placeholder="邮箱（选填）"
              style={{
                background: 'var(--bg-page)',
                borderColor: 'var(--border-color)',
                color: 'var(--text-primary)',
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
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

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#999' }} />}
              placeholder="确认密码"
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
              注册
            </Button>
          </Form.Item>
        </Form>

        {/* Login link */}
        <div style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 14 }}>
            已有账号？{' '}
            <Link
              to="/login"
              style={{ color: '#4f6ef7' }}
              onClick={clearError}
            >
              返回登录
            </Link>
          </Text>
        </div>
      </Card>
    </div>
  );
}
