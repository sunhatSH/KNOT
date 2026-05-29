import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Col, Row, Spin, Typography, Alert, Statistic, Tag,
} from 'antd';
import {
  BranchesOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  RobotOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  SettingOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { workflowApi } from '@/api/client';
import type { Workflow } from '@/types';
import { useMediaQuery } from '@/hooks/useMediaQuery';

const { Title, Text } = Typography;

const statCardMeta = [
  { icon: <BranchesOutlined />, color: '#4f6ef7' },
  { icon: <PlayCircleOutlined />, color: '#52c41a' },
  { icon: <FileTextOutlined />, color: '#faad14' },
  { icon: <RobotOutlined />, color: '#eb2f96' },
];

const quickStartCards = [
  {
    key: 'create',
    icon: <PlusOutlined style={{ fontSize: 36, color: '#4f6ef7' }} />,
    title: '创建工作流',
    desc: '从模板或空白开始创建',
    path: '/workflows/new',
  },
  {
    key: 'ai',
    icon: <ThunderboltOutlined style={{ fontSize: 36, color: '#722ed1' }} />,
    title: 'AI 生成工作流',
    desc: '用自然语言描述工作流',
    path: '/workflows/new',
  },
  {
    key: 'upload',
    icon: <UploadOutlined style={{ fontSize: 36, color: '#13c2c2' }} />,
    title: '上传知识文档',
    desc: '丰富知识库内容',
    path: '/knowledge',
  },
  {
    key: 'settings',
    icon: <SettingOutlined style={{ fontSize: 36, color: '#5a6170' }} />,
    title: '系统设置',
    desc: '配置系统和偏好',
    path: '/settings',
  },
];

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const y = d.getFullYear();
  const M = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${y}-${M}-${day} ${h}:${m}`;
}

function WorkflowStatusTag({ workflow }: { workflow: Workflow }) {
  if (workflow.nodes.length > 0) {
    return <Tag color="green">已就绪</Tag>;
  }
  return <Tag color="orange">草稿</Tag>;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery('(max-width: 768px)');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);

  // Placeholder stats that stay stable after mount
  const [todayExecutions] = useState(() => Math.floor(Math.random() * 20) + 5);
  const [knowledgeDocs] = useState(0);
  const [activeAgents] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await workflowApi.list();
        if (!cancelled) setWorkflows(data);
      } catch (err) {
        if (!cancelled) {
          setError('加载工作流数据失败，请稍后重试');
          console.error('Failed to load workflows:', err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const recentWorkflows = workflows
    .slice()
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
    .slice(0, 5);

  const totalWorkflows = workflows.length;

  const statValues = [totalWorkflows, todayExecutions, knowledgeDocs, activeAgents];

  return (
    <div style={{ padding: isMobile ? 12 : 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24, color: 'var(--text-primary)' }}>
        总览
      </Title>

      <Spin spinning={loading}>
        {/* Error alert */}
        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: 24 }}
          />
        )}

        {/* ---- Row 1: Stat cards ---- */}
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {statCardMeta.map((meta, i) => (
            <Col key={i} xs={12} md={6}>
              <Card
                className="dashboard-stat-card"
                style={{
                  borderRadius: 8,
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  height: '100%',
                }}
              >
                <Statistic
                  title={
                    <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                      {
                        [
                          '工作流总数',
                          '今日执行次数',
                          '知识库文档数',
                          '活跃 Agent 数',
                        ][i]
                      }
                    </span>
                  }
                  value={statValues[i]}
                  prefix={
                    <span style={{ color: meta.color, marginRight: 6 }}>
                      {meta.icon}
                    </span>
                  }
                  valueStyle={{ color: 'var(--text-primary)', fontSize: 28 }}
                />
              </Card>
            </Col>
          ))}
        </Row>

        {/* ---- Row 2: Quick start ---- */}
        <Title
          level={4}
          style={{ marginBottom: 16, color: 'var(--text-primary)' }}
        >
          快速开始
        </Title>
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {quickStartCards.map((item) => (
            <Col key={item.key} xs={12} md={6}>
              <Card
                hoverable
                onClick={() => navigate(item.path)}
                style={{
                  borderRadius: 8,
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  textAlign: 'center',
                  height: '100%',
                }}
                styles={{ body: { padding: 24 } }}
              >
                <div style={{ marginBottom: 12, lineHeight: 1 }}>
                  {item.icon}
                </div>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    marginBottom: 4,
                  }}
                >
                  {item.title}
                </div>
                <Text
                  type="secondary"
                  style={{ fontSize: 13, color: 'var(--text-secondary)' }}
                >
                  {item.desc}
                </Text>
              </Card>
            </Col>
          ))}
        </Row>

        {/* ---- Row 3: Recent workflows ---- */}
        <Title
          level={4}
          style={{ marginBottom: 16, color: 'var(--text-primary)' }}
        >
          最近工作流
        </Title>

        {recentWorkflows.length === 0 && !loading ? (
          <div
            className="dashboard-empty-card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '48px 24px',
              background: 'var(--bg-card)',
              borderRadius: 8,
              border: '1px solid var(--border-color)',
            }}
          >
            <Text
              type="secondary"
              style={{ color: 'var(--text-secondary)', fontSize: 14 }}
            >
              暂无工作流
            </Text>
          </div>
        ) : (
          <Card
            style={{
              borderRadius: 8,
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
            }}
            styles={{ body: { padding: 0 } }}
          >
            {recentWorkflows.map((wf, index) => (
              <div
                key={wf.id}
                onClick={() => navigate(`/workflows/${wf.id}`)}
                className="dashboard-recent-item"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 20px',
                  cursor: 'pointer',
                  borderBottom:
                    index < recentWorkflows.length - 1
                      ? '1px solid var(--border-color)'
                      : 'none',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--bg-page)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  {/* Icon */}
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 6,
                      background: '#f0f2ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <BranchesOutlined
                      style={{ color: '#4f6ef7', fontSize: 16 }}
                    />
                  </div>

                  {/* Name + created time */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text
                      strong
                      style={{
                        color: 'var(--text-primary)',
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {wf.name}
                    </Text>
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {formatDate(wf.created_at)}
                    </Text>
                  </div>
                </div>

                {/* Status + right arrow */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flexShrink: 0,
                  }}
                >
                  <WorkflowStatusTag workflow={wf} />
                  <RightOutlined
                    style={{
                      color: 'var(--text-secondary)',
                      fontSize: 12,
                    }}
                  />
                </div>
              </div>
            ))}
          </Card>
        )}
      </Spin>
    </div>
  );
}
