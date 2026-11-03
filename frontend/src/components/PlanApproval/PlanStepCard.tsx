import React from 'react';
import type { PlanStep } from './types';

interface PlanStepCardProps {
  step: PlanStep;
  totalSteps: number;
}

export const PlanStepCard: React.FC<PlanStepCardProps> = ({ step, totalSteps }) => {
  const stepIndexFormatted = step.stepNumber < 10 ? `0${step.stepNumber}` : `${step.stepNumber}`;

  return (
    <div className="rounded-xl bg-surface-container border border-outline-variant/30 p-space-md flex flex-col gap-3 shadow-xs hover:border-primary/30 transition-colors">
      {/* Step Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-md bg-primary-container/20 border border-primary/30 text-primary font-mono text-xs font-semibold flex items-center justify-center flex-shrink-0">
            {stepIndexFormatted}
          </span>
          <h4 className="font-semibold text-xs sm:text-sm text-on-surface leading-tight">
            {step.title}
          </h4>
        </div>

        <span className="text-[10px] font-mono uppercase tracking-wider text-outline px-1.5 py-0.5 rounded bg-surface-container-high border border-outline-variant/30 flex-shrink-0">
          Step {step.stepNumber}/{totalSteps}
        </span>
      </div>

      {/* Target & Action Metadata Bar */}
      <div className="flex items-center justify-between flex-wrap gap-2 text-xs font-mono bg-surface-container-low px-2.5 py-1.5 rounded-lg border border-outline-variant/20">
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span className="text-primary font-medium flex items-center gap-1">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {step.targetFile || 'Target file: n/a'}
          </span>
          {step.lineRange && (
            <span className="text-outline">
              ({step.lineRange})
            </span>
          )}
        </div>

        {step.action && (
          <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant border border-outline-variant/40">
            Action: {step.action}
          </span>
        )}
      </div>

      {/* Directives & Impact Two-column/Stack Block */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-surface-container-lowest/80 p-2.5 rounded-lg border border-outline-variant/20 flex flex-col gap-1">
          <span className="text-[9px] uppercase tracking-wider text-outline font-semibold">
            Synthesized Directive
          </span>
          <p className="text-[11px] text-on-surface-variant leading-relaxed">
            {step.directive || 'n/a'}
          </p>
        </div>

        <div className="bg-surface-container-lowest/80 p-2.5 rounded-lg border border-outline-variant/20 flex flex-col gap-1">
          <span className="text-[9px] uppercase tracking-wider text-outline font-semibold">
            Technical Impact
          </span>
          <p className="text-[11px] text-on-surface-variant leading-relaxed">
            {step.technicalImpact || 'n/a'}
          </p>
        </div>
      </div>
    </div>
  );
};
