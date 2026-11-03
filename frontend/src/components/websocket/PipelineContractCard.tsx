import React from 'react';

export const PipelineContractCard: React.FC = () => {
  const stages = [
    {
      label: 'SOURCE',
      title: 'FastAPI WS (Tamanna)',
      detail: 'Broadcasts raw runtime frames on /ws/runs/:run_id',
    },
    {
      label: 'HOOK BOUNDARY',
      title: 'useAgentRunSocket Task 3 (This View)',
      detail: 'FSM connection lifecycle & safe JSON parser',
    },
    {
      label: 'STATE LAYER',
      title: 'React Memory Buffer',
      detail: 'FIFO bounded queue (default cap: 500 events)',
    },
    {
      label: 'TARGET UI',
      title: 'Live Agent Console (Task 4 Consumer)',
      detail: 'Ingests stream directly for real-time inspection',
    },
  ];

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-md">
        {/* Header */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="6" height="6" rx="1" />
              <rect x="15" y="15" width="6" height="6" rx="1" />
              <path d="M6 9v3a3 3 0 0 0 3 3h6" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-on-surface">
            Architectural Pipeline &amp; Consumer Contract
          </h3>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed">
          <strong className="text-on-surface">Pure Consumer Model:</strong> This hook strictly ingests runtime broadcast frames from FastAPI (<span className="font-mono text-primary">/ws/runs/:run_id</span>). Zero changes to backend runtime (Tamanna) or LangGraph orchestrator (Sanjeevni). No HTTP polling fallback.
        </p>

        {/* 4 Pipeline Stages */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-sm pt-1">
          {stages.map((stage, idx) => (
            <div
              key={stage.label}
              className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-1 text-xs"
            >
              <div className="flex items-center justify-between text-[10px] font-mono text-outline">
                <span>{stage.label}</span>
                <span>0{idx + 1}</span>
              </div>
              <span className="font-semibold text-on-surface text-xs mt-0.5">
                {stage.title}
              </span>
              <p className="text-[11px] text-on-surface-variant leading-tight">
                {stage.detail}
              </p>
            </div>
          ))}
        </div>

        {/* Task 4 Ready Note */}
        <div className="p-space-sm rounded-lg bg-primary-container/10 border border-primary/20 flex items-center gap-2 text-xs font-mono text-primary">
          <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <span>
            Ready for Task 4 Live Agent Console — This client buffer feeds directly into Task 4 components via <code className="font-bold">useAgentRunSocket()</code> without any backend modifications.
          </span>
        </div>
      </div>
    </div>
  );
};
