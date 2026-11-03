/**
 * useAgentRunSocket Hook (Task 3)
 *
 * Architectural Boundary:
 * FastAPI WebSocket (Tamanna) -> useAgentRunSocket -> React Buffer -> Task 4 LiveConsole
 *
 * Consumer Contract for Task 4 (Live Agent Console):
 * ```typescript
 * const {
 *   connectionState, // 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'
 *   readyState,      // 0 (CONNECTING), 1 (OPEN), 2 (CLOSING), 3 (CLOSED)
 *   events,          // Bounded FIFO buffer of received agent events
 *   latestEvent,     // Most recent envelope
 *   telemetry,       // Honest socket telemetry (uptime, counts, errors, target URI)
 *   connect,         // Manual connect/reconnect function
 *   disconnect,      // Manual disconnect function
 *   clearBuffer,     // Empties event buffer
 *   error            // Latest socket or transport error
 * } = useAgentRunSocket(runId, options);
 * ```
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '../config/env';
import type {
  SocketConnectionState,
  SocketReadyState,
  AgentEventEnvelope,
  SocketTelemetry,
  UseAgentRunSocketOptions,
  UseAgentRunSocketReturn,
} from './types';

/**
 * Derives the WebSocket URL from the configured HTTP base URL.
 * Converts http:// -> ws:// and https:// -> wss://.
 */
export function getWebSocketUri(runId?: string | null): string {
  const httpUrl = API_BASE_URL.replace(/\/+$/, '');
  const wsBase = httpUrl.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
  const path = runId ? `/ws/runs/${encodeURIComponent(runId)}` : '/ws/runs';
  return `${wsBase}${path}`;
}

