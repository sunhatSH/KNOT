import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Spin, Tag, Typography, Timeline, Empty, Button, Descriptions, Collapse, Statistic, Row, Col,
} from 'antd';
import {
  ArrowLeftOutlined, LoadingOutlined,
  PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  MinusCircleOutlined, ToolOutlined, DatabaseOutlined, InfoCircleOutlined,
} from '@ant-design/icons';

import { executionApi } from '@/api/client';
import type { Execution, TraceEntry } from '@/types';

const { Title, Text } = Typography;

// ─── Status Config ──────────────────────────────────────────────────────

const statusConfig: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: '成功' },
  failed: { color: 'error', label: '失败' },
  running: { color: 'processing', label: '运行中' },
  pending: { color: 'default', label: '等待中' },
  paused: { color: 'warning', label: '已暂停' },
  cancelled: { color: 'default', label: '已取消' },
};

// ─── Event Type Config ──────────────────────────────────────────────────

const eventConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  node_start: { color: '#1677ff', icon: <PlayCircleOutlined />, label: '节点开始' },
  node_complete: { color: '#52c41a', icon: <CheckCircleOutlined />, label: '节点完成' },
  node_failed: { color: '#ff4d4f', icon: <CloseCircleOutlined />, label: '节点失败' },
  node_skipped: { color: '#8c8c8c', icon: <MinusCircleOutlined />, label: '节点跳过' },
  tool_call: { color: '#fa8c16', icon: <ToolOutlined />, label: '工具调用' },
  knowledge_retrieval: { color: '#722ed1', icon: <DatabaseOutlined />, label: '知识检索' },
  info: { color: '#1677ff', icon: <InfoCircleOutlined />, label: '信息' },
  error: { color: '#ff4d4f', icon: <CloseCircleOutlined />, label: '错误' },
};

const defaultEvent = { color: '#8c8c8c', icon: <InfoCircleOutlined />, label: '事件' };

// ─── Helpers ────────────────────────────────────────────────────────────

