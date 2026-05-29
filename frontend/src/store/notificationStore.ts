import { create } from 'zustand';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number; // ms, 0 = sticky
}

interface NotificationStore {
  notifications: Notification[];
  addNotification: (n: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

let counter = 0;

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],

  addNotification: (n) => {
    const id = `notif_${Date.now()}_${++counter}`;
    const notification: Notification = { ...n, id };

    set((s) => ({
      notifications: [...s.notifications, notification],
    }));

    // Auto-remove after duration (default: success/info=4s, warning/error=sticky)
    const duration =
      n.duration !== undefined
        ? n.duration
        : n.type === 'success' || n.type === 'info'
          ? 4000
          : 0;

    if (duration > 0) {
      setTimeout(() => {
        get().removeNotification(id);
      }, duration);
    }
  },

  removeNotification: (id) => {
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
    }));
  },

  success: (title, message) => {
    get().addNotification({ type: 'success', title, message });
  },

  error: (title, message) => {
    get().addNotification({ type: 'error', title, message });
  },

  warning: (title, message) => {
    get().addNotification({ type: 'warning', title, message });
  },

  info: (title, message) => {
    get().addNotification({ type: 'info', title, message });
  },
}));
