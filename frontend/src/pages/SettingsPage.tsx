import { useState, useCallback } from 'react';
import { Alert, Button, Card, Form, Input, message, Select, Switch, Typography, Space, Divider } from 'antd';
import { SettingOutlined, GlobalOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useLanguage } from '@/i18n/useLanguage';

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
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [testing, setTesting] = useState(false);
  const isMobile = useMediaQuery('(max-width: 768px)');
  const { currentLang, switchLanguage } = useLanguage();

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
      message.success(t('settings.connectionSuccess'));
    } catch {
      message.error(t('settings.connectionFailed'));
    } finally {
      setTesting(false);
    }
  }, [form]);

  const handleFinish = (values: SettingsValues) => {
    saveSettings(values);
    message.success(t('settings.saved'));
  };

  return (
    <div style={{ padding: isMobile ? 12 : 24, maxWidth: 800, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          {t('settings.title')}
        </Title>
        <Text type="secondary" style={{ marginTop: 4, display: 'block', fontSize: 14 }}>
          {t('settings.subtitle')}
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
            message={t('settings.notConfigured')}
            description={t('settings.notConfiguredDesc')}
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
            label={t('settings.llmProvider')}
            rules={[{ required: true, message: t('settings.providerRequired') }]}
          >
            <Select options={providerOptions} placeholder={t('settings.selectProvider')} />
          </Form.Item>

          <Form.Item
            name="apiBaseUrl"
            label={t('settings.apiBaseUrl')}
            rules={[{ required: true, message: t('settings.apiBaseUrlRequired') }]}
          >
            <Input placeholder={t('settings.apiBaseUrlPlaceholder')} />
          </Form.Item>

          <Form.Item
            name="apiKey"
            label={t('settings.apiKey')}
            rules={[{ required: true, message: t('settings.apiKeyRequired') }]}
          >
            <Input.Password placeholder={t('settings.apiKeyPlaceholder')} />
          </Form.Item>

          <Divider style={{ margin: '16px 0' }} />

          <Form.Item
            name="debugMode"
            label={t('settings.debugMode')}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Divider style={{ margin: '16px 0' }} />

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit">
                {t('settings.save')}
              </Button>
              <Button onClick={handleTestConnection} loading={testing} disabled={testing}>
                {t('settings.test')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {/* Language settings */}
      <Card
        style={{
          marginTop: 16,
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>
              {t('settings.language')}
            </Text>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {currentLang === 'zh' ? '简体中文' : 'English'}
            </Text>
          </div>
          <Select
            value={currentLang}
            onChange={(value) => switchLanguage(value as 'zh' | 'en')}
            style={{ width: 140 }}
            options={[
              { value: 'zh', label: '中文' },
              { value: 'en', label: 'English' },
            ]}
          />
        </div>
      </Card>
    </div>
  );
}
