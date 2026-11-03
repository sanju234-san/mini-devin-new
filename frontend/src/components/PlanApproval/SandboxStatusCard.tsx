import React from 'react';

interface SandboxStatusCardProps {
  sandboxed?: boolean;
  sandboxDetails?: string;
}

export const SandboxStatusCard: React.FC<SandboxStatusCardProps> = ({
  sandboxed,
  sandboxDetails,
}) => {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex items-start gap-2.5 shadow-sm text-xs font-mono">
      <div className="p-1.5 rounded-lg bg-surface-container-high text-primary flex-shrink-0 mt-0.5">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      </div>

      <div className="flex flex-col gap-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-on-surface text-[11px] uppercase tracking-wider">
            Execution Sandbox Status
          </span>
          {sandboxed !== undefined && (
            <span
              className={`px-1.5 py-0.2 rounded text-[9px] uppercase font-mono ${
                sandboxed
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
              }`}
            >
              {sandboxed ? 'Active' : 'Standby'}
            </span>
          )}
        </div>

        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          {sandboxDetails ||
            (sandboxed
              ? 'Containerized isolation active for scheduled test runs and execution.'
              : 'Sandbox telemetry pending backend contract confirmation (Tamanna).')}
        </p>
      </div>
    </div>
  );
};
