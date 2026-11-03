'use client';

import React, { useState } from 'react';
import type { InspectState } from './artifactsUtils';

interface ArtifactHeaderProps {
  runId: string;
  repository?: string;
  issueTag?: string;
  targetBranch?: string;
  sandboxId?: string;
  runtimeElapsed?: string;
  totalSizeFormatted?: string;
  inspectState: InspectState;
  onSelectInspectState: (state: InspectState) => void;
}

export const ArtifactHeader: React.FC<ArtifactHeaderProps> = ({
  runId,
  repository = 'octocat/linguist',
  issueTag = '#482: UTF-8 multibyte parser bug',
  targetBranch = 'fix/parser-multibyte',
  sandboxId = 'sandbox-vm-e8a',
  runtimeElapsed = '00:01:42',
  totalSizeFormatted = '2.4 MB',
  inspectState,
  onSelectInspectState,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = () => {
    navigator.clipboard.writeText(runId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-3 p-space-md rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs font-mono">
      {/* 1. Title + Breadcrumb + Inspect State Switcher */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5 text-[11px] text-outline">
            <span>Mini-Devin</span>
            <span className="text-outline-variant">/</span>
            <span className="text-primary font-semibold">Artifacts</span>
            <span className="text-outline-variant">/</span>
            <span>Trail Viewer</span>
          </div>
          <h1 className="text-lg font-bold tracking-tight text-on-surface">
            Artifact Trail Viewer
          </h1>
          <p className="text-xs text-outline">
            Explore artifacts, run manifests, and intermediate outputs synthesized during autonomous execution.
          </p>
        </div>

        {/* Inspect State Selector matching Stitch design */}
        <div className="flex items-center gap-2 self-start lg:self-auto flex-wrap">
          <span className="text-[11px] uppercase tracking-wider text-outline font-bold">
            INSPECT STATE:
          </span>
          <div className="inline-flex rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 flex-wrap">
            <button
              type="button"
              onClick={() => onSelectInspectState('active')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                inspectState === 'active'
                  ? 'bg-primary-container text-on-primary-container font-bold shadow-xs'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Active Preview</span>
            </button>

            <button
              type="button"
              onClick={() => onSelectInspectState('loading')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                inspectState === 'loading'
                  ? 'bg-primary-container text-on-primary-container font-bold shadow-xs'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              <svg className="w-3 h-3 animate-spin text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
              <span>Loading</span>
            </button>

            <button
              type="button"
              onClick={() => onSelectInspectState('empty')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                inspectState === 'empty'
                  ? 'bg-primary-container text-on-primary-container font-bold shadow-xs'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              <svg className="w-3 h-3 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="9" x2="15" y2="15" />
                <line x1="15" y1="9" x2="9" y2="15" />
              </svg>
              <span>Empty</span>
            </button>

            <button
              type="button"
              onClick={() => onSelectInspectState('unavailable')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                inspectState === 'unavailable'
                  ? 'bg-red-500/20 text-red-300 font-bold border border-red-500/40'
                  : 'text-outline hover:text-red-400'
              }`}
            >
              <svg className="w-3 h-3 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
              </svg>
              <span>Unavailable</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Run Context Badges Strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-outline-variant/20 text-[11px]">
        {/* Left Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Run ID */}
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container border border-outline-variant/30 text-primary">
            <span>{runId.startsWith('#') ? runId : `#${runId}`}</span>
            <button
              type="button"
              onClick={handleCopyRunId}
              className="text-outline hover:text-on-surface transition-colors"
              title="Copy Run ID"
            >
              {copied ? (
                <span className="text-emerald-400">✓</span>
              ) : (
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
            </button>
          </div>

          {/* Repo */}
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container border border-outline-variant/20 text-on-surface">
            <svg className="w-3 h-3 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <span>{repository}</span>
          </div>

          {/* Issue Tag */}
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container border border-outline-variant/20 text-amber-300">
            <span>{issueTag}</span>
          </div>

          {/* Branch */}
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container border border-outline-variant/20 text-emerald-400">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="6" y1="3" x2="6" y2="15" />
              <circle cx="18" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <path d="M18 9a9 9 0 0 1-9 9" />
            </svg>
            <span>{targetBranch}</span>
          </div>

          {/* Sandbox VM */}
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container border border-outline-variant/20 text-primary">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            <span>{sandboxId}</span>
          </div>
        </div>

        {/* Right Metrics */}
        <div className="flex items-center gap-3 text-outline">
          <div className="flex items-center gap-1">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>Runtime: {runtimeElapsed}</span>
          </div>
          <span className="text-outline-variant">/</span>
          <div className="flex items-center gap-1">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            </svg>
            <span>Artifact Size: {totalSizeFormatted}</span>
          </div>
          <span className="text-outline-variant">/</span>
          <div className="flex items-center gap-1 text-emerald-400 font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>SYNCHRONIZED</span>
          </div>
        </div>
      </div>
    </div>
  );
};
