import React from 'react';
import type { ImplementationPlanData } from './types';
import { PlanStepCard } from './PlanStepCard';

interface ImplementationPlanProps {
  plan?: ImplementationPlanData;
}

export const ImplementationPlan: React.FC<ImplementationPlanProps> = ({ plan }) => {
  if (!plan) {
    return (
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md text-outline text-xs font-mono">
        No implementation plan data available.
      </div>
    );
  }

  const steps = plan.steps || [];
  const affectedFilesCount = plan.affectedFiles ? plan.affectedFiles.length : 0;
  const versionLabel = plan.version || 'v0.1';
  const isDraft = plan.isDraft ?? true;

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-4 shadow-sm">
      {/* Plan Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-outline-variant/20">
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <h3 className="font-bold text-sm sm:text-base text-on-surface uppercase tracking-wider font-mono">
              Implementation Plan
            </h3>
          </div>

          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-surface-container-high text-primary border border-primary/20">
            {versionLabel} {isDraft ? 'draft' : ''}
          </span>
        </div>

        {/* Metrics Badges */}
        <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
          <span className="px-2 py-0.5 rounded text-[10px] bg-surface-container-high text-on-surface-variant border border-outline-variant/30">
            {steps.length} Execution Steps
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] bg-surface-container-high text-on-surface-variant border border-outline-variant/30">
            {affectedFilesCount} Files Affected
          </span>
          {plan.sandboxed !== undefined && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] border ${
                plan.sandboxed
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-surface-container-high text-outline border-outline-variant/30'
              }`}
            >
              {plan.sandboxed ? '✓ Sandboxed' : 'Unsandboxed'}
            </span>
          )}
        </div>
      </div>

      {/* Planner Rationale & Upstream Strategy */}
      <div className="bg-surface-container-high/40 p-space-md rounded-xl border border-outline-variant/30 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-xs font-mono text-primary font-medium">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span className="uppercase tracking-wider text-[11px] font-semibold">
            Planner Rationale & Upstream Strategy
          </span>
        </div>
        <p className="text-xs sm:text-sm text-on-surface-variant leading-relaxed font-sans">
          {plan.rationale || 'No planner rationale provided in contract payload.'}
        </p>
      </div>

      {/* Staged Execution Steps Feed */}
      <div className="flex flex-col gap-2.5">
        <div className="text-[11px] font-mono uppercase tracking-wider text-outline px-1">
          Execution Steps Sequence ({steps.length})
        </div>

        {steps.length === 0 ? (
          <div className="p-space-lg rounded-xl bg-surface-container border border-outline-variant/20 text-center text-outline font-mono text-xs">
            Zero steps registered in plan.
          </div>
        ) : (
          steps.map((step) => (
            <PlanStepCard key={step.stepNumber} step={step} totalSteps={steps.length} />
          ))
        )}
      </div>
    </div>
  );
};
