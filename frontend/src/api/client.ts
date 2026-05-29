import axios from 'axios';
import type { Workflow, Execution, User, AgentConfig, WorkflowTemplate, WorkflowVersion } from '@/types';

const client = axios.create({ baseURL: '/api/v1' });

// Request interceptor: attach auth token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('knot-token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('knot-token');
      // Only redirect if not already on an auth page
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const workflowApi = {
  list: () => client.get<Workflow[]>('/workflows').then(r => r.data),

  get: (id: string) => client.get<Workflow>(`/workflows/${id}`).then(r => r.data),

  create: (wf: Partial<Workflow>) =>
    client.post<Workflow>('/workflows', wf).then(r => r.data),

  execute: (id: string, context?: Record<string, unknown>) =>
    client.post<Execution>(`/workflows/${id}/execute`, context || {}).then(r => r.data),

  getExecution: (id: string) =>
    client.get<Execution>(`/workflows/executions/${id}`).then(r => r.data),

  createFromNL: (description: string) =>
    client.post<Workflow>('/workflows/from-nl', { description }).then(r => r.data),

  // ── Version History ──────────────────────────────────────────────────────

  listVersions: (id: string) =>
    client.get<WorkflowVersion[]>(`/workflows/${id}/versions`).then(r => r.data),

  getVersion: (id: string, version: number) =>
    client.get<WorkflowVersion>(`/workflows/${id}/versions/${version}`).then(r => r.data),

  restoreVersion: (id: string, version: number) =>
    client.post<Workflow>(`/workflows/${id}/versions/restore/${version}`).then(r => r.data),
};

export const executionApi = {
  list: (limit?: number) =>
    client.get<Execution[]>('/workflows/executions', { params: { limit } }).then(r => r.data),
  get: (id: string) => client.get<Execution>(`/workflows/executions/${id}`).then(r => r.data),
  pause: (id: string) => client.post<Execution>(`/workflows/executions/${id}/pause`).then(r => r.data),
  resume: (id: string) => client.post<Execution>(`/workflows/executions/${id}/resume`).then(r => r.data),
  cancel: (id: string) => client.post<Execution>(`/workflows/executions/${id}/cancel`).then(r => r.data),
};

export const knowledgeApi = {
  createCollection: (name: string, dimension = 1024) =>
    client.post('/knowledge/collections', null, { params: { name, dimension } }),

  listCollections: () =>
    client.get<{name: string; description?: string; chunk_count: number; dimension: number; created_at: string}[]>('/knowledge/collections').then(r => r.data),

  deleteCollection: (name: string) =>
    client.delete(`/knowledge/collections/${encodeURIComponent(name)}`).then(r => r.data),

  search: (collectionName: string, query: string, topK = 10) =>
    client.post('/knowledge/search', null, { params: { collection_name: collectionName, query, top_k: topK } }),

  uploadDocument: (collectionName: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/knowledge/documents/upload', formData, {
      params: { collection_name: collectionName },
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  listDocuments: (collectionName: string, params?: { page?: number; page_size?: number; type?: string; date_from?: string; date_to?: string }) =>
    client.get<{documents: any[]; total: number; page: number; page_size: number}>(`/knowledge/collections/${encodeURIComponent(collectionName)}/documents`, { params }).then(r => r.data),

  deleteDocument: (collectionName: string, documentId: string) =>
    client.delete(`/knowledge/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`).then(r => r.data),

  batchDeleteDocuments: (collectionName: string, documentIds: string[]) =>
    client.post(`/knowledge/collections/${encodeURIComponent(collectionName)}/documents/batch-delete`, { document_ids: documentIds }).then(r => r.data),

  getDocument: (collectionName: string, documentId: string) =>
    client.get(`/knowledge/collections/${encodeURIComponent(collectionName)}/documents/${documentId}`).then(r => r.data),
};

export const agentApi = {
  list: () => client.get<AgentConfig[]>('/api/v1/agents').then(r => r.data),
  register: (agent: Partial<AgentConfig>) =>
    client.post<AgentConfig>('/api/v1/agents', agent).then(r => r.data),
};

export interface TemplateCategory {
  category: string;
  count: number;
}

export const templateApi = {
  list: (params?: { category?: string; search?: string }) =>
    client.get<WorkflowTemplate[]>('/templates', { params }).then(r => r.data),

  get: (id: string) => client.get<WorkflowTemplate>(`/templates/${id}`).then(r => r.data),

  save: (template: Partial<WorkflowTemplate>) =>
    client.post<WorkflowTemplate>('/templates', template).then(r => r.data),

  listCategories: () =>
    client.get<TemplateCategory[]>('/templates/categories').then(r => r.data),

  incrementUse: (id: string) =>
    client.post<WorkflowTemplate>(`/templates/${id}/use`).then(r => r.data),

  instantiate: (id: string) =>
    client.post<Workflow>(`/templates/${id}/instantiate`).then(r => r.data),

  delete: (id: string) => client.delete(`/templates/${id}`),
};

export interface DashboardMetrics {
  total_executions: number;
  execution_counts: Record<string, number>;
  success_rate: number;
  avg_duration_ms: number | null;
  top_slow_nodes: {
    node_id: string;
    node_label: string;
    avg_duration_ms: number;
    total_ms: number;
    count: number;
  }[];
  recent_executions: {
    id: string;
    workflow_id: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_ms: number | null;
    error: string | null;
  }[];
  executions_by_day: { date: string; count: number }[];
}

export const metricsApi = {
  dashboard: () =>
    client.get<DashboardMetrics>('/metrics/dashboard').then(r => r.data),
};

export const authApi = {
  login: (username: string, password: string) =>
    client.post<{access_token: string; token_type: string; user: User}>('/auth/login', null, {
      params: { username, password }
    }).then(r => r.data),

  register: (username: string, password: string, email?: string) =>
    client.post<{id: string; username: string; message: string}>('/auth/register', null, {
      params: { username, password, email: email || '' }
    }).then(r => r.data),

  me: () => client.get<User>('/auth/me').then(r => r.data),
};
