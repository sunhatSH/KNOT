import { useEffect, useState } from 'react';
import { Select, Spin, Tag, Typography, Empty, Alert } from 'antd';
import { agentApi } from '@/api/client';
import type { AgentConfig } from '@/types';

const { Text } = Typography;

interface AgentSelectorProps {
  value?: string[];
  onChange?: (agentIds: string[]) => void;
  placeholder?: string;
  style?: React.CSSProperties;
}

const roleColors: Record<string, string> = {
  planner: 'blue',
  executor: 'green',
  researcher: 'purple',
  coder: 'cyan',
  validator: 'orange',
  summarizer: 'geekblue',
};

export default function AgentSelector({
  value,
  onChange,
  placeholder = '选择智能体',
  style,
}: AgentSelectorProps) {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    agentApi
      .list()
      .then((data) => {
        if (!cancelled) setAgents(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || '加载智能体列表失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '12px 0' }}>
        <Spin size="small" />
        <Text type="secondary" style={{ display: 'block', marginTop: 4, fontSize: 12 }}>
          加载智能体列表...
        </Text>
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
        style={{ marginBottom: 8, fontSize: 12 }}
      />
    );
  }

  if (agents.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <Text type="secondary" style={{ fontSize: 12 }}>
            暂无已注册的智能体，请先在后台注册
          </Text>
        }
      />
    );
  }

  return (
    <Select
      mode="multiple"
      allowClear
      showSearch
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      style={{ width: '100%', ...style }}
      optionFilterProp="label"
      maxTagCount={3}
      maxTagTextLength={8}
      options={agents.map((agent) => ({
        label: agent.name,
        value: agent.id,
        agent,
      }))}
      optionRender={(option) => {
        const agent = option.data.agent as AgentConfig;
        return (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '2px 0',
            }}
          >
            <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
              {agent.name}
            </span>
            <Tag
              color={roleColors[agent.role] || 'default'}
              style={{ marginRight: 0, fontSize: 11, lineHeight: '18px' }}
            >
              {agent.role}
            </Tag>
            <Text
              type="secondary"
              style={{
                fontSize: 11,
                marginLeft: 'auto',
                color: 'var(--text-secondary)',
              }}
            >
              {agent.model_name || agent.model}
            </Text>
          </div>
        );
      }}
    />
  );
}
