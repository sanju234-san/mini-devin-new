import React from 'react';
import type { AgentEventEnvelope } from '../../hooks/types';

interface ActiveAgentPanelProps {
  latestEvent: AgentEventEnvelope | null;
}

export const ActiveAgentPanel: React.FC<ActiveAgentPanelProps> = ({
  latestEvent,
}) => {
  const agentName = latestEvent?.agent || 'None (Idle)';
  const currentStep = latestEvent?.step ? String(latestEvent.step) : 'n/a';
  const description =
    (latestEvent?.payload as { message?: string })?.message ||
    (latestEvent?.payload as { details?: string })?.details ||
    (latestEvent ? `Executing ${latestEvent.eventType || 'event'}` : 'Awaiting agent activity');
  const activeModel = latestEvent?.model || 'n/a';
  const activeTool = latestEvent?.tool || 'None';

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-sm">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="font-mono text-[11px] uppercase tracking-wider font-semibold text-on-surface">
              Active Agent
            </span>
          </div>
          <span className="font-mono text-[10px] text-outline">
            {latestEvent ? 'Live Frame' : 'Standby'}
          </span>
        </div>

        {/* Agent Identity Box */}
        <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center text-primary font-bold font-mono text-sm">
            {agentName.charAt(0).toUpperCase()}
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-sm text-on-surface truncate">
                {agentName}
              </span>
              <span className="px-1 py-0.2 rounded font-mono text-[9px] uppercase bg-surface-container-high text-outline">
                Agent
              </span>
            </div>
            <span className="font-mono text-[10px] text-outline truncate">
              Step: <span className="text-on-surface-variant font-medium">{currentStep}</span>
            </span>
          </div>
        </div>

        {/* Current Description */}
        <div className="p-2.5 rounded bg-surface-container-lowest border border-outline-variant/20 text-xs text-on-surface-variant leading-relaxed">
          {description}
        </div>

        {/* 2x2 Telemetry Grid (Real or n/a) */}
        <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
          {/* Active Model */}
          <div className="p-2 rounded bg-surface-container border border-outline-variant/15 flex flex-col">
            <span className="text-[10px] text-outline uppercase tracking-wider">
              Active Model
            </span>
            <span className="font-semibold text-primary truncate mt-0.5">
              {activeModel}
            </span>
          </div>

          {/* Active Tool */}
          <div className="p-2 rounded bg-surface-container border border-outline-variant/15 flex flex-col">
            <span className="text-[10px] text-outline uppercase tracking-wider">
              Active Tool
            </span>
            <span className="font-semibold text-tertiary truncate mt-0.5">
              {activeTool}
            </span>
          </div>

          {/* Prompt Tokens (Contract gap: n/a) */}
          <div className="p-2 rounded bg-surface-container border border-outline-variant/15 flex flex-col">
            <span className="text-[10px] text-outline uppercase tracking-wider">
              Prompt Tokens
            </span>
            <span className="text-outline-variant mt-0.5">n/a</span>
          </div>

          {/* Completion Tokens (Contract gap: n/a) */}
          <div className="p-2 rounded bg-surface-container border border-outline-variant/15 flex flex-col">
            <span className="text-[10px] text-outline uppercase tracking-wider">
              Completion
            </span>
            <span className="text-outline-variant mt-0.5">n/a</span>
          </div>
        </div>
      </div>
    </div>
  );
};
