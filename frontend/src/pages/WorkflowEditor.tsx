import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button, Spin, Typography, message, Space, Drawer, Descriptions, Tag, Modal, Input,
  InputNumber, Select, Badge, List, Progress, Alert,
} from 'antd';
import {
  PlayCircleOutlined, SaveOutlined, ArrowLeftOutlined, ThunderboltOutlined,
  MenuOutlined, CloseOutlined, AppstoreOutlined, HistoryOutlined,
  PauseCircleOutlined, StopOutlined, LoadingOutlined,
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

import { workflowApi, executionApi, templateApi } from '@/api/client';
import { useWorkflowStore } from '@/store/workflowStore';
import type { Workflow, Execution, Node, TraceEntry } from '@/types';
import NodePalette from '@/components/NodePalette';
import WorkflowNode from '@/components/WorkflowNode';
import VersionHistory from '@/components/VersionHistory';
import AgentConfigPanel from '@/components/AgentConfigPanel';
import type { MultiAgentMode, AgentTeamMember } from '@/types';
import { useExecutionWebSocket } from '@/hooks/useExecutionWebSocket';

const { Title, Text } = Typography;

const nodeTypeLabels: Record<string, string> = {
  input: '输入节点',
  output: '输出节点',
  task: '任务节点',
  condition: '条件节点',
  parallel: '并行节点',
  loop: '循环节点',
};

const executionStatusLabels: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
  pending: '等待中',
  paused: '已暂停',
  cancelled: '已取消',
};

const executionStatusColors: Record<string, string> = {
  success: 'success',
  failed: 'error',
  running: 'processing',
  pending: 'default',
  paused: 'warning',
  cancelled: 'default',
};

