import { memo, useState } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { CloseOutlined } from '@ant-design/icons';

const nodeTypeStyles: Record<string, { bg: string; border: string; color: string }> = {
  input: { bg: '#e6f7ff', border: '#91d5ff', color: '#1890ff' },
  output: { bg: '#f6ffed', border: '#b7eb8f', color: '#52c41a' },
  task: { bg: '#fff7e6', border: '#ffd591', color: '#fa8c16' },
  condition: { bg: '#fff0f6', border: '#ffadd2', color: '#eb2f96' },
  parallel: { bg: '#f9f0ff', border: '#d3adf7', color: '#722ed1' },
  loop: { bg: '#e6fffb', border: '#87e8de', color: '#13c2c2' },
};

const statusColors: Record<string, string> = {
  pending: '#d9d9d9',
  running: '#1890ff',
  success: '#52c41a',
  failed: '#ff4d4f',
  skipped: '#faad14',
};

function WorkflowNode({ id, data, selected }: NodeProps) {
  const [hovered, setHovered] = useState(false);
  const { deleteElements } = useReactFlow();

  const nodeType = (data as Record<string, unknown>)?.type as string || 'task';
  const style = nodeTypeStyles[nodeType] || nodeTypeStyles.task;
  const status = (data as Record<string, unknown>)?.status as string | undefined;
  const label = (data as Record<string, unknown>)?.label as string || id;
  const agentId = (data as Record<string, unknown>)?.agent_id as string | undefined;

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    deleteElements({ nodes: [{ id }] });
  };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: style.bg,
        border: `1.5px solid ${selected ? '#1677ff' : style.border}`,
        borderRadius: 8,
        padding: '8px 14px 8px 14px',
        minWidth: 150,
        position: 'relative',
        boxShadow: selected
          ? '0 0 0 2px rgba(22, 119, 255, 0.2), 0 1px 4px rgba(0,0,0,0.1)'
          : '0 1px 3px rgba(0,0,0,0.08)',
        transition: 'box-shadow 0.15s',
      }}
    >
      {/* Status indicator */}
      {status && (
        <div
          style={{
            position: 'absolute',
            top: -4,
            left: -4,
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: statusColors[status] || statusColors.pending,
            border: '2px solid #fff',
            zIndex: 1,
          }}
        />
      )}

      {/* Delete button on hover */}
      {hovered && (
        <div
          onClick={handleDelete}
          style={{
            position: 'absolute',
            top: -8,
            right: -8,
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: '#ff4d4f',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: 10,
            zIndex: 10,
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          }}
        >
          <CloseOutlined />
        </div>
      )}

      {/* Label */}
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2, color: '#333' }}>
        {label}
      </div>

      {/* Type badge */}
      <div
        style={{
          fontSize: 11,
          color: style.color,
          display: 'inline-block',
          padding: '0 6px',
          borderRadius: 4,
          background: `${style.color}15`,
          lineHeight: '18px',
        }}
      >
        {nodeType}
      </div>

      {/* Agent if assigned */}
      {agentId && (
        <div style={{ fontSize: 11, color: '#888', marginTop: 3 }}>
          {agentId}
        </div>
      )}

      {/* Connection handles */}
      <Handle type="target" position={Position.Top} style={{ background: '#666', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#666', width: 8, height: 8 }} />
    </div>
  );
}

export default memo(WorkflowNode);
