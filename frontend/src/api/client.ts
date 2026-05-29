import axios from 'axios';
import type { Workflow, Execution, User, AgentConfig } from '@/types';

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
};

export const executionApi = {
  get: (id: string) => client.get<Execution>(`/workflows/executions/${id}`).then(r => r.data),
  pause: (id: string) => client.post<Execution>(`/workflows/executions/${id}/pause`).then(r => r.data),
  resume: (id: string) => client.post<Execution>(`/workflows/executions/${id}/resume`).then(r => r.data),
  cancel: (id: string) => client.post<Execution>(`/workflows/executions/${id}/cancel`).then(r => r.data),
};

export const knowledgeApi = {
  createCollection: (name: string, dimension = 1024) =>
    client.post('/knowledge/collections', null, { params: { name, dimension } }),

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
};

export const agentApi = {
  list: () => client.get<AgentConfig[]>('/api/v1/agents').then(r => r.data),
  register: (agent: Partial<AgentConfig>) =>
    client.post<AgentConfig>('/api/v1/agents', agent).then(r => r.data),
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
