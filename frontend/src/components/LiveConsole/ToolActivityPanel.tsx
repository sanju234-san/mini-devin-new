import React from 'react';
import type { AgentEventEnvelope } from '../../hooks/types';

interface ToolActivityPanelProps {
  events: AgentEventEnvelope[];
}

export const ToolActivityPanel: React.FC<ToolActivityPanelProps> = ({ events }) => {
  // Extract all events that involve a tool
  const toolEvents = events.filter(
    (e) => e.tool || (e.eventType && e.eventType.toLowerCase().includes('tool'))
  );

  const recentTools = toolEvents.slice(-5).reverse();

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-sm">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
            <span className="font-mono text-[11px] uppercase tracking-wider font-semibold text-on-surface">
              Live Tool Activity
            </span>
          </div>
          <span className="font-mono text-[10px] text-outline">
            {toolEvents.length} Recorded
          </span>
        </div>

        {/* Tool Activity List */}
        {recentTools.length === 0 ? (
          <div className="p-4 rounded-lg bg-surface-container text-center text-xs text-outline font-mono">
            No tool invocations recorded yet.
          </div>
        ) : (
          <div className="flex flex-col gap-1.5 font-mono text-xs">
            {recentTools.map((evt, idx) => {
              const toolName = evt.tool || 'Unknown Tool';
              const timeStr = evt.timestamp
                ? new Date(evt.timestamp).toLocaleTimeString()
                : 'Recent';
              const isFinish = (evt.eventType || '').toLowerCase().includes('finish');

              return (
                <div
                  key={evt.id || idx}
                  className="p-2 rounded bg-surface-container border border-outline-variant/15 flex items-center justify-between gap-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        isFinish ? 'bg-emerald-400' : 'bg-primary'
                      }`}
                    />
                    <span className="font-semibold text-on-surface truncate text-[11px]">
                      {toolName}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-[10px] text-outline flex-shrink-0">
                    <span className="px-1.5 py-0.2 rounded bg-surface-container-high text-outline-variant">
                      {isFinish ? 'DONE' : 'IN-FLIGHT'}
                    </span>
                    <span>{timeStr}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
