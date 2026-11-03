'use client';

import React from 'react';

interface ChangeSummaryBarProps {
  filesCount: number;
  totalAdditions: number;
  totalDeletions: number;
}

export const ChangeSummaryBar: React.FC<ChangeSummaryBarProps> = ({
  filesCount,
  totalAdditions,
  totalDeletions,
}) => {
  return (
    <div className="flex items-center justify-between gap-space-sm pt-2 text-xs font-mono">
      {/* Counts: Files Changed, +Additions, -Deletions */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-semibold text-on-surface">
          {filesCount} {filesCount === 1 ? 'File Changed' : 'Files Changed'}
        </span>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          +{totalAdditions}
        </span>
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-red-500/15 text-red-400 border border-red-500/30">
          -{totalDeletions}
        </span>
      </div>

      {/* Right-aligned AST Context Badge */}
      <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high border border-outline-variant/30 text-[11px] text-outline">
        <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span className="hidden sm:inline font-sans">AST Context</span>
        <span className="text-primary font-semibold">Active</span>
      </div>
    </div>
  );
};
