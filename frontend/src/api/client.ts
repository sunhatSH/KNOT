import axios from 'axios';
import type { Workflow, Execution } from '@/types';

const client = axios.create({ baseURL: '/api/v1' });

export const workflowApi = {
  list: () => client.get<Workflow[]>('/workflows').then(r => r.data),

  get: (id: string) => client.get<Workflow>(`/workflows/${id}`).then(r => r.data),

  create: (wf: Partial<Workflow>) =>
    client.post<Workflow>('/workflows', wf).then(r => r.data),

  execute: (id: string, context?: Record<string, unknown>) =>
    client.post<Execution>(`/workflows/${id}/execute`, context || {}).then(r => r.data),

  getExecution: (id: string) =>
    client.get<Execution>(`/workflows/executions/${id}`).then(r => r.data),
};

export const executionApi = {
  get: (id: string) => client.get<Execution>(`/workflows/executions/${id}`).then(r => r.data),
};

export const knowledgeApi = {
  createCollection: (name: string, dimension = 1024) =>
    client.post('/knowledge/collections', null, { params: { name, dimension } }),

  search: (collectionName: string, query: string, topK = 10) =>
    client.post('/knowledge/search', null, { params: { collection_name: collectionName, query, top_k: topK } }),
};
