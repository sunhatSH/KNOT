import { create } from 'zustand';
import { authApi } from '@/api/client';
import type { User } from '@/types';

const TOKEN_KEY = 'knot-token';

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, email?: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const res = await authApi.login(username, password);
      localStorage.setItem(TOKEN_KEY, res.access_token);
      set({ token: res.access_token, user: res.user, loading: false });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '登录失败';
      set({ error: msg, loading: false });
      throw err;
    }
  },

  register: async (username: string, password: string, email?: string) => {
    set({ loading: true, error: null });
    try {
      await authApi.register(username, password, email);
      set({ loading: false });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '注册失败';
      set({ error: msg, loading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    set({ token: null, user: null, error: null });
  },

  fetchUser: async () => {
    const { token } = get();
    if (!token) return;
    try {
      const user = await authApi.me();
      set({ user });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      set({ token: null, user: null });
    }
  },

  clearError: () => set({ error: null }),
}));

// Convenience selector
export const useIsAuthenticated = () => useAuthStore((s) => !!s.token);
