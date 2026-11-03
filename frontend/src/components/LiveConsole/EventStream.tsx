import React, { useRef, useEffect } from 'react';
import type { AgentEventEnvelope, SocketConnectionState } from '../../hooks/types';
import { EventCard } from './EventCard';

interface EventStreamProps {
  events: AgentEventEnvelope[];
  connectionState: SocketConnectionState;
  selectedEventId: string | null;
  onSelectEvent: (event: AgentEventEnvelope) => void;
  autoScroll: boolean;
  parseErrorCount: number;
  bufferCap: number;
  runId?: string | null;
  error?: Error | null;
  targetUri: string;
}

export const EventStream: React.FC<EventStreamProps> = ({
  events,
  connectionState,
  selectedEventId,
  onSelectEvent,
  autoScroll,
  parseErrorCount,
  bufferCap,
  runId,
  error,
  targetUri,
}) => {
  const streamBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && streamBottomRef.current) {
      streamBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col justify-between overflow-hidden shadow-sm h-[680px]">
      {/* Scrollable Event Area */}
      <div className="flex-1 p-space-md overflow-y-auto flex flex-col gap-space-sm" role="log" aria-label="Agent Event Stream">
        {/* Error Banner if hook exposed an error */}
        {error && (
          <div className="p-3 rounded-lg bg-red-950/30 border border-red-500/30 text-xs font-mono text-red-300 flex items-center gap-2">
            <svg className="w-4 h-4 text-red-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="truncate">{error.message}</span>
          </div>
        )}

        {/* Empty / State Views */}
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-outline">
            {connectionState === 'CONNECTING' ? (
              <>
                <span className="w-6 h-6 rounded-full border-2 border-primary border-t-transparent animate-spin mb-3" />
                <span className="font-semibold text-sm text-on-surface">
                  Connecting to WebSocket Stream...
                </span>
                <span className="font-mono text-xs text-outline mt-1 truncate max-w-sm">
                  {targetUri}
                </span>
              </>
            ) : connectionState === 'RECONNECTING' ? (
              <>
                <span className="w-6 h-6 rounded-full border-2 border-amber-400 border-t-transparent animate-spin mb-3" />
                <span className="font-semibold text-sm text-amber-300">
                  Reconnecting to Stream (Exponential Backoff)...
                </span>
                <span className="font-mono text-xs text-outline mt-1">
                  Awaiting socket reconnection
                </span>
              </>
            ) : (
              <>
                <svg className="w-10 h-10 text-outline/40 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
                <span className="font-semibold text-sm text-on-surface">
                  No WebSocket Events Recorded Yet
                </span>
                <p className="text-xs text-on-surface-variant max-w-sm mt-1 leading-relaxed">
                  Start an autonomous agent run to ingest real-time step execution frames, tool calls, and model reasoning traces.
                </p>
              </>
            )}
          </div>
        ) : (
          events.map((evt, idx) => (
            <EventCard
              key={evt.id || idx}
              event={evt}
              isSelected={selectedEventId === (evt.id || String(idx))}
              onSelect={onSelectEvent}
            />
          ))
        )}

        <div ref={streamBottomRef} />
      </div>

      {/* Stream Footer Telemetry Strip */}
      <div className="px-space-md py-2 bg-surface-container border-t border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-outline">
        <div className="flex items-center gap-2 truncate">
          <svg className="w-3.5 h-3.5 text-primary flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="4 17 10 11 4 5" />
            <line x1="12" y1="19" x2="20" y2="19" />
          </svg>
          <span className="truncate">
            Raw frame receiver connected: <code className="text-on-surface">useAgentRunSocket(&quot;{runId || 'default'}&quot;)</code>
          </span>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                parseErrorCount > 0 ? 'bg-amber-400' : 'bg-emerald-400'
              }`}
            />
            <span>{parseErrorCount} dropped frames</span>
          </span>
          <span className="text-outline-variant">|</span>
          <span>
            Buffer: {events.length}/{bufferCap}
          </span>
        </div>
      </div>
    </div>
  );
};
