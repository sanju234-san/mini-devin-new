import React from 'react';
import type { VerificationGate } from './types';

interface VerificationGatesProps {
  gates?: VerificationGate[];
}

export const VerificationGates: React.FC<VerificationGatesProps> = ({ gates = [] }) => {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-3 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 11 12 14 22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          <h3 className="font-bold text-xs sm:text-sm text-on-surface uppercase tracking-wider font-mono">
            Planned Verification Gates
          </h3>
        </div>

        <span className="text-[10px] font-mono text-outline">
          Sandbox Execution Queue ({gates.length} Gates)
        </span>
      </div>

      {/* Gates Feed */}
      {gates.length === 0 ? (
        <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 text-outline text-xs font-mono text-center">
          No verification gates declared by Planner.
        </div>
      ) : (
        <div className="flex flex-col gap-2 font-mono text-xs">
          {gates.map((gate, idx) => (
            <div
              key={`${gate.command}-${idx}`}
              className="p-2.5 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
            >
              <div className="flex items-start sm:items-center gap-2.5 min-w-0">
                <span className="w-4 h-4 rounded border border-outline-variant/50 flex items-center justify-center text-outline flex-shrink-0 mt-0.5 sm:mt-0">
                  <span className="w-1.5 h-1.5 rounded-xs bg-outline/40" />
                </span>
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 min-w-0">
                  <code className="text-primary font-semibold text-xs truncate">
                    {gate.command}
                  </code>
                  <span className="text-on-surface-variant text-[11px] truncate">
                    {gate.description}
                  </span>
                </div>
              </div>

              {/* Status Badge: Strictly PLANNED, never passing or executed */}
              <div className="self-end sm:self-auto flex-shrink-0">
                <span className="px-2 py-0.5 rounded text-[9px] uppercase font-mono tracking-wider bg-surface-container-high text-outline border border-outline-variant/30">
                  {gate.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
