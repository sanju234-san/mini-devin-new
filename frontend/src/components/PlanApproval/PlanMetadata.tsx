import React from 'react';
import type { PlanMetadata as PlanMetadataType } from './types';

interface PlanMetadataProps {
  metadata?: PlanMetadataType;
}

export const PlanMetadata: React.FC<PlanMetadataProps> = ({ metadata }) => {
  const fields = [
    {
      label: 'Planner Model:',
      value: metadata?.plannerModel || 'n/a',
      isContractGap: !metadata?.plannerModel,
    },
    {
      label: 'LangGraph Agent:',
      value: metadata?.agent || 'n/a',
      isContractGap: !metadata?.agent,
    },
    {
      label: 'Plan Version:',
      value: metadata?.version || 'n/a',
      isContractGap: !metadata?.version,
    },
    {
      label: 'Token Consumption:',
      value: metadata?.tokenConsumption || 'n/a',
      isContractGap: !metadata?.tokenConsumption,
    },
    {
      label: 'Est. Execution Time:',
      value: metadata?.estimatedExecutionTime || 'n/a',
      isContractGap: !metadata?.estimatedExecutionTime,
    },
    {
      label: 'Target Branch:',
      value: metadata?.targetBranch || 'n/a',
      isContractGap: !metadata?.targetBranch,
    },
  ];

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col gap-2.5 shadow-sm">
      <div className="flex items-center justify-between pb-1.5 border-b border-outline-variant/20">
        <h4 className="font-mono text-[11px] uppercase tracking-wider text-outline font-semibold">
          Plan Metadata & Engine Telemetry
        </h4>
        <span className="text-[10px] font-mono text-outline">Telemetry</span>
      </div>

      <div className="flex flex-col gap-1.5 text-xs font-mono">
        {fields.map((f) => (
          <div key={f.label} className="flex items-center justify-between gap-2">
            <span className="text-outline text-[11px]">{f.label}</span>
            <div className="flex items-center gap-1 min-w-0">
              <span className="text-on-surface font-medium truncate text-right text-[11px]">
                {f.value}
              </span>
              {f.isContractGap && (
                <span className="text-[9px] text-amber-400/80 font-mono" title="Contract Gap: field not yet in schema">
                  *
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
