import React, { useState } from 'react';
import type { AgentEventEnvelope } from '../../hooks/types';

interface EventEnvelopeInspectorProps {
  selectedEvent: AgentEventEnvelope | null;
}

export const EventEnvelopeInspector: React.FC<EventEnvelopeInspectorProps> = ({
  selectedEvent,
}) => {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!selectedEvent) {
    return (
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md text-xs font-mono text-outline text-center shadow-sm">
        Select an event from the stream to inspect its envelope.
      </div>
    );
  }

  const rawJsonString = JSON.stringify(selectedEvent.raw || selectedEvent, null, 2);
  const isTruncated = rawJsonString.length > 5000;
  const displayJson = isTruncated
    ? rawJsonString.substring(0, 5000) + '\n... [Truncated for display performance]'
    : rawJsonString;

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col gap-space-sm shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
          <span className="font-mono text-[11px] uppercase tracking-wider font-semibold text-on-surface">
            Event Envelope Inspector
          </span>
        </div>
        <span className="font-mono text-[10px] text-primary truncate max-w-[140px]">
          {selectedEvent.id || 'evt_unspecified'}
        </span>
      </div>

      {/* Metadata Table */}
      <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] font-mono py-1">
        <div className="text-outline">Timestamp:</div>
        <div className="text-on-surface truncate">
          {selectedEvent.timestamp ? new Date(selectedEvent.timestamp).toLocaleTimeString() : 'n/a'}
        </div>

        <div className="text-outline">Agent:</div>
        <div className="text-on-surface truncate font-semibold">
          {selectedEvent.agent || 'n/a'}
        </div>

        <div className="text-outline">Step:</div>
        <div className="text-on-surface truncate">
          {selectedEvent.step ? String(selectedEvent.step) : 'n/a'}
        </div>

        <div className="text-outline">Event Type:</div>
        <div className="text-on-surface truncate">
          {selectedEvent.eventType || 'n/a'}
        </div>

        <div className="text-outline">Tool:</div>
        <div className="text-tertiary truncate">
          {selectedEvent.tool || 'None'}
        </div>

        <div className="text-outline">Model:</div>
        <div className="text-primary truncate">
          {selectedEvent.model || 'n/a'}
        </div>
      </div>

      {/* Expandable Raw JSON View */}
      <div className="pt-2 border-t border-outline-variant/20">
        <button
          type="button"
          onClick={() => setShowRawJson((prev) => !prev)}
          className="flex items-center justify-between w-full py-1 text-xs font-mono text-outline hover:text-on-surface transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <span>&lt;&gt;</span>
            <span>View Raw JSON Envelope</span>
          </span>
          <span className="text-[10px]">{showRawJson ? '▲ Hide' : '▼ Expand'}</span>
        </button>

        {showRawJson && (
          <pre className="mt-2 p-2.5 rounded bg-surface-container-lowest border border-outline-variant/20 font-mono text-[10px] text-on-surface-variant overflow-x-auto max-h-48 whitespace-pre-wrap">
            {displayJson}
          </pre>
        )}
      </div>

      {/* Client Verification Note */}
      <div className="p-2 rounded bg-surface-container/60 border border-outline-variant/15 text-[10px] font-mono text-outline leading-tight">
        Client Verification: Frontend-only rendering. Consumes WebSocket events from Tamanna&apos;s backend and Sanjeevni&apos;s LangGraph agents. Zero teammate backend mutations required.
      </div>
    </div>
  );
};