function formatDuration(start: string, end?: string): string {
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const diff = e - s;
  if (diff < 0) return '-';
  if (diff < 1000) return `${diff}ms`;
  if (diff < 60000) return `${Math.floor(diff / 1000)}s`;
  const m = Math.floor(diff / 60000);
  const sec = Math.floor((diff % 60000) / 1000);
  return `${m}m ${sec}s`;
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatMs(ms: number): string {
  if (ms < 1) return '<1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round(ms % 60000);
  return `${m}m ${s}s`;
}

function computeStats(execution: Execution): Record<string, unknown> {
  const stats: Record<string, unknown> = {};

  // Total duration
  if (execution.started_at) {
    const s = new Date(execution.started_at).getTime();
    const e = execution.completed_at ? new Date(execution.completed_at).getTime() : Date.now();
    stats.total_duration_ms = e - s;
  } else {
    stats.total_duration_ms = null;
  }

  // Node counts from node_states
  const nodeStates = execution.node_states || {};
  const states = Object.values(nodeStates).map(v => typeof v === 'string' ? v : String(v));
  stats.node_count = Object.keys(nodeStates).length;
  stats.completed_count = states.filter(s => s === 'success').length;
  stats.failed_count = states.filter(s => s === 'failed').length;
  stats.skipped_count = states.filter(s => s === 'skipped').length;

  // Duration from trace entries
  const trace = execution.trace || [];
  const nodeDurations: number[] = [];
  for (const entry of trace) {
    if (entry.event === 'node_complete' && entry.duration_ms != null) {
      nodeDurations.push(entry.duration_ms);
    }
  }
  if (nodeDurations.length > 0) {
    stats.avg_node_duration_ms = nodeDurations.reduce((a, b) => a + b, 0) / nodeDurations.length;
  } else {
    stats.avg_node_duration_ms = null;
  }

  return stats;
}

// ─── JSON Viewer ────────────────────────────────────────────────────────

function JsonViewer({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data, null, 2);

  const html = json
    .replace(
      /("(?:[^"\\]|\\.)*")\s*:/g,
      '<span style="color:#4f6ef7">$1</span>:',
    )
    .replace(
      /:\s*("(?:[^"\\]|\\.)*")/g,
      ': <span style="color:#52c41a">$1</span>',
    )
    .replace(
      /:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
      ': <span style="color:#fa8c16">$1</span>',
    )
    .replace(
      /:\s*(true|false)/g,
      ': <span style="color:#eb2f96">$1</span>',
    )
    .replace(
      /:\s*(null)/g,
      ': <span style="color:#999">$1</span>',
    );

  if (!json || json === '{}') {
    return <Text type="secondary">空</Text>;
  }

  return (
    <pre
      style={{
        background: '#f8f9fc',
        border: '1px solid #e8eaf0',
        borderRadius: 8,
        padding: 16,
        fontSize: 13,
        lineHeight: 1.6,
        overflow: 'auto',
        maxHeight: 400,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
        margin: 0,
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ─── Node Duration Bar ──────────────────────────────────────────────────

function DurationBar({ durationMs, maxMs }: { durationMs: number; maxMs: number }) {
  const pct = maxMs > 0 ? Math.min((durationMs / maxMs) * 100, 100) : 0;
  const color = durationMs > maxMs * 0.8 ? '#ff4d4f' : durationMs > maxMs * 0.5 ? '#fa8c16' : '#52c41a';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        style={{
          flex: 1,
          height: 8,
          background: '#f0f0f0',
          borderRadius: 4,
          overflow: 'hidden',
          maxWidth: 120,
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 4,
            transition: 'width 0.3s',
          }}
        />
      </div>
      <Text style={{ fontSize: 12, color, whiteSpace: 'nowrap' }}>
        {formatMs(durationMs)}
      </Text>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [execution, setExecution] = useState<Execution | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError('执行 ID 不能为空');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    executionApi
      .get(id)
      .then((data) => {
        setExecution(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err.response?.status === 404) {
          setError('未找到该执行记录');
        } else {
          setError(err.message || '加载执行详情失败');
        }
        setLoading(false);
      });
  }, [id]);

  /* ---- Loading state ---- */
  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '80vh',
        }}
      >
        <Spin size="large" indicator={<LoadingOutlined />} />
      </div>
    );
  }

  /* ---- Error state ---- */
  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          style={{ marginBottom: 16 }}
        >
          返回
        </Button>
        <Card
          style={{
            borderRadius: 8,
            border: '1px solid #e8eaf0',
          }}
        >
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Title level={4} type="danger">
              {error}
            </Title>
            <Text type="secondary">请确认执行 ID 是否正确</Text>
          </div>
        </Card>
      </div>
    );
  }

  /* ---- Null guard (should not reach here) ---- */
  if (!execution) return null;

  const statusInfo = statusConfig[execution.status] || {
    color: 'default',
    label: execution.status,
  };
  const duration = execution.started_at
    ? formatDuration(execution.started_at, execution.completed_at)
    : '-';

  // Compute statistics
  const stats = computeStats(execution);

  // Prepare timeline data: compute max duration for bar scaling
  const trace = execution.trace || [];
  const maxDuration = Math.max(
    ...trace.map((e: TraceEntry) => e.duration_ms ?? 0),
    1,
  );

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          执行详情
        </Title>
      </div>

      {/* ---- Statistics Summary Card ---- */}
      <Card
        style={{
          marginBottom: 16,
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={12} sm={6}>
            <Statistic
              title="总耗时"
              value={stats.total_duration_ms != null ? formatMs(stats.total_duration_ms as number) : '-'}
              valueStyle={{ fontSize: 20 }}
            />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic
              title="节点总数"
              value={stats.node_count as number}
              suffix={
                <span style={{ fontSize: 14 }}>
                  <Text style={{ color: '#52c41a', marginLeft: 8 }}>
                    {stats.completed_count as number} 成功
                  </Text>
                  {(stats.failed_count as number) > 0 && (
                    <Text style={{ color: '#ff4d4f', marginLeft: 8 }}>
                      {stats.failed_count as number} 失败
                    </Text>
                  )}
                  {(stats.skipped_count as number) > 0 && (
                    <Text style={{ color: '#8c8c8c', marginLeft: 8 }}>
                      {stats.skipped_count as number} 跳过
                    </Text>
                  )}
                </span>
              }
              valueStyle={{ fontSize: 20 }}
            />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic
              title="平均节点耗时"
              value={stats.avg_node_duration_ms != null ? formatMs(stats.avg_node_duration_ms as number) : '-'}
              valueStyle={{ fontSize: 20 }}
            />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic
              title="状态"
              valueRender={() => (
                <Tag color={statusInfo.color} style={{ fontSize: 14, padding: '4px 12px', margin: 0 }}>
                  {statusInfo.label}
                </Tag>
              )}
            />
          </Col>
        </Row>
      </Card>

      {/* ---- Metadata Card ---- */}
      <Card
        style={{
          marginBottom: 16,
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        <Descriptions column={{ xs: 1, sm: 2 }} size="small">
          <Descriptions.Item label="执行 ID">
            <Text copyable style={{ fontSize: 13 }}>
              {execution.id}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusInfo.color}>{statusInfo.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="工作流 ID">
            <Text copyable style={{ fontSize: 13 }}>
              {execution.workflow_id}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="耗时">{duration}</Descriptions.Item>
          {execution.started_at && (
            <Descriptions.Item label="开始时间">
              {formatTimestamp(execution.started_at)}
            </Descriptions.Item>
          )}
          {execution.completed_at && (
            <Descriptions.Item label="完成时间">
              {formatTimestamp(execution.completed_at)}
            </Descriptions.Item>
          )}
          {execution.error && (
            <Descriptions.Item label="错误信息" span={2}>
              <pre
                style={{
                  color: '#ff4d4f',
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                  fontSize: 13,
                }}
              >
                {execution.error}
              </pre>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* ---- Execution Trace Timeline ---- */}
      <Card
        title="执行追踪"
        style={{
          marginBottom: 16,
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        {trace.length > 0 ? (
          <Timeline
            items={trace.map((entry: TraceEntry, index: number) => {
              const event = eventConfig[entry.event] || defaultEvent;
              const durationMs = entry.duration_ms;
              const meta = entry.metadata;
              const hasMeta = meta && Object.keys(meta).length > 0;
              const nodeId = entry.node_id;

              return {
                color: event.color,
                dot: event.icon,
                children: (
                  <div key={index}>
                    {/* Header row: event type + timestamp */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                        <Tag color={event.color} style={{ marginRight: 0 }}>
                          {event.label}
                        </Tag>
                        {nodeId && (
                          <Text strong style={{ fontSize: 13 }}>
                            {entry.node_label || nodeId}
                          </Text>
                        )}
                      </div>
                      {entry.timestamp && (
                        <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap', marginLeft: 12 }}>
                          {formatTimestamp(entry.timestamp)}
                        </Text>
                      )}
                    </div>

                    {/* Message */}
                    {entry.message && (
                      <div style={{ marginTop: 4 }}>
                        <Text style={{ fontSize: 13, color: '#595959' }}>
                          {entry.message}
                        </Text>
                      </div>
                    )}

                    {/* Duration bar for node_complete */}
                    {durationMs != null && (
                      <div style={{ marginTop: 4 }}>
                        <DurationBar durationMs={durationMs} maxMs={maxDuration} />
                      </div>
                    )}

                    {/* Expandable metadata details */}
                    {hasMeta && (
                      <div style={{ marginTop: 6 }}>
                        <Collapse
                          ghost
                          size="small"
                          items={[
                            {
                              key: 'meta',
                              label: <Text type="secondary" style={{ fontSize: 12 }}>详细数据</Text>,
                              children: <JsonViewer data={meta as Record<string, unknown>} />,
                            },
                          ]}
                        />
                      </div>
                    )}
                  </div>
                ),
              };
            })}
          />
        ) : (
          <Empty description="暂无追踪记录" />
        )}
      </Card>

      {/* ---- Global Context JSON Viewer ---- */}
      <Card
        title="全局上下文"
        style={{
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        <JsonViewer data={execution.global_context} />
      </Card>
    </div>
  );
}
