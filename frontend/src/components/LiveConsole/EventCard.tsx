import React from 'react';
import type { AgentEventEnvelope } from '../../hooks/types';

interface EventCardProps {
  event: AgentEventEnvelope;
  isSelected: boolean;
  onSelect: (event: AgentEventEnvelope) => void;
}

export const EventCard: React.FC<EventCardProps> = ({
  event,
  isSelected,
  onSelect,
}) => {
  const agentName = event.agent || 'SYSTEM';
  const eventTitle =
    (event.payload as { message?: string })?.message ||
    event.eventType ||
    'Agent step execution';
  const timestampStr = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString()
    : 'n/a';
  const eventId = event.id || 'evt_unspecified';

  // Agent badge color scheme
  const agentLower = agentName.toLowerCase();
  let agentBadgeStyle = 'bg-primary/10 text-primary border-primary/30';
  if (agentLower.includes('plan')) {
    agentBadgeStyle = 'bg-secondary/15 text-secondary border-secondary/30';
  } else if (agentLower.includes('coder') || agentLower.includes('code')) {
    agentBadgeStyle = 'bg-teal-500/15 text-teal-400 border-teal-500/30';
  } else if (agentLower.includes('retriev')) {
    agentBadgeStyle = 'bg-tertiary/15 text-tertiary border-tertiary/30';
  } else if (agentLower.includes('test')) {
    agentBadgeStyle = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
  }

  // Derive status badge
  const typeLower = (event.eventType || '').toLowerCase();
  let statusBadge = 'RUNNING';
  let statusColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30';

  if (typeLower.includes('finish') || typeLower.includes('complete')) {
    statusBadge = 'COMPLETED';
    statusColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  } else if (typeLower.includes('error') || typeLower.includes('fail')) {
    statusBadge = 'FAILED';
    statusColor = 'text-red-400 bg-red-500/10 border-red-500/30';
  }

  // Snippet description
  const payloadDetails =
    (event.payload as { details?: string })?.details ||
    (event.payload as { query?: string })?.query ||
    (event.payload as { tokenDelta?: string })?.tokenDelta ||
    (event.payload as { targetFile?: string })?.targetFile;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-selected={isSelected}
      onClick={() => onSelect(event)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(event);
        }
      }}
      className={`rounded-lg p-space-md border transition-all text-left cursor-pointer flex flex-col gap-2 ${
        isSelected
          ? 'bg-surface-container-high border-primary ring-1 ring-primary/40 shadow-md'
          : 'bg-surface-container/70 border-outline-variant/30 hover:bg-surface-container-high hover:border-outline-variant/50'
      }`}
    >
      {/* Top Header: Timestamp, Agent Badge, Title, Status */}
      <div className="flex items-start justify-between gap-2 flex-wrap text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[11px] text-outline">
            {timestampStr}
          </span>
          <span
            className={`px-1.5 py-0.5 rounded font-mono text-[10px] uppercase font-semibold border ${agentBadgeStyle}`}
          >
            [{agentName.toUpperCase()}]
          </span>
          <span className="font-semibold text-on-surface text-xs">
            {eventTitle}
          </span>
        </div>

        <span
          className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider font-semibold border ${statusColor}`}
        >
          {statusBadge}
        </span>
      </div>

      {/* Snippet / Code block if details exist */}
      {payloadDetails && (
        <div className="p-2 rounded bg-surface-container-lowest border border-outline-variant/20 font-mono text-[11px] text-on-surface-variant overflow-x-auto">
          <code>{payloadDetails}</code>
        </div>
      )}

      {/* Footer Meta Row: Model, Tool, Event ID */}
      <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-outline pt-1 border-t border-outline-variant/15 flex-wrap">
        <div className="flex items-center gap-3">
          {event.model ? (
            <span className="flex items-center gap-1 text-on-surface-variant">
              <span>Model:</span>
              <span className="text-primary font-medium">{event.model}</span>
            </span>
          ) : (
            <span>Model: n/a</span>
          )}

          {event.tool ? (
            <span className="flex items-center gap-1 text-on-surface-variant">
              <span>Tool:</span>
              <span className="text-tertiary font-medium">{event.tool}</span>
            </span>
          ) : (
            <span>Tool: None</span>
          )}
        </div>

        <span className="text-outline-variant text-[10px]">
          # id: {eventId}
        </span>
      </div>
    </div>
  );
};
