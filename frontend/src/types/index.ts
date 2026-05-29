export interface Node {
  id: string;
  type: 'task' | 'condition' | 'parallel' | 'loop' | 'input' | 'output';
  label: string;
  agent_id?: string;
  config: Record<string, unknown>;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  status?: 'pending' | 'running' | 'success' | 'failed' | 'skipped';
  timeout_seconds?: number;
  max_retries?: number;
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
  timestamp: string;
  node_id: string;
  node_label?: string;
  event: string;
  message?: string;
  duration_ms?: number | null;
  metadata?: Record<string, unknown>;
}

export interface User {
  id: string;
  username: string;
  email?: string;
  created_at?: string;
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

// ─── Multi-Agent ─────────────────────────────────────────────────────────────

export type MultiAgentMode = 'pipeline' | 'parallel' | 'debate';
export type AgentRole =
  | 'planner'
  | 'executor'
  | 'reviewer'
  | 'observer'
  | 'researcher'
  | 'coder'
  | 'validator'
  | 'summarizer';

export interface AgentConfig {
  id: string;
  name: string;
  role: AgentRole;
  capabilities?: string[];
  model_name?: string;
  model?: string;       // backend field name
  temperature?: number;
  instructions?: string;
  system_prompt?: string; // backend field name
  tools?: string[];     // backend field name
  config?: Record<string, unknown>;
}

export interface AgentTeamMember {
  agent_id: string;
  agent_name: string;
  role: AgentRole;
  temperature: number;
}

// ─── Workflow Version ───────────────────────────────────────────────────────

export interface WorkflowVersion {
  version: number;
  workflow_id: string;
  nodes: Node[];
  edges: Edge[];
  config: Record<string, unknown>;
  saved_at: string;
  saved_by: string;
  message: string;
}

// ─── Workflow Template ──────────────────────────────────────────────────────

export interface WorkflowTemplate {
  id: string;
  name: string;
  description?: string;
  category: string;
  nodes: Node[];
  edges: Edge[];
  config: Record<string, unknown>;
  tags: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}
