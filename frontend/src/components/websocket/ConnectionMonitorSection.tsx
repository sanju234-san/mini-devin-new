'use client';

import React, { useState } from 'react';
import { useAgentRunSocket, getWebSocketUri } from '../../hooks/useAgentRunSocket';
import type {
  SocketConnectionState,
  SocketTelemetry,
  AgentEventEnvelope,
} from '../../hooks/types';
import { SocketTelemetryCard } from './SocketTelemetryCard';
import { ClientEventPreview } from './ClientEventPreview';
import { LifecycleStatesCard } from './LifecycleStatesCard';
import { PipelineContractCard } from './PipelineContractCard';

type PreviewMode =
  | 'CONNECTED'
  | 'CONNECTING'
  | 'RECONNECTING'
  | 'DISCONNECTED'
  | 'live';

export const ConnectionMonitorSection: React.FC = () => {
  const [previewMode, setPreviewMode] = useState<PreviewMode>('DISCONNECTED');
  const [selectedRunId] = useState<string>('sample-run');

  // Real hook instance
  const liveSocket = useAgentRunSocket(selectedRunId, {
    autoConnect: false, // User can manually trigger live connection or preview
    bufferCap: 500,
  });

  // Construct mock telemetry for static preview mode
  const targetUri = getWebSocketUri(selectedRunId);

  const getActiveTelemetry = (): SocketTelemetry => {
    if (previewMode === 'live') {
      return liveSocket.telemetry;
    }

    const mockStates: Record<
      'CONNECTED' | 'CONNECTING' | 'RECONNECTING' | 'DISCONNECTED',
      SocketTelemetry
    > = {
      CONNECTED: {
        connectionState: 'CONNECTED',
        readyState: 1,
        uptimeSeconds: 522, // 08:42
        ingestedEventCount: 142,
        parseErrorCount: 0,
        lastMessageTimestamp: new Date().toISOString(),
        reconnectAttempt: 0,
        targetUri,
      },
      CONNECTING: {
        connectionState: 'CONNECTING',
        readyState: 0,
        uptimeSeconds: 0,
        ingestedEventCount: 0,
        parseErrorCount: 0,
        lastMessageTimestamp: null,
        reconnectAttempt: 0,
        targetUri,
      },
      RECONNECTING: {
        connectionState: 'RECONNECTING',
        readyState: 3,
        uptimeSeconds: 0,
        ingestedEventCount: 42,
        parseErrorCount: 0,
        lastMessageTimestamp: new Date(Date.now() - 5000).toISOString(),
        reconnectAttempt: 2,
        targetUri,
      },
      DISCONNECTED: {
        connectionState: 'DISCONNECTED',
        readyState: 3,
        uptimeSeconds: 0,
        ingestedEventCount: 0,
        parseErrorCount: 0,
        lastMessageTimestamp: null,
        reconnectAttempt: 0,
        targetUri,
      },
    };

    return mockStates[previewMode];
  };

  const currentTelemetry = getActiveTelemetry();
  const currentEvents: AgentEventEnvelope[] =
    previewMode === 'live'
      ? liveSocket.events
      : previewMode === 'CONNECTED'
      ? [
          {
            id: 'evt-1',
            agent: 'Planner',
            step: '1.1',
            eventType: 'agent.step_finish',
            timestamp: new Date(Date.now() - 30000).toISOString(),
            payload: { message: 'Planning complete. Decomposed issue into 3 files.' },
          },
          {
            id: 'evt-2',
            agent: 'Retrieval',
            step: '1.2',
            eventType: 'tool.execution',
            timestamp: new Date(Date.now() - 15000).toISOString(),
            payload: { tool: 'ripgrep', query: 'useAgentRunSocket' },
          },
          {
            id: 'evt-3',
            agent: 'Coder',
            step: '2.1',
            eventType: 'llm.stream_chunk',
            timestamp: new Date().toISOString(),
            payload: { tokenDelta: 'export function useAgentRunSocket' },
          },
        ]
      : [];

  return (
    <section
      className="flex flex-col gap-space-lg pt-space-xs"
      aria-label="WebSocket Client & Connection Monitor"
    >
      {/* Section Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md pb-space-md border-b border-outline-variant/20">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 font-mono text-[11px] text-outline">
            <span>TASK 03</span>
            <span>/</span>
            <span className="text-on-surface-variant font-medium">REAL-TIME INGESTION</span>
            <span>/</span>
            <span className="text-primary truncate">frontend/src/hooks/useAgentRunSocket.ts</span>
          </div>

          <div className="flex items-center gap-space-sm flex-wrap mt-0.5">
            <h2 className="text-xl font-semibold text-on-surface">
              WebSocket Client &amp; Connection Monitor
            </h2>
            <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-surface-container-high text-primary border border-primary/20">
              RFC 6455 Event-Driven (No Polling)
            </span>
          </div>
          <p className="text-sm text-on-surface-variant max-w-3xl">
            Real-time streaming ingestion client consuming broadcast envelopes from Tamanna&apos;s FastAPI backend into a bounded React state buffer for Task 4 Live Console.
          </p>
        </div>

        {/* State Preview Switcher */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-outline px-1">
            UI State Preview:
          </span>
          <div className="inline-flex flex-wrap p-1 rounded-lg bg-surface-container-low border border-outline-variant/30 text-xs">
            {(
              [
                'CONNECTED',
                'CONNECTING',
                'RECONNECTING',
                'DISCONNECTED',
                'live',
              ] as PreviewMode[]
            ).map((mode) => {
              const isActive = previewMode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setPreviewMode(mode)}
                  className={`px-2.5 py-1 rounded font-medium font-mono text-xs transition-all ${
                    isActive
                      ? mode === 'live'
                        ? 'bg-teal-500 text-surface-container-lowest font-bold shadow-sm'
                        : 'bg-primary-container text-on-primary-container shadow-sm font-semibold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  {mode === 'live' ? 'Live Socket' : mode}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Connection Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-space-md py-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20 font-mono text-xs text-outline">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className={`inline-flex rounded-full h-2 w-2 ${
                currentTelemetry.connectionState === 'CONNECTED'
                  ? 'bg-emerald-400'
                  : currentTelemetry.connectionState === 'CONNECTING' ||
                    currentTelemetry.connectionState === 'RECONNECTING'
                  ? 'bg-amber-400 animate-ping'
                  : 'bg-outline'
              }`}
            />
          </span>
          <span className="font-semibold text-on-surface">
            {currentTelemetry.connectionState}
          </span>
          <span className="text-outline-variant">|</span>
          <span className="text-outline text-[11px] truncate max-w-sm">
            {currentTelemetry.targetUri}
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px]">
          {previewMode !== 'live' && (
            <span className="px-1.5 py-0.2 rounded bg-surface-container-high border border-outline-variant/30 text-outline-variant uppercase">
              Static Preview Mode
            </span>
          )}
          {previewMode === 'live' && (
            <span className="text-teal-400 font-semibold">
              Live Hook Active
            </span>
          )}
        </div>
      </div>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg">
        {/* Left: Telemetry & Metrics */}
        <SocketTelemetryCard telemetry={currentTelemetry} />

        {/* Right: Client Event Preview */}
        <ClientEventPreview
          events={currentEvents}
          onClearBuffer={liveSocket.clearBuffer}
          bufferCap={500}
          lastMessageTimestamp={currentTelemetry.lastMessageTimestamp}
        />
      </div>

      {/* Lower Row: Lifecycle States & Architectural Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg">
        <LifecycleStatesCard
          activeState={currentTelemetry.connectionState}
          reconnectAttempt={currentTelemetry.reconnectAttempt}
          onManualConnect={liveSocket.connect}
          onManualDisconnect={liveSocket.disconnect}
        />

        <PipelineContractCard />
      </div>
    </section>
  );
};
