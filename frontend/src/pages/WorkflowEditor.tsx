import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button, Spin, Typography, message, Space, Drawer, Descriptions, Tag, Modal, Input,
  InputNumber,
} from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, ArrowLeftOutlined, ThunderboltOutlined,
  MenuOutlined, CloseOutlined,
} from '@ant-design/icons';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  addEdge,
  type Node as RFNode,
  type Edge as RFEdge,
  type Connection,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { workflowApi } from '@/api/client';
import { useWorkflowStore } from '@/store/workflowStore';
import type { Workflow, Execution, Node } from '@/types';
import NodePalette from '@/components/NodePalette';
import WorkflowNode from '@/components/WorkflowNode';
import AgentConfigPanel from '@/components/AgentConfigPanel';
import type { MultiAgentMode, AgentTeamMember } from '@/types';

const { Title, Text } = Typography;

const nodeTypeLabels: Record<string, string> = {
  input: '输入节点',
  output: '输出节点',
  task: '任务节点',
  condition: '条件节点',
  parallel: '并行节点',
  loop: '循环节点',
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
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Responsive layout
  // ---------------------------------------------------------------------------
  const isMobile = useMediaQuery('(max-width: 768px)');
  const isTiny = useMediaQuery('(max-width: 480px)');
  const [sidebarVisible, setSidebarVisible] = useState(true);

  // Auto-hide sidebar on mobile screens
  useEffect(() => {
    if (isMobile) setSidebarVisible(false);
  }, [isMobile]);

  // ---------------------------------------------------------------------------
  // React Flow instance (used for coordinate conversion on drop)
  // ---------------------------------------------------------------------------
  const [rfInstance, setRfInstance] = useState<any>(null);

  // ---------------------------------------------------------------------------
  // Convert workflow data to React Flow nodes / edges
  // ---------------------------------------------------------------------------
  const initialNodes: RFNode[] = useMemo(() => {
    if (!currentWorkflow) return [];
    return currentWorkflow.nodes.map((n, i) => ({
      id: n.id,
      type: 'workflowNode',
      position: (n.config as any)?.position || { x: 250, y: i * 120 },
      data: {
        id: n.id,
        label: n.label || n.id,
        type: n.type,
        agent_id: n.agent_id,
        status: n.status,
      },
    }));
  }, [currentWorkflow]);

  const initialEdges: RFEdge[] = useMemo(() => {
    if (!currentWorkflow) return [];
    return currentWorkflow.edges.map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      label: e.condition || e.label || '',
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: '#8e95a3' },
      animated: true,
    }));
  }, [currentWorkflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync store -> React Flow state
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // ---------------------------------------------------------------------------
  // Load workflow
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (id && id !== 'new') {
      setLoading(true);
      workflowApi.get(id)
        .then((wf) => setCurrentWorkflow(wf))
        .catch(() => message.error('加载工作流失败'))
        .finally(() => setLoading(false));
    } else {
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

  // ---------------------------------------------------------------------------
  // Helpers: update a single field on a node (both local state and store)
  // ---------------------------------------------------------------------------
  const updateNodeData = useCallback((nodeId: string, field: string, value: any) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, [field]: value } } : n,
      ),
    );
    const { currentWorkflow: wf, updateNodes } = useWorkflowStore.getState();
    if (wf) {
      updateNodes(
        wf.nodes.map((n) => (n.id === nodeId ? { ...n, [field]: value } : n)),
      );
    }
  }, [setNodes]);

  // ---------------------------------------------------------------------------
  // Node / edge event handlers
  // ---------------------------------------------------------------------------

  const onNodeClick = useCallback((_event: React.MouseEvent, node: RFNode) => {
    setSelectedNodeId(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      const edgeId = `edge_${Math.random().toString(36).slice(2, 10)}`;
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            id: edgeId,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: '#8e95a3' },
            animated: true,
          },
          eds,
        ),
      );
      const { currentWorkflow: wf, updateEdges } = useWorkflowStore.getState();
      if (wf) {
        updateEdges([
          ...wf.edges,
          { id: edgeId, source_id: connection.source, target_id: connection.target, label: '' },
        ]);
      }
    },
    [setEdges],
  );

  const onNodesDelete = useCallback((deletedNodes: RFNode[]) => {
    const deletedIds = new Set(deletedNodes.map((n) => n.id));
    setSelectedNodeId((prev) => (prev && deletedIds.has(prev) ? null : prev));

    const { currentWorkflow: wf, updateNodes, updateEdges } = useWorkflowStore.getState();
    if (wf) {
      updateNodes(wf.nodes.filter((n) => !deletedIds.has(n.id)));
      updateEdges(
        wf.edges.filter((e) => !deletedIds.has(e.source_id) && !deletedIds.has(e.target_id)),
      );
    }
  }, []);

  const onEdgesDelete = useCallback((deletedEdges: RFEdge[]) => {
    const deletedIds = new Set(deletedEdges.map((e) => e.id));
    const { currentWorkflow: wf, updateEdges } = useWorkflowStore.getState();
    if (wf) {
      updateEdges(wf.edges.filter((e) => !deletedIds.has(e.id)));
    }
  }, []);

  const onNodeDragStop = useCallback((_event: React.MouseEvent, node: RFNode) => {
    const { currentWorkflow: wf, updateNodes } = useWorkflowStore.getState();
    if (!wf) return;
    const existingNode = wf.nodes.find((n) => n.id === node.id);
    const existingPos = (existingNode?.config as any)?.position;
    const newPos = { x: Math.round(node.position.x), y: Math.round(node.position.y) };
    if (existingPos?.x !== newPos.x || existingPos?.y !== newPos.y) {
      updateNodes(
        wf.nodes.map((n) =>
          n.id === node.id ? { ...n, config: { ...n.config, position: newPos } } : n,
        ),
      );
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Drag-and-drop from the palette
  // ---------------------------------------------------------------------------
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow');
      if (!type || !rfInstance) return;

      const position = rfInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const nodeId = `node_${Math.random().toString(36).slice(2, 10)}`;
      const label = nodeTypeLabels[type] || type;

      setNodes((nds) => [
        ...nds,
        {
          id: nodeId,
          type: 'workflowNode',
          position,
          data: { id: nodeId, label, type, agent_id: undefined, status: undefined },
        },
      ]);

      const { currentWorkflow: wf, updateNodes } = useWorkflowStore.getState();
      if (wf) {
        updateNodes([
          ...wf.nodes,
          {
            id: nodeId,
            type: type as Node['type'],
            label,
            config: { position: { x: Math.round(position.x), y: Math.round(position.y) } },
            inputs: {},
            outputs: {},
          } as Node,
        ]);
      }
    },
    [rfInstance, setNodes],
  );

  // ---------------------------------------------------------------------------
  // Custom node type registration
  // ---------------------------------------------------------------------------
  const nodeTypes = useMemo(() => ({ workflowNode: WorkflowNode }), []);

  // ---------------------------------------------------------------------------
  // Selected node data (for the property panel)
  // ---------------------------------------------------------------------------
  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !currentWorkflow) return null;
    return currentWorkflow.nodes.find((n) => n.id === selectedNodeId) ?? null;
  }, [selectedNodeId, currentWorkflow]);

  // ---------------------------------------------------------------------------
  // Multi-agent helpers (reads/writes node.config)
  // ---------------------------------------------------------------------------
  const updateNodeConfig = useCallback(
    (nodeId: string, configUpdate: Record<string, unknown>) => {
      const { currentWorkflow: wf, updateNodes } = useWorkflowStore.getState();
      if (!wf) return;
      updateNodes(
        wf.nodes.map((n) =>
          n.id === nodeId ? { ...n, config: { ...n.config, ...configUpdate } } : n,
        ),
      );
    },
    [],
  );

  const currentMultiAgentMode = useMemo<MultiAgentMode | undefined>(() => {
    if (!selectedNode?.config) return undefined;
    return (selectedNode.config as any)?.multi_agent_mode as MultiAgentMode | undefined;
  }, [selectedNode]);

  const currentAgentTeam = useMemo<AgentTeamMember[]>(() => {
    if (!selectedNode?.config) return [];
    return ((selectedNode.config as any)?.agent_team as AgentTeamMember[]) || [];
  }, [selectedNode]);

  // ---------------------------------------------------------------------------
  // Save handler – merges React Flow positions into workflow nodes
  // ---------------------------------------------------------------------------
  const handleSave = useCallback(async () => {
    if (!currentWorkflow) return;

    const nodesToSave = currentWorkflow.nodes.map((node) => {
      const rfNode = nodes.find((n) => n.id === node.id);
      if (rfNode) {
        return {
          ...node,
          config: {
            ...node.config,
            position: { x: rfNode.position.x, y: rfNode.position.y },
          },
        };
      }
      return node;
    });

    try {
      const saved = await workflowApi.create({
        name: currentWorkflow.name,
        description: currentWorkflow.description,
        nodes: nodesToSave,
        edges: currentWorkflow.edges,
      });
      setCurrentWorkflow(saved);
      message.success('工作流已保存');
      if (id === 'new') navigate(`/workflows/${saved.id}`, { replace: true });
    } catch (e: any) {
      message.error(`保存失败: ${e.message}`);
    }
  }, [currentWorkflow, nodes, id, navigate, setCurrentWorkflow]);

  // ---------------------------------------------------------------------------
  // Execute handler
  // ---------------------------------------------------------------------------
  const handleExecute = useCallback(async () => {
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
  }, [currentWorkflow]);

  // ---------------------------------------------------------------------------
  // NL generation handler
  // ---------------------------------------------------------------------------
  const handleGenerateFromNL = useCallback(async () => {
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
  }, [nlInput, navigate, setCurrentWorkflow]);

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------
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
        <Spin size="large" />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div style={{ height: 'calc(100vh - 56px)', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <div
        style={{
          padding: '10px 20px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-card)',
          gap: 8,
        }}
      >
        <Space>
          {isMobile && (
            <Button
              type="text"
              icon={sidebarVisible ? <CloseOutlined /> : <MenuOutlined />}
              onClick={() => setSidebarVisible((v) => !v)}
              style={{ color: 'var(--text-secondary, #5a6170)' }}
            />
          )}
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/workflows')}
            {...(isTiny ? { type: 'text', style: { color: 'var(--text-secondary, #5a6170)' } } : {})}
          >
            {isTiny ? undefined : '返回'}
          </Button>
          {!isTiny && (
            <>
              <div
                style={{
                  width: 1,
                  height: 20,
                  background: 'var(--border-color)',
                  margin: '0 8px',
                }}
              />
              <Title level={5} style={{ margin: 0, fontWeight: 600, fontSize: isTiny ? 14 : undefined }}>
                {currentWorkflow?.name || '工作流编辑器'}
              </Title>
            </>
          )}
        </Space>
        <Space size={isTiny ? 4 : 8}>
          <Button
            icon={<ThunderboltOutlined />}
            {...(isTiny ? { type: 'text', style: { color: 'var(--text-secondary, #5a6170)' } } : {})}
            onClick={() => setNlModalOpen(true)}
          >
            {isTiny ? undefined : 'AI 生成'}
          </Button>
          <Button
            icon={<SaveOutlined />}
            {...(isTiny ? { type: 'text', style: { color: 'var(--text-secondary, #5a6170)' } } : {})}
            onClick={handleSave}
          >
            {isTiny ? undefined : '保存'}
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            {...(isTiny ? { style: { width: 36, height: 36, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' } } : {})}
          >
            {isTiny ? undefined : '执行'}
          </Button>
        </Space>
      </div>

      {/* Main content: sidebar + canvas */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {sidebarVisible && <NodePalette compact={isMobile} />}

        <ReactFlowProvider>
          <div style={{ flex: 1, position: 'relative' }}>
            {/* Empty canvas hint */}
            {nodes.length === 0 && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  pointerEvents: 'none',
                  color: '#bbb',
                  fontSize: 14,
                  zIndex: 5,
                  padding: 20,
                  textAlign: 'center',
                }}
              >
                从左侧面板拖拽节点到画布，或点击「AI 生成」输入自然语言
              </div>
            )}

            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              onNodesDelete={onNodesDelete}
              onEdgesDelete={onEdgesDelete}
              onNodeDragStop={onNodeDragStop}
              onInit={setRfInstance}
              nodeTypes={nodeTypes}
              fitView
              attributionPosition="bottom-left"
            >
              <Background />
              <Controls />
              <MiniMap
                nodeStrokeColor="#666"
                nodeColor="#e0e0e0"
                style={{ border: '1px solid #e8eaf0' }}
              />
            </ReactFlow>
          </div>
        </ReactFlowProvider>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Node Property Panel (Drawer on the right)                          */}
      {/* ------------------------------------------------------------------ */}
      <Drawer
        title="节点属性"
        placement="right"
        width={360}
        onClose={() => setSelectedNodeId(null)}
        open={selectedNodeId !== null}
      >
        {selectedNode ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* ID (readonly) */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                ID
              </Text>
              <Input size="small" value={selectedNode.id} disabled />
            </div>

            {/* Label */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                标签
              </Text>
              <Input
                size="small"
                value={selectedNode.label}
                onChange={(e) => updateNodeData(selectedNode.id, 'label', e.target.value)}
              />
            </div>

            {/* Type (readonly tag) */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                类型
              </Text>
              <Tag color={
                selectedNode.type === 'input' ? 'blue' :
                selectedNode.type === 'output' ? 'green' :
                selectedNode.type === 'task' ? 'orange' :
                selectedNode.type === 'condition' ? 'pink' :
                selectedNode.type === 'parallel' ? 'purple' :
                selectedNode.type === 'loop' ? 'cyan' : undefined
              }>
                {nodeTypeLabels[selectedNode.type] || selectedNode.type}
              </Tag>
            </div>

            {/* Agent */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Agent
              </Text>
              <Input
                size="small"
                value={selectedNode.agent_id || ''}
                placeholder="输入 agent ID"
                onChange={(e) =>
                  updateNodeData(selectedNode.id, 'agent_id', e.target.value || undefined)
                }
              />
            </div>

            {/* Multi-Agent Config */}
            <div
              style={{
                marginTop: 4,
                padding: '12px 10px',
                borderRadius: 6,
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-color)',
              }}
            >
              <AgentConfigPanel
                mode={currentMultiAgentMode}
                team={currentAgentTeam}
                defaultRole="executor"
                onChange={({ mode, team }) => {
                  if (!selectedNode) return;
                  const cfg: Record<string, unknown> = {};
                  if (mode) cfg.multi_agent_mode = mode;
                  else cfg.multi_agent_mode = undefined;
                  if (team) cfg.agent_team = team;
                  else cfg.agent_team = [];
                  updateNodeConfig(selectedNode.id, cfg);
                }}
              />
            </div>

            {/* Timeout */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                超时时间 (秒)
              </Text>
              <InputNumber
                size="small"
                value={selectedNode.timeout_seconds ?? 60}
                min={1}
                style={{ width: '100%' }}
                onChange={(v) => updateNodeData(selectedNode.id, 'timeout_seconds', v)}
              />
            </div>

            {/* Max Retries */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                最大重试次数
              </Text>
              <InputNumber
                size="small"
                value={selectedNode.max_retries ?? 0}
                min={0}
                max={10}
                style={{ width: '100%' }}
                onChange={(v) => updateNodeData(selectedNode.id, 'max_retries', v)}
              />
            </div>

            {/* Config (readonly) */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                配置 (JSON)
              </Text>
              <Input.TextArea
                rows={4}
                value={JSON.stringify(selectedNode.config, null, 2)}
                disabled
                style={{ fontSize: 11, fontFamily: 'monospace' }}
              />
            </div>
          </div>
        ) : (
          <Text type="secondary">请选择一个节点</Text>
        )}
      </Drawer>

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
                <Tag
                  color={
                    execution.status === 'success'
                      ? 'green'
                      : execution.status === 'failed'
                        ? 'red'
                        : 'blue'
                  }
                >
                  {execution.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="节点状态">
                {Object.entries(execution.node_states || {}).map(([nid, status]) => (
                  <div key={nid}>
                    {nid}: <Tag>{String(status)}</Tag>
                  </div>
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
