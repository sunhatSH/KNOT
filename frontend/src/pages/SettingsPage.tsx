import { useState, useCallback } from 'react';
import { Alert, Button, Card, Form, Input, message, Select, Switch, Typography, Space, Divider } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useMediaQuery } from '@/hooks/useMediaQuery';

const { Title, Text } = Typography;

const STORAGE_KEY = 'knot_settings';
const BASE_URL = '/api/v1';

const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'azure', label: 'Azure OpenAI' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'custom', label: 'Custom' },
];

interface SettingsValues {
  llmProvider: string;
  apiBaseUrl: string;
  apiKey: string;
  debugMode: boolean;
}

const defaultValues: SettingsValues = {
  llmProvider: 'openai',
  apiBaseUrl: '',
  apiKey: '',
  debugMode: false,
};

function loadSettings(): SettingsValues {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...defaultValues, ...JSON.parse(raw) };
    }
  } catch {
    // ignore parse errors
  }
  return defaultValues;
}

function saveSettings(values: SettingsValues) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
}

export default function SettingsPage() {
  const [form] = Form.useForm();
  const [testing, setTesting] = useState(false);
  const isMobile = useMediaQuery('(max-width: 768px)');

  const initialValues = loadSettings();
  const hasSettings = !!(initialValues.apiBaseUrl || initialValues.apiKey);

  const handleTestConnection = useCallback(async () => {
    setTesting(true);
    try {
      const values = form.getFieldsValue() as SettingsValues;
      const baseUrl = values.apiBaseUrl || BASE_URL;
      const response = await fetch(`${baseUrl}/health`, {
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      message.success('连接成功');
    } catch {
      message.error('连接失败，请检查地址和配置');
    } finally {
      setTesting(false);
    }
  }, [form]);

  const handleFinish = (values: SettingsValues) => {
    saveSettings(values);
    message.success('设置已保存');
  };

  return (
    <div style={{ padding: isMobile ? 12 : 24, maxWidth: 800, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          设置
        </Title>
        <Text type="secondary" style={{ marginTop: 4, display: 'block', fontSize: 14 }}>
          配置 LLM 连接参数以启用 AI 功能
        </Text>
      </div>

      <Card
        style={{
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        {!hasSettings && (
          <Alert
            message="尚未配置"
            description="请填写以下 LLM 连接参数以启用 AI 功能。配置后会自动保存在本地浏览器中。"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={handleFinish}
        >
          <Form.Item
            name="llmProvider"
            label="LLM Provider"
            rules={[{ required: true, message: '请选择 LLM 提供商' }]}
          >
            <Select options={providerOptions} placeholder="选择 LLM 提供商" />
          </Form.Item>

          <Form.Item
            name="apiBaseUrl"
            label="API Base URL"
            rules={[{ required: true, message: '请输入 API 地址' }]}
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item
            name="apiKey"
            label="API Key"
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Divider style={{ margin: '16px 0' }} />

          <Form.Item
            name="debugMode"
            label="Debug Mode"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Divider style={{ margin: '16px 0' }} />

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit">
                保存设置
              </Button>
              <Button onClick={handleTestConnection} loading={testing} disabled={testing}>
                测试连接
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
