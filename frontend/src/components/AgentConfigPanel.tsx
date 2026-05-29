import { useEffect, useState } from 'react';
import {
  Radio,
  Select,
  Slider,
  Button,
  Card,
  Tag,
  Typography,
  Space,
  Popconfirm,
  Empty,
  Divider,
  Spin,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  TeamOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { agentApi } from '@/api/client';
import AgentSelector from './AgentSelector';
import type { AgentConfig, AgentTeamMember, MultiAgentMode, AgentRole } from '@/types';

const { Text, Title } = Typography;

interface AgentConfigPanelProps {
  mode?: MultiAgentMode;
  team?: AgentTeamMember[];
  defaultRole?: AgentRole;
  onChange: (config: {
    mode?: MultiAgentMode;
    team?: AgentTeamMember[];
    defaultRole?: AgentRole;
  }) => void;
}

const multiAgentModeOptions = [
  {
    value: 'pipeline' as MultiAgentMode,
    label: '流水线 (Pipeline)',
    description: '多个 Agent 按顺序依次执行，前一个 Agent 的输出作为后一个的输入',
  },
  {
    value: 'parallel' as MultiAgentMode,
    label: '并行 (Parallel)',
    description: '多个 Agent 同时独立执行同一任务，结果汇总合并',
  },
  {
    value: 'debate' as MultiAgentMode,
    label: '辩论 (Debate)',
    description: '多个 Agent 进行多轮讨论，通过辩论达成共识',
  },
];

const agentRoleOptions: { value: AgentRole; label: string }[] = [
  { value: 'planner', label: '规划者 (Planner)' },
  { value: 'executor', label: '执行者 (Executor)' },
  { value: 'reviewer', label: '审查者 (Reviewer)' },
  { value: 'observer', label: '观察者 (Observer)' },
];

const roleColors: Record<string, string> = {
  planner: 'blue',
  executor: 'green',
  reviewer: 'orange',
  observer: 'purple',
};

export default function AgentConfigPanel({
  mode,
  team = [],
  defaultRole = 'executor',
  onChange,
}: AgentConfigPanelProps) {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  // Fetch available agents
  useEffect(() => {
    setAgentsLoading(true);
    setAgentsError(null);
    agentApi
      .list()
      .then((data) => setAgents(data))
      .catch((err) => setAgentsError(err?.message || '加载失败'))
      .finally(() => setAgentsLoading(false));
  }, []);

  const handleModeChange = (newMode: MultiAgentMode) => {
    onChange({ mode: newMode, team, defaultRole });
  };

  const handleAddAgent = () => {
    if (!selectedAgentId) return;
    const agent = agents.find((a) => a.id === selectedAgentId);
    if (!agent) return;
    if (team.some((m) => m.agent_id === selectedAgentId)) return;

    const newMember: AgentTeamMember = {
      agent_id: agent.id,
      agent_name: agent.name,
      role: defaultRole,
      temperature: 0.7,
    };

    onChange({ mode, team: [...team, newMember], defaultRole });
    setSelectedAgentId(null);
  };

  const handleRemoveAgent = (agentId: string) => {
    onChange({ mode, team: team.filter((m) => m.agent_id !== agentId), defaultRole });
  };

  const handleUpdateMember = (
    agentId: string,
    field: keyof AgentTeamMember,
    value: string | number,
  ) => {
    onChange({
      mode,
      team: team.map((m) =>
        m.agent_id === agentId ? { ...m, [field]: value } : m,
      ),
      defaultRole,
    });
  };

  const handleDefaultRoleChange = (newRole: AgentRole) => {
    onChange({ mode, team, defaultRole: newRole });
  };

  const availableAgents = agents.filter(
    (a) => !team.some((m) => m.agent_id === a.id),
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Section: Multi-Agent Mode ── */}
      <div>
        <Text
          strong
          style={{
            fontSize: 13,
            display: 'block',
            marginBottom: 8,
            color: 'var(--text-primary)',
          }}
        >
          <SettingOutlined style={{ marginRight: 6 }} />
          多智能体模式
        </Text>
        <Radio.Group
          value={mode}
          onChange={(e) => handleModeChange(e.target.value)}
          style={{ width: '100%' }}
        >
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            {multiAgentModeOptions.map((opt) => (
              <div
                key={opt.value}
                style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: `1px solid ${
                    mode === opt.value ? 'var(--border-color)' : 'var(--border-color)'
                  }`,
                  background:
                    mode === opt.value
                      ? 'var(--bg-canvas)'
                      : 'transparent',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onClick={() => handleModeChange(opt.value)}
              >
                <Radio value={opt.value}>
                  <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--text-primary)' }}>
                    {opt.label}
                  </span>
                </Radio>
                <Text
                  type="secondary"
                  style={{
                    display: 'block',
                    marginTop: 2,
                    marginLeft: 24,
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                  }}
                >
                  {opt.description}
                </Text>
              </div>
            ))}
          </Space>
        </Radio.Group>
      </div>

      <Divider style={{ margin: '4px 0' }} />

      {/* ── Section: Agent Team ── */}
      <div>
        <Text
          strong
          style={{
            fontSize: 13,
            display: 'block',
            marginBottom: 8,
            color: 'var(--text-primary)',
          }}
        >
          <TeamOutlined style={{ marginRight: 6 }} />
          智能体团队
        </Text>

        {agentsLoading ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <Spin size="small" />
            <Text
              type="secondary"
              style={{ display: 'block', marginTop: 4, fontSize: 12 }}
            >
              加载智能体列表...
            </Text>
          </div>
        ) : agentsError ? (
          <Text type="danger" style={{ fontSize: 12 }}>
            加载失败: {agentsError}
          </Text>
        ) : team.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Text type="secondary" style={{ fontSize: 12 }}>
                暂未添加智能体
              </Text>
            }
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {team.map((member) => {
              const agentInfo = agents.find(
                (a) => a.id === member.agent_id,
              );
              return (
                <Card
                  key={member.agent_id}
                  size="small"
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 6,
                  }}
                  styles={{
                    body: { padding: '10px 12px' },
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: 8,
                    }}
                  >
                    <Space size={6}>
                      <Tag color="blue" style={{ marginRight: 0 }}>
                        {member.agent_name}
                      </Tag>
                      <Tag
                        color={roleColors[member.role] || 'default'}
                        style={{ marginRight: 0, fontSize: 11 }}
                      >
                        {member.role}
                      </Tag>
                    </Space>
                    <Popconfirm
                      title="确认移除该智能体？"
                      onConfirm={() => handleRemoveAgent(member.agent_id)}
                      okText="确认"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                      />
                    </Popconfirm>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    {/* Role selector */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <Text
                        type="secondary"
                        style={{
                          fontSize: 12,
                          minWidth: 40,
                          color: 'var(--text-secondary)',
                        }}
                      >
                        角色
                      </Text>
                      <Select
                        size="small"
                        value={member.role}
                        onChange={(v) =>
                          handleUpdateMember(
                            member.agent_id,
                            'role',
                            v as AgentRole,
                          )
                        }
                        style={{ flex: 1 }}
                        options={agentRoleOptions}
                      />
                    </div>

                    {/* Model display */}
                    {agentInfo?.model_name || agentInfo?.model ? (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                        }}
                      >
                        <Text
                          type="secondary"
                          style={{
                            fontSize: 12,
                            minWidth: 40,
                            color: 'var(--text-secondary)',
                          }}
                        >
                          模型
                        </Text>
                        <Tag
                          style={{
                            fontSize: 11,
                            margin: 0,
                          }}
                        >
                          {agentInfo.model_name || agentInfo.model}
                        </Tag>
                      </div>
                    ) : null}

                    {/* Temperature slider */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <Text
                        type="secondary"
                        style={{
                          fontSize: 12,
                          minWidth: 40,
                          color: 'var(--text-secondary)',
                        }}
                      >
                        Temperature
                      </Text>
                      <Slider
                        size="small"
                        min={0}
                        max={2}
                        step={0.1}
                        value={member.temperature}
                        onChange={(v) =>
                          handleUpdateMember(
                            member.agent_id,
                            'temperature',
                            v,
                          )
                        }
                        style={{ flex: 1, margin: '0 4px' }}
                        tooltip={{ formatter: (v) => v?.toFixed(1) }}
                      />
                      <Text
                        style={{
                          fontSize: 11,
                          minWidth: 24,
                          textAlign: 'right',
                          color: 'var(--text-secondary)',
                        }}
                      >
                        {member.temperature.toFixed(1)}
                      </Text>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Add agent button */}
        {availableAgents.length > 0 && (
          <div
            style={{
              display: 'flex',
              gap: 8,
              marginTop: 10,
            }}
          >
            <Select
              size="small"
              showSearch
              placeholder="选择智能体添加"
              value={selectedAgentId}
              onChange={setSelectedAgentId}
              style={{ flex: 1 }}
              optionFilterProp="label"
              options={availableAgents.map((a) => ({
                label: `${a.name} (${a.role})`,
                value: a.id,
              }))}
            />
            <Button
              size="small"
              type="primary"
              icon={<PlusOutlined />}
              disabled={!selectedAgentId}
              onClick={handleAddAgent}
            >
              添加
            </Button>
          </div>
        )}
      </div>

      <Divider style={{ margin: '4px 0' }} />

      {/* ── Section: Default Agent Role ── */}
      <div>
        <Text
          strong
          style={{
            fontSize: 13,
            display: 'block',
            marginBottom: 8,
            color: 'var(--text-primary)',
          }}
        >
          默认 Agent 角色
        </Text>
        <Select
          value={defaultRole}
          onChange={handleDefaultRoleChange}
          style={{ width: '100%' }}
          options={agentRoleOptions}
        />
        <Text
          type="secondary"
          style={{
            display: 'block',
            marginTop: 4,
            fontSize: 11,
            color: 'var(--text-secondary)',
          }}
        >
          新添加的智能体将默认使用此角色
        </Text>
      </div>
    </div>
  );
}
