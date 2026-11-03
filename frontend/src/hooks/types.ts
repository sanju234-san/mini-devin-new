/**
 * WebSocket Types for Mini-Devin Live Agent Telemetry
 *
 * Types strictly reflect the architectural boundary between:
 * - Tamanna (Backend WebSocket transport & lifecycle)
 * - Sanjeevni (Agent event envelope & step schemas)
 * - Nikunj (Frontend consumption hook & Task 4 Live Console)
 */

export type SocketConnectionState =
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'DISCONNECTED';

// Native WebSocket readyState mappings:
// 0 = CONNECTING, 1 = OPEN, 2 = CLOSING, 3 = CLOSED
export type SocketReadyState = 0 | 1 | 2 | 3;

/**
 * Dual-compatible event envelope representing both legacy camelCase
 * and Sanjeevni's authoritative StepEvent schema (docs/design/schemas.md §4).
 */
export interface AgentEventEnvelope {
  id?: string;
  event_id?: string;
  eventType?: string;
  event_type?: string;
  runId?: string;
  run_id?: string;
  agent?: string;
  step?: string | number;
  tool?: string;
  tool_name?: string;
  model?: string;
  model_info?: {
    kind?: string;
    name?: string;
    provider?: string;
    tier?: string;
  };
  tokens?: {
    input_tokens?: number;
    output_tokens?: number;
  };
  message?: string;
  plan_version_id?: string;
  timestamp?: string;
  payload?: unknown;
  raw?: unknown;
}

export interface SocketTelemetry {
  connectionState: SocketConnectionState;
  readyState: SocketReadyState;
  uptimeSeconds: number;
  ingestedEventCount: number;
  parseErrorCount: number;
  lastMessageTimestamp: string | null;
  reconnectAttempt: number;
  targetUri: string;
}

export interface UseAgentRunSocketOptions {
  autoConnect?: boolean;
  bufferCap?: number;
  maxReconnectAttempts?: number;
  onEvent?: (event: AgentEventEnvelope) => void;
  onError?: (error: Event | Error) => void;
}

/**
 * Return signature of useAgentRunSocket().
 * Directly consumed by Task 4's LiveConsole.
 */
export interface UseAgentRunSocketReturn {
  connectionState: SocketConnectionState;
  readyState: SocketReadyState;
  events: AgentEventEnvelope[];
  latestEvent: AgentEventEnvelope | null;
  telemetry: SocketTelemetry;
  connect: () => void;
  disconnect: () => void;
  clearBuffer: () => void;
  error: Error | null;
}
