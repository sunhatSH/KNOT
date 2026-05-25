import { create } from 'zustand';
import type { Workflow, Edge, Node } from '@/types';

interface WorkflowState {
  workflows: Workflow[];
  currentWorkflow: Workflow | null;
  loading: boolean;

  setWorkflows: (wfs: Workflow[]) => void;
  setCurrentWorkflow: (wf: Workflow | null) => void;
  setLoading: (v: boolean) => void;
  updateNodes: (nodes: Node[]) => void;
  updateEdges: (edges: Edge[]) => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [],
  currentWorkflow: null,
  loading: false,

  setWorkflows: (workflows) => set({ workflows }),
  setCurrentWorkflow: (currentWorkflow) => set({ currentWorkflow }),
  setLoading: (loading) => set({ loading }),

  updateNodes: (nodes) => {
    const wf = get().currentWorkflow;
    if (wf) set({ currentWorkflow: { ...wf, nodes } });
  },

  updateEdges: (edges) => {
    const wf = get().currentWorkflow;
    if (wf) set({ currentWorkflow: { ...wf, edges } });
  },
}));
