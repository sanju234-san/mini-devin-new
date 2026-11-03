import React, { useState, useRef, useEffect } from 'react';
import type { AgentEventEnvelope } from '../../hooks/types';

interface ClientEventPreviewProps {
  events: AgentEventEnvelope[];
  onClearBuffer: () => void;
  bufferCap?: number;
  lastMessageTimestamp?: string | null;
}

export const ClientEventPreview: React.FC<ClientEventPreviewProps> = ({
  events,
  onClearBuffer,
  bufferCap = 500,
  lastMessageTimestamp,
}) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-md">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-tertiary">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-on-surface">
              Client Event Preview
            </h3>
          </div>

          <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-outline border border-outline-variant/30">
            {events.length} / {bufferCap} buffered
          </span>
        </div>

        <p className="text-xs text-on-surface-variant">
          Lightweight FIFO ingestion buffer. Verifies envelope decoding prior to Task 4 deep console consumption.
        </p>

        {/* Action Controls Bar */}
        <div className="flex items-center justify-between gap-2 pt-1 pb-1 text-xs font-mono">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setAutoScroll((prev) => !prev)}
              className={`px-2 py-1 rounded border text-[11px] transition-colors ${
                autoScroll
                  ? 'bg-primary/10 border-primary/30 text-primary'
                  : 'bg-surface-container-high border-outline-variant/30 text-outline'
              }`}
            >
              Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
            </button>

            <button
              type="button"
              onClick={onClearBuffer}
              disabled={events.length === 0}
              className="px-2 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-[11px] disabled:opacity-40 transition-colors"
            >
              Clear Buffer
            </button>
          </div>

          <span className="text-outline text-[11px] hidden sm:inline">
            Last Event:{' '}
            {lastMessageTimestamp
              ? new Date(lastMessageTimestamp).toLocaleTimeString()
              : 'None'}
          </span>
        </div>

        {/* Event Stream Container */}
        <div
          ref={scrollRef}
          className="h-64 rounded-lg bg-surface-container-lowest border border-outline-variant/30 p-space-sm font-mono text-xs overflow-y-auto flex flex-col gap-2"
        >
          {events.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-outline">
              <svg className="w-8 h-8 text-outline/50 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10" />
                <line x1="8" y1="12" x2="16" y2="12" />
              </svg>
              <span className="text-xs font-medium text-on-surface-variant">
                No WebSocket events received yet
              </span>
              <span className="text-[11px] text-outline mt-1 max-w-xs">
                Connect to a running agent session to ingest real-time step frames.
              </span>
            </div>
          ) : (
            events.map((evt, idx) => (
              <div
                key={evt.id || idx}
                className="p-2 rounded bg-surface-container/60 border border-outline-variant/20 flex flex-col gap-1 text-[11px]"
              >
                <div className="flex items-center justify-between text-outline text-[10px]">
                  <span className="text-tertiary font-semibold">
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'Recent'}
                  </span>
                  <span className="px-1.5 py-0.2 rounded bg-surface-container-high text-outline-variant uppercase">
                    {evt.eventType || 'agent.event'}
                  </span>
                </div>

                {evt.agent && (
                  <div className="text-on-surface font-medium">
                    [{evt.agent}] {evt.step ? `Step ${evt.step}` : ''}
                  </div>
                )}

                <pre className="text-[10px] text-outline overflow-x-auto whitespace-pre-wrap">
                  {typeof evt.raw === 'string'
                    ? evt.raw
                    : JSON.stringify(evt.payload || evt.raw || evt, null, 2)}
                </pre>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
