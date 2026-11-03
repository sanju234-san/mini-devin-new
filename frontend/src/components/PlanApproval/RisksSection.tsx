import React from 'react';
import type { PlanRisk } from './types';

interface RisksSectionProps {
  risks?: PlanRisk[];
}

export const RisksSection: React.FC<RisksSectionProps> = ({ risks = [] }) => {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-3 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <h3 className="font-bold text-xs sm:text-sm text-on-surface uppercase tracking-wider font-mono">
            Risks & System Considerations
          </h3>
        </div>

        <span className="text-[10px] font-mono text-outline">
          Evaluated by Planner
        </span>
      </div>

      {/* Risk Cards Grid */}
      {risks.length === 0 ? (
        <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 text-outline text-xs font-mono text-center">
          No risk assessments attached by Planner.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {risks.map((risk, idx) => {
            let severityBadge = (
              <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono font-semibold bg-surface-container-high text-outline border border-outline-variant/30">
                {risk.severity}
              </span>
            );

            if (risk.severity === 'LOW RISK') {
              severityBadge = (
                <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/30">
                  LOW RISK
                </span>
              );
            } else if (risk.severity === 'MEDIUM ATTENTION') {
              severityBadge = (
                <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                  MEDIUM ATTENTION
                </span>
              );
            } else if (risk.severity === 'HIGH RISK') {
              severityBadge = (
                <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono font-semibold bg-red-500/10 text-red-300 border border-red-500/30">
                  HIGH RISK
                </span>
              );
            } else if (risk.severity === 'MITIGATED') {
              severityBadge = (
                <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                  MITIGATED
                </span>
              );
            }

            return (
              <div
                key={`${risk.category}-${idx}`}
                className="bg-surface-container p-3 rounded-lg border border-outline-variant/20 flex flex-col justify-between gap-2 shadow-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-xs text-on-surface truncate">
                    {risk.category}
                  </span>
                  {severityBadge}
                </div>

                <p className="text-[11px] text-on-surface-variant font-mono leading-relaxed mt-1">
                  {risk.description}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
