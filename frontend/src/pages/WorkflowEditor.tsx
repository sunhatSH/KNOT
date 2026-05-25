import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button, Spin, Typography, message, Space, Drawer, Descriptions, Tag, Modal, Input,
} from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, ArrowLeftOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node as RFNode,
  type Edge as RFEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { workflowApi } from '@/api/client';
import { useWorkflowStore } from '@/store/workflowStore';
import type { Workflow, Execution } from '@/types';

const { Title } = Typography;

const nodeTypeStyles: Record<string, React.CSSProperties> = {
  input: { background: '#e6f7ff', border: '1px solid #91d5ff' },
  output: { background: '#f6ffed', border: '1px solid #b7eb8f' },
  task: { background: '#fff7e6', border: '1px solid #ffd591' },
  condition: { background: '#fff0f6', border: '1px solid #ffadd2' },
  parallel: { background: '#f9f0ff', border: '1px solid #d3adf7' },
  loop: { background: '#e6fffb', border: '1px solid #87e8de' },
};

export default function WorkflowEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { currentWorkflow, loading, setCurrentWorkflow, setLoading } = useWorkflowStore();
  const [execution, setExecution] = useState<Execution | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [nlModalOpen, setNlModalOpen] = useState(false);
  const [nlInput, setNlInput] = useState('');
  const [nlGenerating, setNlGenerating] = useState(false);

  // Convert workflow nodes to React Flow nodes
  const initialNodes: RFNode[] = useMemo(() => {
    if (!currentWorkflow) return [];
    return currentWorkflow.nodes.map((n, i) => ({
      id: n.id,
      type: 'default',
      position: { x: 250, y: i * 120 },
      data: {
        label: (
          <div>
            <strong>{n.label || n.id}</strong>
            <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
              {n.type}
              {n.agent_id ? ` · ${n.agent_id}` : ''}
            </div>
          </div>
        ),
      },
      style: {
        ...nodeTypeStyles[n.type] || {},
        padding: '8px 16px',
        borderRadius: 8,
        minWidth: 140,
      },
    }));
  }, [currentWorkflow]);

  // Convert workflow edges to React Flow edges
  const initialEdges: RFEdge[] = useMemo(() => {
    if (!currentWorkflow) return [];
    return currentWorkflow.edges.map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      label: e.condition || e.label || '',
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: '#888' },
      animated: true,
    }));
  }, [currentWorkflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges]);

  // Load workflow
  useEffect(() => {
    if (id && id !== 'new') {
      setLoading(true);
      workflowApi.get(id)
        .then((wf) => setCurrentWorkflow(wf))
        .catch(() => message.error('加载工作流失败'))
        .finally(() => setLoading(false));
    } else {
      // New workflow
      setCurrentWorkflow({
        id: '',
        name: '新建工作流',
        nodes: [],
        edges: [],
        global_context: {},
        created_at: new Date().toISOString(),
      });
    }
  }, [id]);

  const handleExecute = async () => {
    if (!currentWorkflow) return;
    try {
      const result = await workflowApi.execute(currentWorkflow.id);
      setExecution(result);
      setDrawerOpen(true);
      if (result.status === 'success') {
        message.success('工作流执行成功');
      } else {
        message.error(`执行失败: ${result.error || result.status}`);
      }
    } catch (e: any) {
      message.error(`执行出错: ${e.message}`);
    }
  };

  const handleSave = async () => {
    if (!currentWorkflow) return;
    try {
      const saved = await workflowApi.create({
        name: currentWorkflow.name,
        description: currentWorkflow.description,
        nodes: currentWorkflow.nodes,
        edges: currentWorkflow.edges,
      });
      setCurrentWorkflow(saved);
      message.success('工作流已保存');
      if (id === 'new') navigate(`/workflows/${saved.id}`, { replace: true });
    } catch (e: any) {
      message.error(`保存失败: ${e.message}`);
    }
  };

  const handleGenerateFromNL = async () => {
    if (!nlInput.trim()) {
      message.warning('请输入自然语言描述');
      return;
    }
    setNlGenerating(true);
    try {
      const workflow = await workflowApi.createFromNL(nlInput.trim());
      setCurrentWorkflow(workflow);
      message.success('工作流生成成功');
      setNlModalOpen(false);
      setNlInput('');
      if (workflow.id) {
        navigate(`/workflows/${workflow.id}`, { replace: true });
      }
    } catch (e: any) {
      message.error(`生成失败: ${e.message}`);
    } finally {
      setNlGenerating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <div style={{
        padding: '8px 16px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#fff',
      }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/workflows')}>
            返回
          </Button>
          <Title level={5} style={{ margin: 0 }}>
            {currentWorkflow?.name || '工作流编辑器'}
          </Title>
        </Space>
        <Space>
          <Button icon={<ThunderboltOutlined />} onClick={() => setNlModalOpen(true)}>
            AI 生成
          </Button>
          <Button icon={<SaveOutlined />} onClick={handleSave}>
            保存
          </Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleExecute}>
            执行
          </Button>
        </Space>
      </div>

      {/* React Flow Canvas */}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          attributionPosition="bottom-left"
        >
          <Background />
          <Controls />
          <MiniMap
            nodeStrokeColor="#666"
            nodeColor="#e0e0e0"
            style={{ border: '1px solid #f0f0f0' }}
          />
        </ReactFlow>
      </div>

      {/* NL Generation Modal */}
      <Modal
        title="从自然语言生成工作流"
        open={nlModalOpen}
        onCancel={() => {
          if (!nlGenerating) {
            setNlModalOpen(false);
          }
        }}
        footer={[
          <Button key="cancel" onClick={() => setNlModalOpen(false)} disabled={nlGenerating}>
            取消
          </Button>,
          <Button
            key="generate"
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={nlGenerating}
            onClick={handleGenerateFromNL}
          >
            生成工作流
          </Button>,
        ]}
      >
        <Spin spinning={nlGenerating}>
          <Input.TextArea
            rows={5}
            value={nlInput}
            onChange={(e) => setNlInput(e.target.value)}
            placeholder="请输入自然语言描述，例如：搜索并分析最新的AI论文，然后生成一份总结报告"
            disabled={nlGenerating}
          />
        </Spin>
      </Modal>

      {/* Execution Result Drawer */}
      <Drawer
        title="执行结果"
        placement="right"
        width={480}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
      >
        {execution ? (
          <div>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="执行 ID">{execution.id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={
                  execution.status === 'success' ? 'green' :
                  execution.status === 'failed' ? 'red' : 'blue'
                }>
                  {execution.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="节点状态">
                {Object.entries(execution.node_states || {}).map(([nid, status]) => (
                  <div key={nid}>{nid}: <Tag>{String(status)}</Tag></div>
                ))}
              </Descriptions.Item>
              {execution.error && (
                <Descriptions.Item label="错误">
                  <pre style={{ color: 'red', whiteSpace: 'pre-wrap' }}>{execution.error}</pre>
                </Descriptions.Item>
              )}
            </Descriptions>
          </div>
        ) : (
          <div>暂无执行结果</div>
        )}
      </Drawer>
    </div>
  );
}
