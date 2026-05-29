import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Button, Card, Col, Row, Spin, Statistic, Table, Tag, Typography,
} from 'antd';
import {
  BranchesOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
  PieChartOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RightOutlined,
  RocketOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { executionApi, workflowApi } from '@/api/client';
import { useAuthStore } from '@/store/authStore';
import type { Execution, Workflow } from '@/types';
import { useMediaQuery } from '@/hooks/useMediaQuery';

const { Title, Text } = Typography;

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return '--';
  const d = new Date(dateStr);
  const y = d.getFullYear();
  const M = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${y}-${M}-${day} ${h}:${m}`;
}

const statusColors: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  success: 'success',
  failed: 'error',
  paused: 'warning',
  cancelled: 'default',
};

const statusLabels: Record<string, string> = {
  pending: '待执行',
  running: '运行中',
  success: '成功',
  failed: '失败',
  paused: '已暂停',
  cancelled: '已取消',
};

/** Compute success rate across a list of executions. */
function computeSuccessRate(executions: Execution[]): number {
  if (executions.length === 0) return 0;
  const completed = executions.filter(
    (e) => e.status === 'success' || e.status === 'failed',
  );
  if (completed.length === 0) return 0;
  const succeeded = completed.filter((e) => e.status === 'success').length;
  return Math.round((succeeded / completed.length) * 100);
}

/** Count executions started in the last N hours. */
function countRecent(executions: Execution[], hours = 24): number {
  const cutoff = Date.now() - hours * 60 * 60 * 1000;
  return executions.filter((e) => {
    if (!e.started_at) return false;
    return new Date(e.started_at).getTime() > cutoff;
  }).length;
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery('(max-width: 768px)');
  const user = useAuthStore((s) => s.user);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [wfData, execData] = await Promise.all([
        workflowApi.list(),
        executionApi.list(100),
      ]);
      setWorkflows(wfData);
      setExecutions(execData);
    } catch (err) {
      setError('加载仪表盘数据失败，请稍后重试');
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Derived data ──────────────────────────────────────────────────────────

  const totalWorkflows = workflows.length;
  const totalExecutions = executions.length;
  const successRate = useMemo(() => computeSuccessRate(executions), [executions]);
  const recentActivity = useMemo(() => countRecent(executions, 24), [executions]);

  // Last 10 executions sorted by started_at desc
  const recentExecutions = useMemo(
    () =>
      [...executions]
        .sort(
          (a, b) =>
            new Date(b.started_at ?? 0).getTime() -
            new Date(a.started_at ?? 0).getTime(),
        )
        .slice(0, 10),
    [executions],
  );

  // Last 5 workflows sorted by created_at desc
  const recentWorkflows = useMemo(
    () =>
      [...workflows]
        .sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )
        .slice(0, 5),
    [workflows],
  );

  // Build a workflow-name lookup for execution rows
  const wfNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const wf of workflows) {
      map[wf.id] = wf.name;
    }
    return map;
  }, [workflows]);

  // ── Table columns ─────────────────────────────────────────────────────────

  const executionColumns = [
    {
      title: '工作流',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      ellipsis: true,
      render: (wfId: string, record: Execution) => (
        <a onClick={() => navigate(`/workflows/${wfId}`)}>
          {wfNameMap[wfId] || wfId.substring(0, 12)}
        </a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: string) => (
        <Tag color={statusColors[status] || 'default'}>
          {statusLabels[status] || status}
        </Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 170,
      render: (val: string | undefined | null) => (
        <Text type="secondary" style={{ fontSize: 13 }}>
          {formatDate(val)}
        </Text>
      ),
    },
    {
      title: '完成时间',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 170,
      render: (val: string | undefined | null) => (
        <Text type="secondary" style={{ fontSize: 13 }}>
          {formatDate(val)}
        </Text>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 50,
      render: (_: unknown, record: Execution) => (
        <Button
          type="link"
          size="small"
          icon={<RightOutlined />}
          onClick={() => navigate(`/executions/${record.id}`)}
        />
      ),
    },
  ];

  // ── Stat card config ──────────────────────────────────────────────────────

  const statCards = [
    {
      icon: <BranchesOutlined />,
      color: '#4f6ef7',
      title: '工作流总数',
      value: totalWorkflows,
    },
    {
      icon: <PlayCircleOutlined />,
      color: '#52c41a',
      title: '总执行次数',
      value: totalExecutions,
    },
    {
      icon: <CheckCircleOutlined />,
      color: '#faad14',
      title: '成功率',
      value: `${successRate}%`,
    },
    {
      icon: <ClockCircleOutlined />,
      color: '#eb2f96',
      title: '24h 活跃',
      value: recentActivity,
    },
  ];

  // ── Quick action cards ────────────────────────────────────────────────────

  const quickActions = [
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

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: isMobile ? 12 : 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0, color: 'var(--text-primary)' }}>
            总览
          </Title>
          {user && (
            <Text type="secondary" style={{ fontSize: 14, marginTop: 4, display: 'block' }}>
              欢迎回来，{user.username}
            </Text>
          )}
        </div>
        <Button
          type="primary"
          icon={<RocketOutlined />}
          size="large"
          onClick={() => navigate('/workflows/new')}
        >
          新建工作流
        </Button>
      </div>

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

        {/* ── Row 1: Statistics cards ── */}
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {statCards.map((card, i) => (
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
                      {card.title}
                    </span>
                  }
                  value={card.value}
                  prefix={
                    <span style={{ color: card.color, marginRight: 6 }}>
                      {card.icon}
                    </span>
                  }
                  valueStyle={{ color: 'var(--text-primary)', fontSize: 28 }}
                  suffix={i === 2 ? <PieChartOutlined style={{ fontSize: 16, opacity: 0.5 }} /> : undefined}
                />
              </Card>
            </Col>
          ))}
        </Row>

        {/* ── Row 2: Quick actions ── */}
        <Title level={4} style={{ marginBottom: 16, color: 'var(--text-primary)' }}>
          快速开始
        </Title>
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {quickActions.map((item) => (
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
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {item.desc}
                </Text>
              </Card>
            </Col>
          ))}
        </Row>

        {/* ── Row 3: Recent executions ── */}
        <Title level={4} style={{ marginBottom: 16, color: 'var(--text-primary)' }}>
          最近执行
        </Title>
        <Card
          style={{
            borderRadius: 8,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            marginBottom: 32,
          }}
          styles={{ body: { padding: 0 } }}
        >
          {recentExecutions.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '48px 24px',
              }}
            >
              <CloseCircleOutlined
                style={{ fontSize: 40, color: 'var(--text-secondary)', marginBottom: 12 }}
              />
              <Text type="secondary">暂无执行记录</Text>
              <Button
                type="link"
                icon={<PlusOutlined />}
                onClick={() => navigate('/workflows')}
                style={{ marginTop: 8 }}
              >
                去创建工作流
              </Button>
            </div>
          ) : (
            <Table
              dataSource={recentExecutions}
              columns={executionColumns}
              rowKey="id"
              pagination={false}
              size="middle"
              locale={{ emptyText: '暂无执行记录' }}
              onRow={(record) => ({
                onClick: () => navigate(`/executions/${record.id}`),
                style: { cursor: 'pointer' },
              })}
            />
          )}
        </Card>

        {/* ── Row 4: Recent workflows ── */}
        <Title level={4} style={{ marginBottom: 16, color: 'var(--text-primary)' }}>
          最近工作流
        </Title>
        {recentWorkflows.length === 0 ? (
          <div
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
            <FileTextOutlined
              style={{ fontSize: 40, color: 'var(--text-secondary)', marginBottom: 12 }}
            />
            <Text type="secondary">暂无工作流</Text>
            <Button
              type="link"
              icon={<PlusOutlined />}
              onClick={() => navigate('/workflows/new')}
              style={{ marginTop: 8 }}
            >
              创建工作流
            </Button>
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
                    <BranchesOutlined style={{ color: '#4f6ef7', fontSize: 16 }} />
                  </div>
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
                      style={{ fontSize: 12, color: 'var(--text-secondary)' }}
                    >
                      {formatDate(wf.created_at)}
                    </Text>
                  </div>
                  {/* Show node count */}
                  <Tag style={{ flexShrink: 0 }}>{wf.nodes.length} 节点</Tag>
                </div>
                <RightOutlined
                  style={{ color: 'var(--text-secondary)', fontSize: 12, flexShrink: 0 }}
                />
              </div>
            ))}
          </Card>
        )}
      </Spin>
    </div>
  );
}
