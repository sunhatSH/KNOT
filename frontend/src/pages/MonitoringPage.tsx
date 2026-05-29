import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Card, Col, Row, Statistic, Table, Spin, Alert, Tag, Typography,
  Switch, Space, Empty, Button,
} from 'antd';
import {
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  MinusCircleOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { metricsApi, type DashboardMetrics } from '@/api/client';

const { Title, Text } = Typography;

// ─── Colour palette ──────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  success: '#52c41a',
  failed: '#ff4d4f',
  running: '#1890ff',
  pending: '#faad14',
  paused: '#722ed1',
  cancelled: '#8c8c8c',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  success: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
  running: <PlayCircleOutlined />,
  pending: <ClockCircleOutlined />,
  paused: <PauseCircleOutlined />,
  cancelled: <MinusCircleOutlined />,
};

// ─── Helper components ───────────────────────────────────────────────────────

function StatusTag({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || '#8c8c8c';
  const icon = STATUS_ICONS[status] || null;
  return (
    <Tag icon={icon} color={color} style={{ textTransform: 'capitalize' }}>
      {status}
    </Tag>
  );
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

// ─── Inline bar chart for daily executions ───────────────────────────────────

function DailyBarChart({ data }: { data: { date: string; count: number }[] }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 160, padding: '8px 0' }}>
      {data.map((day) => {
        const pct = (day.count / maxCount) * 100;
        const label = day.date.slice(5); // MM-DD
        return (
          <div
            key={day.date}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              height: '100%',
              justifyContent: 'flex-end',
            }}
          >
            <Text style={{ fontSize: 11, marginBottom: 2 }}>
              {day.count}
            </Text>
            <div
              style={{
                width: '100%',
                maxWidth: 40,
                height: `${Math.max(pct, 4)}%`,
                background: 'linear-gradient(180deg, #4f6ef7 0%, #7b93f5 100%)',
                borderRadius: '4px 4px 0 0',
                transition: 'height 0.3s',
                minHeight: 4,
              }}
            />
            <Text style={{ fontSize: 10, marginTop: 4, color: '#8c8c8c' }}>
              {label}
            </Text>
          </div>
        );
      })}
    </div>
  );
}

// ─── Status breakdown bar (horizontal stacked) ───────────────────────────────

function StatusBreakdown({ counts }: { counts: Record<string, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '24px 0' }}>
        <Text type="secondary">No executions yet</Text>
      </div>
    );
  }

  const statusOrder = ['success', 'failed', 'running', 'pending', 'paused', 'cancelled'];
  const segments = statusOrder
    .filter((s) => (counts[s] || 0) > 0)
    .map((s) => ({
      status: s,
      count: counts[s] || 0,
      pct: ((counts[s] || 0) / total) * 100,
      color: STATUS_COLORS[s] || '#8c8c8c',
    }));

  return (
    <div>
      <div
        style={{
          display: 'flex',
          height: 24,
          borderRadius: 12,
          overflow: 'hidden',
          marginBottom: 12,
        }}
      >
        {segments.map((seg) => (
          <div
            key={seg.status}
            style={{
              width: `${seg.pct}%`,
              minWidth: seg.pct > 0 ? 4 : 0,
              background: seg.color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              color: '#fff',
              fontWeight: 600,
            }}
            title={`${seg.status}: ${seg.count}`}
          >
            {seg.pct > 8 ? seg.count : ''}
          </div>
        ))}
      </div>
      <Row gutter={[8, 8]}>
        {segments.map((seg) => (
          <Col key={seg.status} span={8}>
            <Space size={4}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 4,
                  background: seg.color,
                  display: 'inline-block',
                }}
              />
              <Text style={{ fontSize: 12, textTransform: 'capitalize' }}>
                {seg.status}
              </Text>
              <Text style={{ fontSize: 12, fontWeight: 600 }}>{seg.count}</Text>
            </Space>
          </Col>
        ))}
      </Row>
    </div>
  );
}

// ─── Main page component ─────────────────────────────────────────────────────

