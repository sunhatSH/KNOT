export interface Node {
  id: string;
  type: 'task' | 'condition' | 'parallel' | 'loop' | 'input' | 'output';
  label: string;
  agent_id?: string;
  config: Record<string, unknown>;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  status?: 'pending' | 'running' | 'success' | 'failed' | 'skipped';
}

export interface Edge {
  id: string;
  source_id: string;
  target_id: string;
  label?: string;
  condition?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  global_context: Record<string, unknown>;
  created_at: string;
  tags?: string[];
}

export interface TraceEntry {
  node_id: string;
  node_type: string;
  action?: string;
  timestamp?: string;
  result_summary?: string;
  error?: string;
}

export interface Execution {
  id: string;
  workflow_id: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'paused' | 'cancelled';
  node_states: Record<string, string>;
  global_context: Record<string, unknown>;
  error?: string;
  trace: TraceEntry[];
  started_at?: string;
  completed_at?: string;
}
