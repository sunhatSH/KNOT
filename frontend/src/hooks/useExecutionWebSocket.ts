import { useState, useEffect, useRef, useCallback } from 'react';
import type { Execution } from '@/types';

interface WSExecutionUpdate {
  type: 'execution_update';
  data: Execution;
}

type WSMessage = WSExecutionUpdate;

const MAX_RECONNECT_DELAY = 30000; // 30s cap
const BASE_RECONNECT_DELAY = 1000; // 1s initial

/**
 * React hook that connects to the KNOT WebSocket endpoint for
 * real-time execution updates.
 *
 * - Connects when `executionId` is provided.
 * - Auto-reconnects with exponential backoff on disconnect.
 * - Returns the latest execution state pushed by the server.
 * - The caller can use `connected` to decide whether to fall back
 *   to REST polling.
 *
 * @param executionId - The execution ID to subscribe to.
 * @returns An object with the latest `execution` state, a `connected`
 *          flag, and the raw WebSocket instance (for advanced usage).
 */
export function useExecutionWebSocket(executionId: string | undefined) {
  const [execution, setExecution] = useState<Execution | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
  const mountedRef = useRef(true);

  // Clear execution state when executionId changes
  useEffect(() => {
    setExecution(null);
    setConnected(false);
    setError(null);
    retryCountRef.current = 0;
  }, [executionId]);

  const connect = useCallback(() => {
    if (!executionId) return;

    // Determine protocol based on page protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/executions/${executionId}`;

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnected(true);
      setError(null);
      retryCountRef.current = 0;

      // Send subscription message (informational — server also
      // auto-registers on connect).
      ws.send(JSON.stringify({
        type: 'subscribe',
        execution_id: executionId,
      }));
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === 'execution_update' && msg.data) {
          setExecution(msg.data);
        }
      } catch {
        // Ignore malformed messages (e.g., keep-alive pings)
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setError('WebSocket connection error');
      // onclose will fire after onerror, so reconnect is handled there
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);

      // Exponential backoff reconnect
      const delay = Math.min(
        BASE_RECONNECT_DELAY * 2 ** retryCountRef.current,
        MAX_RECONNECT_DELAY,
      );
      retryCountRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) {
          connect();
        }
      }, delay);
    };
  }, [executionId]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;

      // Clean up WebSocket
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // Clear pending reconnect
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [connect]);

  return { execution, connected, error };
}
