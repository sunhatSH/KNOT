import { useCallback } from 'react';
import { Alert } from 'antd';
import {
  CheckCircleFilled,
  CloseCircleFilled,
  WarningFilled,
  InfoCircleFilled,
} from '@ant-design/icons';
import { useNotificationStore } from '@/store/notificationStore';
import type { Notification } from '@/store/notificationStore';

const typeConfig: Record<
  Notification['type'],
  { icon: React.ReactNode; color: string }
> = {
  success: { icon: <CheckCircleFilled />, color: 'var(--notification-success, #52c41a)' },
  error: { icon: <CloseCircleFilled />, color: 'var(--notification-error, #ff4d4f)' },
  warning: { icon: <WarningFilled />, color: 'var(--notification-warning, #faad14)' },
  info: { icon: <InfoCircleFilled />, color: 'var(--notification-info, #1677ff)' },
};

export default function NotificationContainer() {
  const notifications = useNotificationStore((s) => s.notifications);
  const removeNotification = useNotificationStore((s) => s.removeNotification);

  const handleClose = useCallback(
    (id: string) => {
      removeNotification(id);
    },
    [removeNotification],
  );

  if (notifications.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 1050,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 400,
        pointerEvents: 'none',
      }}
    >
      {notifications.map((n) => (
        <div
          key={n.id}
          style={{
            pointerEvents: 'auto',
            animation: 'notifSlideIn 0.25s ease-out',
          }}
        >
          <Alert
            type={n.type}
            message={
              <span style={{ fontWeight: 500, fontSize: 13 }}>{n.title}</span>
            }
            description={
              n.message ? (
                <span style={{ fontSize: 12, color: 'var(--text-secondary, #5a6170)' }}>
                  {n.message}
                </span>
              ) : undefined
            }
            icon={typeConfig[n.type].icon}
            closable
            onClose={() => handleClose(n.id)}
            style={{
              borderRadius: 8,
              border: `1px solid ${typeConfig[n.type].color}22`,
              background: 'var(--bg-card, #fff)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            }}
          />
        </div>
      ))}

      {/* Keyframe animation for slide-in */}
      <style>{`
        @keyframes notifSlideIn {
          from {
            opacity: 0;
            transform: translateX(40px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
