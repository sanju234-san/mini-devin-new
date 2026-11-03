import React from 'react';
import { HubIcon } from '../icons/Icons';

export const DashboardHeader: React.FC = () => {
  return (
    <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md pb-space-lg border-b border-outline-variant/20">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-space-sm flex-wrap">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
            Mini-Devin Dashboard
          </h1>
          <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-surface-container-high text-primary border border-primary/20">
            Core Orchestrator
          </span>
        </div>
        <p className="text-sm text-on-surface-variant max-w-2xl">
          Autonomous software engineering workflow from issue intake to verified pull request.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-space-sm">
        {/* Static Preview Badge (Replaces Engine: Ready per Honesty Rules) */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/30 shadow-sm">
          <span className="relative flex h-2 w-2">
            <span className="inline-flex rounded-full h-2 w-2 bg-primary/70" />
          </span>
          <span className="font-mono text-xs text-primary uppercase tracking-wider font-semibold">
            Static Preview
          </span>
        </div>

        {/* Multi-Agent Loop Standby Badge */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container-low border border-outline-variant/20 text-on-surface-variant font-mono text-xs">
          <HubIcon className="w-3.5 h-3.5 text-tertiary" />
          <span>
            Multi-Agent Autonomous Loop <span className="text-outline">(Standby)</span>
          </span>
        </div>
      </div>
    </header>
  );
};
