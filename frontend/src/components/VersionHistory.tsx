import { useEffect, useState } from 'react';
import { Modal, Timeline, Button, Spin, Tag, Typography, Empty, message as antMsg } from 'antd';
import { RollbackOutlined, HistoryOutlined } from '@ant-design/icons';
import { workflowApi } from '@/api/client';
import type { WorkflowVersion } from '@/types';
import { useWorkflowStore } from '@/store/workflowStore';

const { Text } = Typography;

interface VersionHistoryProps {
  open: boolean;
  onClose: () => void;
  workflowId: string;
}

export default function VersionHistory({ open, onClose, workflowId }: VersionHistoryProps) {
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState<number | null>(null);
  const setCurrentWorkflow = useWorkflowStore((s) => s.setCurrentWorkflow);

  useEffect(() => {
    if (!open || !workflowId) return;

    setLoading(true);
    workflowApi
      .listVersions(workflowId)
      .then(setVersions)
      .catch(() => antMsg.error('获取版本历史失败'))
      .finally(() => setLoading(false));
  }, [open, workflowId]);

  const handleRestore = async (version: number) => {
    setRestoring(version);
    try {
      const restored = await workflowApi.restoreVersion(workflowId, version);
      setCurrentWorkflow(restored);
      antMsg.success(`已恢复至版本 ${version}`);
      onClose();
    } catch (e: any) {
      antMsg.error(`恢复失败: ${e.message}`);
    } finally {
      setRestoring(null);
    }
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  return (
    <Modal
      title={
        <span>
          <HistoryOutlined style={{ marginRight: 8 }} />
          版本历史
        </span>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={520}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : versions.length === 0 ? (
        <Empty description="暂无版本历史" />
      ) : (
        <Timeline
          items={[...versions]
            .reverse()
            .map((v) => ({
              key: v.version,
              color: 'blue',
              children: (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: 12,
                    padding: '8px 0',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <Tag color="blue" style={{ margin: 0 }}>
                        v{v.version}
                      </Tag>
                      {v.message && (
                        <Text strong style={{ fontSize: 13 }}>
                          {v.message}
                        </Text>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary, #5a6170)',
                        marginTop: 2,
                      }}
                    >
                      <span>{formatTime(v.saved_at)}</span>
                      {v.saved_by && (
                        <span style={{ marginLeft: 8 }}>by {v.saved_by}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary, #8e95a3)', marginTop: 2 }}>
                      {v.nodes.length} 个节点 · {v.edges.length} 条连线
                    </div>
                  </div>
                  <Button
                    type="link"
                    size="small"
                    icon={<RollbackOutlined />}
                    loading={restoring === v.version}
                    onClick={() => handleRestore(v.version)}
                    style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
                  >
                    恢复此版本
                  </Button>
                </div>
              ),
            }))}
        />
      )}
    </Modal>
  );
}
