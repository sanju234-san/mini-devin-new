import React from 'react';
import type { PipelineStageInfo } from './liveConsoleUtils';

interface WorkflowTimelineProps {
  stages: PipelineStageInfo[];
}

export const WorkflowTimeline: React.FC<WorkflowTimelineProps> = ({ stages }) => {
  const activeCount = stages.filter((s) => s.status === 'running').length;
  const completedCount = stages.filter((s) => s.status === 'completed').length;

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col gap-2 shadow-sm">
      {/* Timeline Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 text-xs font-mono">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-primary flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <span className="font-semibold text-on-surface uppercase tracking-wider text-[11px]">
            Autonomous Pipeline Execution
          </span>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-outline">
          <span>
            {completedCount > 0
              ? `${completedCount} Completed · `
              : ''}
            {activeCount > 0 ? `${activeCount} Running` : 'Awaiting Pipeline Events'}
          </span>
        </div>
      </div>

      {/* Stages Horizontal Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 pt-1 overflow-x-auto">
        {stages.map((stage) => {
          let statusBadgeClass = 'bg-surface-container text-outline border-outline-variant/20';
          let statusLabel = 'Standby';
          let indicatorIcon = (
            <span className="w-1.5 h-1.5 rounded-full bg-outline/40" />
          );

          if (stage.status === 'completed') {
            statusBadgeClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
            statusLabel = 'Completed';
            indicatorIcon = (
              <svg className="w-2.5 h-2.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            );
          } else if (stage.status === 'running') {
            statusBadgeClass = 'bg-primary/20 text-primary border-primary/40 ring-1 ring-primary/30';
            statusLabel = 'Active';
            indicatorIcon = (
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
            );
          } else if (stage.status === 'failed') {
            statusBadgeClass = 'bg-red-500/10 text-red-400 border-red-500/30';
            statusLabel = 'Failed';
            indicatorIcon = (
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            );
          }

          return (
            <div
              key={stage.id}
              className={`p-2 rounded-lg border flex flex-col justify-between gap-1 transition-all ${
                stage.status === 'running'
                  ? 'bg-surface-container-high border-primary/40 shadow-sm'
                  : 'bg-surface-container border-outline-variant/20'
              }`}
            >
              <div className="flex items-center justify-between text-[10px] font-mono text-outline">
                <span>0{stage.stageNumber}</span>
                {indicatorIcon}
              </div>

              <div className="font-semibold text-xs text-on-surface truncate mt-0.5">
                {stage.name}
              </div>

              <div className="mt-1">
                <span
                  className={`inline-flex items-center px-1.5 py-0.2 rounded font-mono text-[9px] uppercase tracking-wider border ${statusBadgeClass}`}
                >
                  {statusLabel}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