export default function WorkflowEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { currentWorkflow, loading, setCurrentWorkflow, setLoading } = useWorkflowStore();
  const [execution, setExecution] = useState<Execution | null>(null);
  const [execPanelOpen, setExecPanelOpen] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [nlModalOpen, setNlModalOpen] = useState(false);
  const [nlInput, setNlInput] = useState('');
  const [nlGenerating, setNlGenerating] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Version history modal state
  const [verHistoryOpen, setVerHistoryOpen] = useState(false);

  // Save with commit message
  const [saveMsgModalOpen, setSaveMsgModalOpen] = useState(false);
  const [saveCommitMsg, setSaveCommitMsg] = useState('');

  // Template save modal state
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDesc, setTemplateDesc] = useState('');
  const [templateCategory, setTemplateCategory] = useState<string>('general');
  const [templateTagsStr, setTemplateTagsStr] = useState('');
  const [templateSaving, setTemplateSaving] = useState(false);

  // Polling ref for execution state fallback
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
  // Execution: WebSocket real-time updates
  // ---------------------------------------------------------------------------
  const {
    execution: wsExecution,
    connected: wsConnected,
  } = useExecutionWebSocket(execution?.id);

  // When WS pushes a new state, update local state immediately
  useEffect(() => {
    if (wsExecution) {
      setExecution(wsExecution);
    }
  }, [wsExecution]);

  // ---------------------------------------------------------------------------
  // Execution: sync node_states to React Flow node data (status highlighting)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!execution?.node_states) return;
    setNodes((nds) =>
      nds.map((n) => {
        const execStatus = (execution.node_states as Record<string, string>)[n.id];
        return {
          ...n,
          data: {
            ...n.data,
            status: execStatus || n.data.status,
          },
        };
      }),
    );
  }, [execution?.node_states, setNodes]);

  // Clear node statuses when a new execution starts (no previous execution
  // node_states to sync) -- handled naturally by the effect above since
  // execution?.node_states will be fresh.

  // ---------------------------------------------------------------------------
  // Execution: REST polling fallback when WS is disconnected
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const isTerminal = execution?.status === 'success'
      || execution?.status === 'failed'
      || execution?.status === 'cancelled';

    if (!execution?.id || isTerminal) {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    // If WS is connected, skip polling
    if (wsConnected) {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    // Start polling (only if not already running)
    if (pollingRef.current === null) {
      pollingRef.current = setInterval(() => {
        workflowApi.getExecution(execution.id).then((data) => {
          setExecution(data);
        }).catch(() => {
          // Silently ignore polling errors
        });
      }, 3000);
    }

    return () => {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [execution?.id, execution?.status, wsConnected]);

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
  const doSave = useCallback(async (commitMsg?: string) => {
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
      const payload: any = {
        name: currentWorkflow.name,
        description: currentWorkflow.description,
        nodes: nodesToSave,
        edges: currentWorkflow.edges,
      };
      // Attach commit message as a temporary version entry for the backend
      if (commitMsg) {
        payload.versions = [{ version: 0, workflow_id: currentWorkflow.id || '', message: commitMsg }];
      }
      const saved = await workflowApi.create(payload);
      setCurrentWorkflow(saved);
      message.success('工作流已保存');
      if (id === 'new') navigate(`/workflows/${saved.id}`, { replace: true });
    } catch (e: any) {
      message.error(`保存失败: ${e.message}`);
    }
  }, [currentWorkflow, nodes, id, navigate, setCurrentWorkflow]);

  const handleSave = useCallback(() => {
    if (!currentWorkflow) return;
    // If workflow already exists, prompt for commit message
    if (currentWorkflow.id && currentWorkflow.id !== 'new' && id !== 'new') {
      setSaveCommitMsg('');
      setSaveMsgModalOpen(true);
    } else {
      doSave();
    }
  }, [currentWorkflow, id, doSave]);

  const handleSaveWithMessage = useCallback(() => {
    setSaveMsgModalOpen(false);
    doSave(saveCommitMsg);
  }, [doSave, saveCommitMsg]);

  // ---------------------------------------------------------------------------
  // Execution: Trigger
  // ---------------------------------------------------------------------------
  const handleExecute = useCallback(async () => {
    if (!currentWorkflow) return;
    if (!currentWorkflow.id || currentWorkflow.id === 'new') {
      message.warning('请先保存工作流');
      return;
    }
    if (currentWorkflow.nodes.length === 0) {
      message.warning('工作流没有节点，请先添加节点');
      return;
    }
    if (execution?.status === 'running') {
      message.warning('工作流正在执行中');
      return;
    }
    try {
      const result = await workflowApi.execute(currentWorkflow.id);
      setExecution(result);
      setExecPanelOpen(true);
    } catch (e: any) {
      message.error(`执行出错: ${e.message}`);
    }
  }, [currentWorkflow, execution?.status]);

  // ---------------------------------------------------------------------------
  // Execution: Pause / Resume / Cancel
  // ---------------------------------------------------------------------------
  const handlePause = useCallback(async () => {
    if (!execution?.id) return;
    setPausing(true);
    try {
      const data = await executionApi.pause(execution.id);
      setExecution(data);
      message.success('执行已暂停');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '暂停执行失败');
    } finally {
      setPausing(false);
    }
  }, [execution?.id]);

  const handleResume = useCallback(async () => {
    if (!execution?.id) return;
    setResuming(true);
    try {
      const data = await executionApi.resume(execution.id);
      setExecution(data);
      message.success('执行已恢复');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '恢复执行失败');
    } finally {
      setResuming(false);
    }
  }, [execution?.id]);

  const handleCancel = useCallback(async () => {
    if (!execution?.id) return;
    setCancelling(true);
    try {
      const data = await executionApi.cancel(execution.id);
      setExecution(data);
      message.success('执行已终止');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '终止执行失败');
    } finally {
      setCancelling(false);
    }
  }, [execution?.id]);

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
  // Save as template handler
  // ---------------------------------------------------------------------------
  const handleSaveAsTemplate = useCallback(async () => {
    if (!currentWorkflow) return;
    if (!templateName.trim()) {
      message.warning('请输入模板名称');
      return;
    }
    if (!currentWorkflow.nodes || currentWorkflow.nodes.length === 0) {
      message.warning('工作流没有节点，无法保存为模板');
      return;
    }

    setTemplateSaving(true);
    try {
      const tags = templateTagsStr
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean);

      const saved = await templateApi.save({
        name: templateName.trim(),
        description: templateDesc.trim(),
        category: templateCategory,
        tags,
        nodes: currentWorkflow.nodes,
        edges: currentWorkflow.edges,
        config: currentWorkflow.global_context,
      });
      message.success(`模板「${saved.name}」保存成功`);
      setTemplateModalOpen(false);
      // Reset form
      setTemplateName('');
      setTemplateDesc('');
      setTemplateCategory('general');
      setTemplateTagsStr('');
    } catch (e: any) {
      message.error(`保存模板失败: ${e.message}`);
    } finally {
      setTemplateSaving(false);
    }
  }, [currentWorkflow, templateName, templateDesc, templateCategory, templateTagsStr]);

  // ---------------------------------------------------------------------------
  // Execution progress helpers
  // ---------------------------------------------------------------------------
  const executionProgress = useMemo(() => {
    if (!execution?.node_states) return { total: 0, completed: 0, failed: 0, skipped: 0 };
    const states = Object.values(execution.node_states);
    return {
      total: states.length,
      completed: states.filter((s) => s === 'success').length,
      failed: states.filter((s) => s === 'failed').length,
      skipped: states.filter((s) => s === 'skipped').length,
    };
  }, [execution?.node_states]);

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
  const isExecuting = execution?.status === 'running' || execution?.status === 'paused';

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
            icon={<AppstoreOutlined />}
            {...(isTiny ? { type: 'text', style: { color: 'var(--text-secondary, #5a6170)' } } : {})}
            onClick={() => {
              if (currentWorkflow && currentWorkflow.nodes.length > 0) {
                setTemplateModalOpen(true);
              } else {
                message.warning('请先添加节点再保存为模板');
              }
            }}
          >
            {isTiny ? undefined : '保存为模板'}
          </Button>
          <Button
            icon={<HistoryOutlined />}
            {...(isTiny ? { type: 'text', style: { color: 'var(--text-secondary, #5a6170)' } } : {})}
            onClick={() => setVerHistoryOpen(true)}
          >
            {isTiny ? undefined : '版本历史'}
          </Button>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            disabled={!currentWorkflow?.id || currentWorkflow?.id === 'new' || execution?.status === 'running'}
            {...(isTiny ? { style: { width: 36, height: 36, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' } } : {})}
          >
            {isTiny ? undefined : '执行'}
          </Button>
        </Space>
      </div>

      {/* Execution Status Banner */}
      {isExecuting && (
        <div
          style={{
            padding: '8px 20px',
            background: execution?.status === 'running' ? '#e6f7ff' : '#fffbe6',
            borderBottom: `1px solid ${execution?.status === 'running' ? '#91d5ff' : '#ffe58f'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <Space>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} />} />
            <Text strong style={{ fontSize: 14 }}>
              {execution?.status === 'running' ? '工作流执行中...' : '工作流已暂停'}
            </Text>
            <Badge status={execution?.status === 'running' ? 'processing' : 'warning'} />
            <Text type="secondary" style={{ fontSize: 13 }}>
              共 {currentWorkflow?.nodes.length || 0} 个节点
            </Text>
          </Space>
          <Space>
            {execution?.status === 'running' && (
              <>
                <Button size="small" icon={<PauseCircleOutlined />} loading={pausing} onClick={handlePause}>
                  暂停
                </Button>
                <Button size="small" icon={<StopOutlined />} danger loading={cancelling} onClick={handleCancel}>
                  终止
                </Button>
              </>
            )}
            {execution?.status === 'paused' && (
              <>
                <Button size="small" icon={<PlayCircleOutlined />} loading={resuming} onClick={handleResume}>
                  恢复
                </Button>
                <Button size="small" icon={<StopOutlined />} danger loading={cancelling} onClick={handleCancel}>
                  终止
                </Button>
              </>
            )}
            <Button size="small" onClick={() => setExecPanelOpen(true)}>
              查看详情
            </Button>
          </Space>
        </div>
      )}

      {/* Execution completed banner (transient, shows final summary) */}
      {execution && !isExecuting && (
        <div
          style={{
            padding: '6px 20px',
            background: execution.status === 'success' ? '#f6ffed' : execution.status === 'failed' ? '#fff2f0' : '#fafafa',
            borderBottom: `1px solid ${
              execution.status === 'success' ? '#b7eb8f' : execution.status === 'failed' ? '#ffccc7' : '#d9d9d9'
            }`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <Space>
            <Badge status={executionStatusColors[execution.status] as 'success' | 'error' | 'default'} />
            <Text strong style={{ fontSize: 14 }}>
              {execution.status === 'success' ? '执行完成' :
               execution.status === 'failed' ? '执行失败' :
               execution.status === 'cancelled' ? '执行已取消' : ''}
            </Text>
            <Text type="secondary" style={{ fontSize: 13 }}>
              成功 {executionProgress.completed}
              {executionProgress.failed > 0 && ` / 失败 ${executionProgress.failed}`}
              {executionProgress.skipped > 0 && ` / 跳过 ${executionProgress.skipped}`}
            </Text>
          </Space>
          <Space>
            <Button size="small" onClick={() => setExecPanelOpen(true)}>
              查看详情
            </Button>
            <Button size="small" onClick={() => setExecution(null)}>
              关闭
            </Button>
          </Space>
        </div>
      )}

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

      {/* Save as Template Modal */}
      <Modal
        title="保存为模板"
        open={templateModalOpen}
        onCancel={() => {
          if (!templateSaving) {
            setTemplateModalOpen(false);
          }
        }}
        footer={[
          <Button key="cancel" onClick={() => setTemplateModalOpen(false)} disabled={templateSaving}>
            取消
          </Button>,
          <Button
            key="save"
            type="primary"
            icon={<AppstoreOutlined />}
            loading={templateSaving}
            onClick={handleSaveAsTemplate}
          >
            保存模板
          </Button>,
        ]}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              模板名称 <span style={{ color: '#ff4d4f' }}>*</span>
            </Text>
            <Input
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="输入模板名称"
              disabled={templateSaving}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              描述
            </Text>
            <Input.TextArea
              rows={3}
              value={templateDesc}
              onChange={(e) => setTemplateDesc(e.target.value)}
              placeholder="描述这个模板的用途"
              disabled={templateSaving}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              分类
            </Text>
            <Select
              value={templateCategory}
              onChange={setTemplateCategory}
              style={{ width: '100%' }}
              disabled={templateSaving}
              options={[
                { value: 'general', label: '通用' },
                { value: 'ops', label: '运维监控' },
                { value: 'finance', label: '金融合规' },
                { value: 'medical', label: '医疗健康' },
                { value: 'custom', label: '自定义' },
              ]}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              标签（逗号分隔）
            </Text>
            <Input
              value={templateTagsStr}
              onChange={(e) => setTemplateTagsStr(e.target.value)}
              placeholder="例如: 监控,告警,自动化"
              disabled={templateSaving}
            />
          </div>
        </div>
      </Modal>

      {/* Version History Modal */}
      {currentWorkflow?.id && id !== 'new' && (
        <VersionHistory
          open={verHistoryOpen}
          onClose={() => setVerHistoryOpen(false)}
          workflowId={currentWorkflow.id}
        />
      )}

      {/* Save Commit Message Modal */}
      <Modal
        title="保存版本"
        open={saveMsgModalOpen}
        onCancel={() => setSaveMsgModalOpen(false)}
        onOk={handleSaveWithMessage}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            提交说明（可选）
          </Text>
          <Input
            value={saveCommitMsg}
            onChange={(e) => setSaveCommitMsg(e.target.value)}
            placeholder="简要描述本次变更内容"
            onPressEnter={handleSaveWithMessage}
          />
        </div>
      </Modal>

      {/* ------------------------------------------------------------------ */}
      {/* Execution Panel Drawer                                             */}
      {/* ------------------------------------------------------------------ */}
      <Drawer
        title={
          <Space>
            <span>执行详情</span>
            {execution && (
              <Tag color={executionStatusColors[execution.status] || 'default'}>
                {executionStatusLabels[execution.status] || execution.status}
              </Tag>
            )}
            <Badge
              status={wsConnected ? 'success' : 'default'}
              text={
                <Text type={wsConnected ? 'success' : 'secondary'} style={{ fontSize: 12 }}>
                  {wsConnected ? '实时' : execution?.status === 'running' ? '轮询' : ''}
                </Text>
              }
            />
          </Space>
        }
        placement="right"
        width={480}
        onClose={() => setExecPanelOpen(false)}
        open={execPanelOpen}
      >
        {execution ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Execution ID */}
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 2 }}>
                执行 ID
              </Text>
              <Text copyable style={{ fontSize: 13 }}>{execution.id}</Text>
            </div>

            {/* Start / End time */}
            <div style={{ display: 'flex', gap: 24 }}>
              {execution.started_at && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 2 }}>
                    开始时间
                  </Text>
                  <Text style={{ fontSize: 13 }}>{new Date(execution.started_at).toLocaleString()}</Text>
                </div>
              )}
              {execution.completed_at && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 2 }}>
                    完成时间
                  </Text>
                  <Text style={{ fontSize: 13 }}>{new Date(execution.completed_at).toLocaleString()}</Text>
                </div>
              )}
            </div>

            {/* Progress */}
            {execution.node_states && executionProgress.total > 0 && (
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  执行进度
                </Text>
                <Progress
                  percent={Math.round(
                    ((executionProgress.completed + executionProgress.failed) / executionProgress.total) * 100,
                  )}
                  status={
                    execution.status === 'failed'
                      ? 'exception'
                      : execution.status === 'running' || execution.status === 'paused'
                        ? 'active'
                        : 'success'
                  }
                  format={() => `${executionProgress.completed + executionProgress.failed} / ${executionProgress.total}`}
                />
                <Space style={{ marginTop: 4 }}>
                  <Text style={{ color: '#52c41a', fontSize: 12 }}>成功: {executionProgress.completed}</Text>
                  {executionProgress.failed > 0 && (
                    <Text style={{ color: '#ff4d4f', fontSize: 12 }}>失败: {executionProgress.failed}</Text>
                  )}
                  {executionProgress.skipped > 0 && (
                    <Text style={{ color: '#8c8c8c', fontSize: 12 }}>跳过: {executionProgress.skipped}</Text>
                  )}
                </Space>
              </div>
            )}

            {/* Control buttons */}
            {isExecuting && (
              <div style={{ display: 'flex', gap: 8 }}>
                {execution?.status === 'running' && (
                  <>
                    <Button icon={<PauseCircleOutlined />} loading={pausing} onClick={handlePause} size="small">
                      暂停
                    </Button>
                    <Button icon={<StopOutlined />} danger loading={cancelling} onClick={handleCancel} size="small">
                      终止
                    </Button>
                  </>
                )}
                {execution?.status === 'paused' && (
                  <>
                    <Button icon={<PlayCircleOutlined />} loading={resuming} onClick={handleResume} size="small">
                      恢复
                    </Button>
                    <Button icon={<StopOutlined />} danger loading={cancelling} onClick={handleCancel} size="small">
                      终止
                    </Button>
                  </>
                )}
              </div>
            )}

            {/* Error */}
            {execution.error && (
              <Alert
                type="error"
                showIcon
                message="执行错误"
                description={
                  <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 12 }}>
                    {execution.error}
                  </pre>
                }
              />
            )}

            {/* Trace / Log entries */}
            <div>
              <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>
                执行追踪
              </Text>
              {execution.trace && execution.trace.length > 0 ? (
                <List
                  size="small"
                  dataSource={execution.trace}
                  renderItem={(entry: TraceEntry) => (
                    <List.Item style={{ padding: '6px 0' }}>
                      <div style={{ width: '100%' }}>
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <Space size={4}>
                            <Tag
                              color={
                                entry.event === 'node_complete' ? 'green' :
                                entry.event === 'node_start' ? 'blue' :
                                entry.event === 'node_failed' ? 'red' :
                                entry.event === 'node_skipped' ? 'default' :
                                entry.event === 'error' ? 'red' :
                                'blue'
                              }
                              style={{ fontSize: 11, lineHeight: '18px' }}
                            >
                              {entry.event === 'node_complete' ? '完成' :
                               entry.event === 'node_start' ? '开始' :
                               entry.event === 'node_failed' ? '失败' :
                               entry.event === 'node_skipped' ? '跳过' :
                               entry.event === 'tool_call' ? '工具' :
                               entry.event === 'knowledge_retrieval' ? '知识' :
                               entry.event}
                            </Tag>
                            {entry.node_label && (
                              <Text strong style={{ fontSize: 12 }}>{entry.node_label}</Text>
                            )}
                          </Space>
                          {entry.timestamp && (
                            <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                              {new Date(entry.timestamp).toLocaleTimeString()}
                            </Text>
                          )}
                        </div>
                        {entry.message && (
                          <div style={{ marginTop: 2, marginLeft: 4 }}>
                            <Text style={{ fontSize: 12, color: '#595959' }}>
                              {entry.message}
                            </Text>
                          </div>
                        )}
                        {entry.duration_ms != null && (
                          <div style={{ marginTop: 2, marginLeft: 4 }}>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              耗时: {entry.duration_ms < 1000 ? `${entry.duration_ms}ms` : `${(entry.duration_ms / 1000).toFixed(2)}s`}
                            </Text>
                          </div>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {execution.status === 'running' ? '等待追踪数据...' : '暂无追踪记录'}
                </Text>
              )}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Text type="secondary">暂无执行结果</Text>
          </div>
        )}
      </Drawer>
    </div>
  );
}