export default function MonitoringPage() {
  const [data, setData] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---- Data fetching ----
  const fetchMetrics = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const result = await metricsApi.dashboard();
      setData(result);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load dashboard metrics';
      setError(msg);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchMetrics(true);
  }, [fetchMetrics]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => fetchMetrics(), 30_000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoRefresh, fetchMetrics]);

  // ---- Recent executions columns ----
  const recentColumns = [
    {
      title: 'Time',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string | null) => formatTime(v),
      width: 180,
    },
    {
      title: 'Workflow ID',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      ellipsis: true,
      render: (v: string) => (
        <Text copyable={{ text: v }} style={{ fontFamily: 'monospace', fontSize: 12 }}>
          {v.length > 20 ? `${v.slice(0, 20)}...` : v}
        </Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <StatusTag status={v} />,
      width: 120,
    },
    {
      title: 'Duration',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      render: (v: number | null) => formatDuration(v),
      width: 100,
    },
    {
      title: 'Error',
      dataIndex: 'error',
      key: 'error',
      ellipsis: true,
      render: (v: string | null) =>
        v ? (
          <Text type="danger" style={{ fontSize: 12 }}>
            {v.length > 50 ? `${v.slice(0, 50)}...` : v}
          </Text>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
  ];

  // ---- Slow nodes columns ----
  const slowNodeColumns = [
    {
      title: 'Node',
      dataIndex: 'node_label',
      key: 'node_label',
      ellipsis: true,
    },
    {
      title: 'Avg Duration',
      dataIndex: 'avg_duration_ms',
      key: 'avg_duration_ms',
      render: (v: number) => formatDuration(v),
      width: 140,
      sorter: (a: any, b: any) => a.avg_duration_ms - b.avg_duration_ms,
    },
    {
      title: 'Total',
      dataIndex: 'total_ms',
      key: 'total_ms',
      render: (v: number) => formatDuration(v),
      width: 120,
    },
    {
      title: 'Calls',
      dataIndex: 'count',
      key: 'count',
      width: 80,
    },
  ];

  // ---- Render ----
  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <BarChartOutlined style={{ marginRight: 8 }} />
            Monitoring Dashboard
          </Title>
        </Col>
        <Col>
          <Space size={16}>
            <Space size={8}>
              <Text style={{ fontSize: 13 }}>Auto-refresh (30s)</Text>
              <Switch
                checked={autoRefresh}
                onChange={setAutoRefresh}
                size="small"
              />
            </Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => fetchMetrics(true)}
              loading={loading}
            >
              Refresh
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Error */}
      {error && (
        <Alert
          message="Failed to load metrics"
          description={error}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={() => fetchMetrics(true)}>
              Retry
            </Button>
          }
        />
      )}

      {/* Loading */}
      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">Loading dashboard metrics...</Text>
          </div>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && data && data.total_executions === 0 && (
        <Card>
          <Empty
            description="No execution data available yet. Run a workflow to see metrics."
            style={{ padding: '40px 0' }}
          />
        </Card>
      )}

      {/* Dashboard content */}
      {data && data.total_executions >= 0 && (
        <>
          {/* ── Stats cards ─────────────────────────────────────────────── */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={12} sm={12} md={6}>
              <Card hoverable>
                <Statistic
                  title="Total Executions"
                  value={data.total_executions}
                  prefix={<PlayCircleOutlined style={{ color: '#4f6ef7' }} />}
                  valueStyle={{ color: '#4f6ef7' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={12} md={6}>
              <Card hoverable>
                <Statistic
                  title="Success Rate"
                  value={data.success_rate}
                  suffix="%"
                  precision={1}
                  prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={12} md={6}>
              <Card hoverable>
                <Statistic
                  title="Avg Duration"
                  value={data.avg_duration_ms != null ? formatDuration(data.avg_duration_ms) : '-'}
                  prefix={<ClockCircleOutlined style={{ color: '#faad14' }} />}
                  valueStyle={{ color: '#faad14', fontSize: 24 }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={12} md={6}>
              <Card hoverable>
                <Statistic
                  title="Failed"
                  value={data.execution_counts?.failed || 0}
                  prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Card>
            </Col>
          </Row>

          {/* ── Status breakdown + Daily trend ──────────────────────────── */}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} md={12}>
              <Card title="Execution Status Breakdown" size="small">
                {data.total_executions > 0 ? (
                  <StatusBreakdown counts={data.execution_counts} />
                ) : (
                  <Empty description="No data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card title="Executions (Last 7 Days)" size="small">
                {data.total_executions > 0 ? (
                  <DailyBarChart data={data.executions_by_day} />
                ) : (
                  <Empty description="No data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
          </Row>

          {/* ── Recent executions table ─────────────────────────────────── */}
          <Card
            title="Recent Executions"
            size="small"
            style={{ marginBottom: 24 }}
          >
            {data.recent_executions.length > 0 ? (
              <Table
                dataSource={data.recent_executions}
                columns={recentColumns}
                rowKey="id"
                pagination={false}
                size="small"
                scroll={{ x: 700 }}
              />
            ) : (
              <Empty description="No recent executions" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          {/* ── Slowest nodes table ─────────────────────────────────────── */}
          <Card title="Slowest Nodes (Top 5)" size="small">
            {data.top_slow_nodes.length > 0 ? (
              <Table
                dataSource={data.top_slow_nodes}
                columns={slowNodeColumns}
                rowKey="node_id"
                pagination={false}
                size="small"
              />
            ) : (
              <Empty
                description="No node timing data available"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
