import React from 'react';
import type { AgentStage, ProviderType } from './transparencyUtils';

interface AgentWorkflowPipelineProps {
  stages: AgentStage[];
  activeStageId?: string;
  onSelectStage?: (stageId: string) => void;
}

export const AgentWorkflowPipeline: React.FC<AgentWorkflowPipelineProps> = ({
  stages,
  activeStageId,
  onSelectStage,
}) => {
  const getStatusBadge = (status: AgentStage['status']) => {
    switch (status) {
      case 'done':
      case 'verified':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            {status === 'verified' ? 'VERIFIED' : 'DONE'}
          </span>
        );
      case 'running':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-primary/20 text-primary border border-primary/40 animate-pulse">
            RUNNING
          </span>
        );
      case 'failed':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-red-500/15 text-red-400 border border-red-500/30">
            FAILED
          </span>
        );
      case 'queued':
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-surface-container text-outline border border-outline-variant/30">
            QUEUED
          </span>
        );
      case 'pending':
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase bg-surface-container text-outline-variant border border-outline-variant/20">
            PENDING
          </span>
        );
    }
  };

  const getProviderBadge = (providerType: ProviderType, modelName: string) => {
    if (providerType === 'classifier') {
      return (
        <span
          title="Classifier / Embedding Model"
          className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 flex items-center gap-1"
        >
          <span className="w-1 h-1 rounded-full bg-cyan-400" />
          <span>{modelName}</span>
        </span>
      );
    }

    if (providerType === 'hitl') {
      return (
        <span
          title="Human-in-the-Loop Gate"
          className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 flex items-center gap-1"
        >
          <span>👤 {modelName}</span>
        </span>
      );
    }

    if (providerType === 'sandbox') {
      return (
        <span
          title="Sandbox Execution Environment"
          className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1"
        >
          <span>⚡ {modelName}</span>
        </span>
      );
    }

    if (providerType === 'bot') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-surface-container-high text-outline border border-outline-variant/20">
          {modelName}
        </span>
      );
    }

    // Default: LLM step
    return (
      <span
        title="Generative LLM Model"
        className="px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-purple-500/10 text-purple-300 border border-purple-500/30 flex items-center gap-1"
      >
        <span className="w-1 h-1 rounded-full bg-purple-400" />
        <span>{modelName}</span>
      </span>
    );
  };

  return (
    <div className="w-full overflow-x-auto pb-1">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 min-w-[760px]">
        {stages.map((stage) => {
          const isSelected = activeStageId === stage.id;
          const isCurrentRunning = stage.status === 'running';

          return (
            <button
              key={stage.id}
              type="button"
              onClick={() => onSelectStage?.(stage.id)}
              className={`flex flex-col justify-between p-2 rounded-lg border text-left transition-all ${
                isSelected
                  ? 'bg-surface-container-high border-primary ring-1 ring-primary/40'
                  : isCurrentRunning
                  ? 'bg-surface-container-high/60 border-primary/40'
                  : 'bg-surface-container-lowest/80 border-outline-variant/30 hover:bg-surface-container hover:border-outline-variant/50'
              }`}
            >
              {/* Header: Stage number, name, duration */}
              <div className="flex items-center justify-between text-[11px] font-mono font-semibold text-on-surface mb-1">
                <span className="flex items-center gap-1">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      stage.status === 'done' || stage.status === 'verified'
                        ? 'bg-emerald-400'
                        : isCurrentRunning
                        ? 'bg-primary animate-pulse'
                        : 'bg-outline-variant'
                    }`}
                  />
                  <span>
                    {stage.stepNumber}. {stage.name}
                  </span>
                </span>
                {stage.duration && (
                  <span className="text-[10px] font-normal text-outline">
                    {stage.duration}
                  </span>
                )}
              </div>

              {/* Summary line */}
              <div className="text-[10px] text-on-surface-variant truncate mb-2" title={stage.summary}>
                {stage.summary}
              </div>

              {/* Bottom Row: Status badge & Model / Provider badge */}
              <div className="flex items-center justify-between gap-1 pt-1 border-t border-outline-variant/20 flex-wrap">
                {getStatusBadge(stage.status)}
                {getProviderBadge(stage.providerType, stage.modelBadge)}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
