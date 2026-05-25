import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Spin, Tag, Typography, Timeline, Empty, Button, Descriptions,
} from 'antd';
import { ArrowLeftOutlined, LoadingOutlined } from '@ant-design/icons';

import { executionApi } from '@/api/client';
import type { Execution, TraceEntry } from '@/types';

const { Title, Text } = Typography;

const statusConfig: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: '成功' },
  failed: { color: 'error', label: '失败' },
  running: { color: 'processing', label: '运行中' },
  pending: { color: 'default', label: '等待中' },
  paused: { color: 'warning', label: '已暂停' },
  cancelled: { color: 'default', label: '已取消' },
};

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

function JsonViewer({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data, null, 2);

  // Basic syntax highlighting via regex replacements
  const html = json
    .replace(
      /("(?:[^"\\]|\\.)*")\s*:/g,
      '<span style="color:#1677ff">$1</span>:',
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
        background: '#fafafa',
        border: '1px solid #f0f0f0',
        borderRadius: 6,
        padding: 12,
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
        <Card>
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

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          marginBottom: 16,
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

      {/* ---- Metadata Card ---- */}
      <Card style={{ marginBottom: 16 }}>
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
      <Card title="执行追踪" style={{ marginBottom: 16 }}>
        {execution.trace && execution.trace.length > 0 ? (
          <Timeline
            items={execution.trace.map((entry: TraceEntry, index: number) => {
              const dotColor = entry.error
                ? 'red'
                : entry.node_type === 'output'
                  ? 'green'
                  : entry.node_type === 'input'
                    ? 'blue'
                    : 'gray';

              return {
                color: dotColor,
                children: (
                  <div key={index}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                      }}
                    >
                      <Text strong style={{ fontSize: 14 }}>
                        {entry.node_id}
                      </Text>
                      {entry.timestamp && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTimestamp(entry.timestamp)}
                        </Text>
                      )}
                    </div>
                    <div style={{ marginTop: 2 }}>
                      <Tag>{entry.node_type}</Tag>
                      {entry.action && <Tag color="blue">{entry.action}</Tag>}
                    </div>
                    {entry.result_summary && (
                      <div style={{ marginTop: 4 }}>
                        <Text style={{ fontSize: 13, color: '#595959' }}>
                          {entry.result_summary}
                        </Text>
                      </div>
                    )}
                    {entry.error && (
                      <div style={{ marginTop: 4 }}>
                        <Text style={{ color: '#ff4d4f', fontSize: 13 }}>
                          {entry.error}
                        </Text>
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
      <Card title="全局上下文">
        <JsonViewer data={execution.global_context} />
      </Card>
    </div>
  );
}
