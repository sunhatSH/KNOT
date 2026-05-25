import { Typography } from 'antd';
import {
  ArrowRightOutlined,
  CarryOutOutlined,
  BranchesOutlined,
  ApartmentOutlined,
  SyncOutlined,
  ExportOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

const paletteItems: Array<{
  type: string;
  label: string;
  icon: React.ReactNode;
  bg: string;
  border: string;
  color: string;
}> = [
  { type: 'input', label: '输入节点', icon: <ArrowRightOutlined />, bg: '#e6f7ff', border: '#91d5ff', color: '#1890ff' },
  { type: 'task', label: '任务节点', icon: <CarryOutOutlined />, bg: '#fff7e6', border: '#ffd591', color: '#fa8c16' },
  { type: 'condition', label: '条件节点', icon: <BranchesOutlined />, bg: '#fff0f6', border: '#ffadd2', color: '#eb2f96' },
  { type: 'parallel', label: '并行节点', icon: <ApartmentOutlined />, bg: '#f9f0ff', border: '#d3adf7', color: '#722ed1' },
  { type: 'loop', label: '循环节点', icon: <SyncOutlined />, bg: '#e6fffb', border: '#87e8de', color: '#13c2c2' },
  { type: 'output', label: '输出节点', icon: <ExportOutlined />, bg: '#f6ffed', border: '#b7eb8f', color: '#52c41a' },
];

interface NodePaletteProps {
  compact?: boolean;
}

export default function NodePalette({ compact }: NodePaletteProps) {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      style={{
        width: compact ? 140 : 180,
        borderRight: '1px solid var(--border-color, #f0f0f0)',
        background: 'var(--bg-card, #fafafa)',
        padding: compact ? '10px 6px' : '12px 8px',
        overflowY: 'auto',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: compact ? 3 : 4,
      }}
    >
      <Text strong style={{ fontSize: compact ? 11 : 13, padding: '0 4px 4px', color: 'var(--text-primary, #333)' }}>
        节点类型
      </Text>
      {paletteItems.map((item) => (
        <div
          key={item.type}
          draggable
          onDragStart={(e) => onDragStart(e, item.type)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: compact ? 4 : 8,
            padding: compact ? '6px 8px' : '8px 10px',
            borderRadius: 6,
            cursor: 'grab',
            background: item.bg,
            border: `1px solid ${item.border}`,
            transition: 'box-shadow 0.2s, transform 0.1s',
            userSelect: 'none',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
            e.currentTarget.style.transform = 'translateY(-1px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'none';
            e.currentTarget.style.transform = 'none';
          }}
        >
          <span style={{ color: item.color, fontSize: compact ? 13 : 15, display: 'flex', alignItems: 'center' }}>
            {item.icon}
          </span>
          {!compact && <Text style={{ fontSize: 12, lineHeight: '20px' }}>{item.label}</Text>}
        </div>
      ))}
    </div>
  );
}
