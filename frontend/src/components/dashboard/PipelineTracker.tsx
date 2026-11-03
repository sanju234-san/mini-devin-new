import React from 'react';

export const PipelineTracker: React.FC = () => {
  const steps = [
    '1. Issue Intake',
    '2. Synthesis & Plan',
    '3. Coding Agent',
    '4. Sandboxed Eval',
    '5. Verified PR',
  ];

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-outline font-mono text-[11px] mb-2">
      <span className="text-on-surface-variant font-medium mr-0.5">Pipeline:</span>
      {steps.map((step, idx) => (
        <React.Fragment key={step}>
          <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant/20 text-outline">
            {step}
          </span>
          {idx < steps.length - 1 && (
            <span className="text-outline-variant select-none">→</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};