export function useAgentRunSocket(
  runId?: string | null,
  options: UseAgentRunSocketOptions = {}
): UseAgentRunSocketReturn {
  const {
    autoConnect = true,
    bufferCap = 500,
    maxReconnectAttempts = 5,
    onEvent,
    onError,
  } = options;

  const targetUri = getWebSocketUri(runId);

  // Connection states
  const [connectionState, setConnectionState] =
    useState<SocketConnectionState>('DISCONNECTED');
  const [readyState, setReadyState] = useState<SocketReadyState>(3); // CLOSED by default
  const [events, setEvents] = useState<AgentEventEnvelope[]>([]);
  const [latestEvent, setLatestEvent] = useState<AgentEventEnvelope | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // Telemetry metrics
  const [uptimeSeconds, setUptimeSeconds] = useState<number>(0);
  const [ingestedEventCount, setIngestedEventCount] = useState<number>(0);
  const [parseErrorCount, setParseErrorCount] = useState<number>(0);
  const [lastMessageTimestamp, setLastMessageTimestamp] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);

  // Mutable refs for lifecycle and Strict Mode handling
  const socketRef = useRef<WebSocket | null>(null);
  const isMountedRef = useRef<boolean>(true);
  const isManualCloseRef = useRef<boolean>(false);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const uptimeTimerRef = useRef<NodeJS.Timeout | null>(null);
  const connectedAtRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef<number>(0);

  // Clear event buffer
  const clearBuffer = useCallback(() => {
    setEvents([]);
    setLatestEvent(null);
  }, []);

  // Cleanup helper
  const cleanupTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (uptimeTimerRef.current) {
      clearInterval(uptimeTimerRef.current);
      uptimeTimerRef.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    cleanupTimers();
    if (socketRef.current) {
      try {
        socketRef.current.close(1000, 'Client closed connection');
      } catch {
        // Ignore errors during clean close
      }
      socketRef.current = null;
    }
  }, [cleanupTimers]);

  // Connect function
  const connect = useCallback(() => {
    if (typeof window === 'undefined') return;

    // Reset manual close flag
    isManualCloseRef.current = false;
    cleanupTimers();

    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    setConnectionState('CONNECTING');
    setReadyState(0);
    setError(null);

    try {
      const ws = new WebSocket(targetUri);
      socketRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }

        setConnectionState('CONNECTED');
        setReadyState(1);
        reconnectAttemptRef.current = 0;
        setReconnectAttempt(0);
        connectedAtRef.current = Date.now();

        // Start honest connection duration uptime counter
        if (uptimeTimerRef.current) clearInterval(uptimeTimerRef.current);
        uptimeTimerRef.current = setInterval(() => {
          if (connectedAtRef.current && isMountedRef.current) {
            setUptimeSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
          }
        }, 1000);
      };

      ws.onmessage = (messageEvent: MessageEvent) => {
        if (!isMountedRef.current) return;

        const now = new Date().toISOString();
        setLastMessageTimestamp(now);
        setIngestedEventCount((prev) => prev + 1);

        let parsed: AgentEventEnvelope;
        try {
          if (typeof messageEvent.data === 'string') {
            const json = JSON.parse(messageEvent.data);
            parsed = {
              ...json,
              id: json.id || json.event_id,
              event_id: json.event_id || json.id,
              runId: json.runId || json.run_id,
              run_id: json.run_id || json.runId,
              eventType: json.eventType || json.event_type,
              event_type: json.event_type || json.eventType,
              tool: json.tool || json.tool_name,
              tool_name: json.tool_name || json.tool,
              model: json.model || json.model_info?.name,
              message: json.message || (typeof json.payload === 'string' ? json.payload : undefined),
              timestamp: json.timestamp || now,
              raw: json,
            };
          } else {
            parsed = {
              eventType: 'binary_frame',
              timestamp: now,
              raw: messageEvent.data,
            };
          }
        } catch (parseErr) {
          // Track parse errors honestly without dropping without a trace
          setParseErrorCount((prev) => prev + 1);
          parsed = {
            eventType: 'parse_error',
            timestamp: now,
            payload: { rawText: String(messageEvent.data), error: String(parseErr) },
          };
        }

        setLatestEvent(parsed);
        setEvents((prev) => {
          const next = [...prev, parsed];
          if (next.length > bufferCap) {
            return next.slice(next.length - bufferCap);
          }
          return next;
        });

        if (onEvent) {
          onEvent(parsed);
        }
      };

      ws.onerror = (errEvent) => {
        if (!isMountedRef.current) return;
        const err = new Error(`WebSocket error for ${targetUri}`);
        setError(err);
        if (onError) onError(err);
      };

      ws.onclose = (closeEvent) => {
        if (!isMountedRef.current) return;

        setReadyState(3);
        connectedAtRef.current = null;
        if (uptimeTimerRef.current) {
          clearInterval(uptimeTimerRef.current);
          uptimeTimerRef.current = null;
        }

        // Normal closure or manual disconnect: transition directly to DISCONNECTED
        if (closeEvent.code === 1000 || isManualCloseRef.current) {
          setConnectionState('DISCONNECTED');
          return;
        }

        // Abnormal drop: trigger bounded exponential backoff reconnect
        if (reconnectAttemptRef.current < maxReconnectAttempts) {
          setConnectionState('RECONNECTING');
          reconnectAttemptRef.current += 1;
          setReconnectAttempt(reconnectAttemptRef.current);

          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttemptRef.current - 1),
            15000
          );

          reconnectTimerRef.current = setTimeout(() => {
            if (isMountedRef.current && !isManualCloseRef.current) {
              connect();
            }
          }, delay);
        } else {
          setConnectionState('DISCONNECTED');
        }
      };
    } catch (createErr) {
      setConnectionState('DISCONNECTED');
      setReadyState(3);
      const err =
        createErr instanceof Error
          ? createErr
          : new Error(`Failed to create WebSocket: ${String(createErr)}`);
      setError(err);
      if (onError) onError(err);
    }
  }, [
    targetUri,
    bufferCap,
    maxReconnectAttempts,
    onEvent,
    onError,
    cleanupTimers,
  ]);

  // Manual disconnect
  const disconnect = useCallback(() => {
    isManualCloseRef.current = true;
    closeSocket();
    setConnectionState('DISCONNECTED');
    setReadyState(3);
    connectedAtRef.current = null;
    setUptimeSeconds(0);
  }, [closeSocket]);

  // Main lifecycle effect (React 18 Strict Mode safe)
  useEffect(() => {
    isMountedRef.current = true;

    if (autoConnect) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      closeSocket();
    };
  }, [autoConnect, connect, closeSocket]);

  const telemetry: SocketTelemetry = {
    connectionState,
    readyState,
    uptimeSeconds,
    ingestedEventCount,
    parseErrorCount,
    lastMessageTimestamp,
    reconnectAttempt,
    targetUri,
  };

  return {
    connectionState,
    readyState,
    events,
    latestEvent,
    telemetry,
    connect,
    disconnect,
    clearBuffer,
    error,
  };
}
