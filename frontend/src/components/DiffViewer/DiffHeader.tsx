'use client';

import React, { useState } from 'react';
import type { DiffMetadata } from './types';
import { SourceIcon, BranchIcon } from '../icons/Icons';
import { CopyIcon, CheckIcon } from './diffUtils';

interface DiffHeaderProps {
  metadata: DiffMetadata;
}

export const DiffHeader: React.FC<DiffHeaderProps> = ({ metadata }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = () => {
    if (metadata.runId) {
      navigator.clipboard.writeText(metadata.runId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col gap-space-sm">
      {/* Title + Badges Row */}
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <div className="flex items-center gap-space-sm flex-wrap">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-on-surface uppercase">
            Diff Viewer
          </h1>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Read Only
          </span>
        </div>

        <span className="px-2.5 py-0.5 rounded text-[11px] font-mono uppercase tracking-wider bg-surface-container-high text-outline border border-outline-variant/30">
          Task 6
        </span>
      </div>

      {/* Description */}
      <p className="text-xs sm:text-sm text-on-surface-variant max-w-3xl leading-relaxed">
        Inspect machine-synthesized diffs &amp; AST patches before sandbox test execution.
      </p>

      {/* Contextual Metadata Chips */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {/* Run ID Chip with Copy */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/30 text-xs font-mono text-outline">
          <span className="text-primary font-semibold"># {metadata.runId || 'run-preview'}</span>
          <button
            type="button"
            onClick={handleCopyRunId}
            className="p-0.5 rounded hover:bg-surface-container-highest text-outline hover:text-on-surface transition-colors"
            title="Copy Run ID"
            aria-label="Copy Run ID"
          >
            {copied ? (
              <CheckIcon className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <CopyIcon className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {/* Repository Chip */}
        {metadata.repository && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/30 text-xs font-mono text-outline">
            <SourceIcon className="w-3.5 h-3.5 text-primary/80" />
            <span className="text-on-surface">{metadata.repository}</span>
          </div>
        )}

        {/* Issue Chip */}
        {metadata.issueId && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/30 text-xs font-mono text-outline">
            <svg className="w-3.5 h-3.5 text-amber-400/80" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="text-on-surface truncate max-w-xs">
              #{metadata.issueId}{metadata.issueTitle ? `: ${metadata.issueTitle}` : ''}
            </span>
          </div>
        )}

        {/* Branch Chip if available */}
        {metadata.branch && (
          <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/30 text-xs font-mono text-outline">
            <BranchIcon className="w-3.5 h-3.5 text-outline/80" />
            <span className="truncate max-w-xs">{metadata.branch}</span>
          </div>
        )}
      </div>
    </div>
  );
};
