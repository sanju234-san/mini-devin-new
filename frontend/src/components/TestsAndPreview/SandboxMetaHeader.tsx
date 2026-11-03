'use client';

import React, { useState } from 'react';
import type { TestSuiteSummary } from './testsAndPreviewUtils';

interface SandboxMetaHeaderProps {
  runId: string;
  summary: TestSuiteSummary;
  repository?: string;
  issueNumber?: string | number;
  issueTitle?: string;
  targetBranch?: string;
}

export const SandboxMetaHeader: React.FC<SandboxMetaHeaderProps> = ({
  runId,
  summary,
  repository = 'octocat/linguist',
  issueNumber = '482',
  issueTitle = 'UTF-8 parser',
  targetBranch = 'fix/parser-multibyte',
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = () => {
    navigator.clipboard.writeText(runId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isRunning = summary.status === 'RUNNING';
  const isPassed = summary.status === 'PASSED';
  const isFailed = summary.status === 'FAILED';

  return (
    <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-space-md p-space-md rounded-xl bg-surface-container-low border border-outline-variant/30">
      {/* Left: Title & Subtitle + Run Identifier */}
      <div className="flex flex-col gap-1.5">
        <h1 className="text-lg font-bold tracking-tight text-on-surface">
          Terminal &amp; Test Output
        </h1>
        <p className="text-xs text-outline">
          Monitor execution logs and inspect test results in real-time.
        </p>

        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {/* Run ID Pill */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-container-high border border-outline-variant/40 text-xs font-mono text-primary">
            <span>{runId.startsWith('#') ? runId : `#${runId}`}</span>
            <button
              type="button"
              onClick={handleCopyRunId}
              className="text-outline hover:text-on-surface transition-colors"
              title="Copy Run ID"
            >
              {copied ? (
                <svg
                  className="w-3.5 h-3.5 text-emerald-400"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
            </button>
          </div>

          {/* Execution Status Pill */}
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-bold uppercase tracking-wider ${
              isRunning
                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                : isPassed
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                : isFailed
                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                : 'bg-surface-container-high text-outline border border-outline-variant/30'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isRunning
                  ? 'bg-blue-400 animate-pulse'
                  : isPassed
                  ? 'bg-emerald-400'
                  : isFailed
                  ? 'bg-red-400'
                  : 'bg-outline'
              }`}
            />
            <span>{summary.status}</span>
          </div>
        </div>
      </div>

      {/* Right: Repository Context & Sandbox Metrics Strip */}
      <div className="flex flex-col items-start lg:items-end gap-2 text-xs font-mono">
        {/* Repo / Issue / Branch badges matching Stitch */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1 text-on-surface bg-surface-container px-2 py-0.5 rounded border border-outline-variant/20">
            <svg
              className="w-3.5 h-3.5 text-outline"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <span>{repository}</span>
          </div>

          <div className="flex items-center gap-1 text-on-surface bg-surface-container px-2 py-0.5 rounded border border-outline-variant/20">
            <span className="text-amber-400">#{issueNumber}</span>
            <span className="text-outline">({issueTitle})</span>
          </div>

          <div className="flex items-center gap-1 text-emerald-400 bg-surface-container px-2 py-0.5 rounded border border-outline-variant/20">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="6" y1="3" x2="6" y2="15" />
              <circle cx="18" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <path d="M18 9a9 9 0 0 1-9 9" />
            </svg>
            <span>{targetBranch}</span>
          </div>
        </div>

        {/* Runtime Metrics: Timer / Memory / Sandbox ID */}
        <div className="flex items-center gap-2 text-[11px] text-outline flex-wrap">
          <div className="flex items-center gap-1">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>00:01:42</span>
          </div>
          <span className="text-outline-variant">/</span>

          <div className="flex items-center gap-1">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
              <line x1="6" y1="6" x2="6.01" y2="6" />
              <line x1="6" y1="18" x2="6.01" y2="18" />
            </svg>
            <span>{summary.memoryUsageMb} MB</span>
          </div>
          <span className="text-outline-variant">/</span>

          <div className="flex items-center gap-1 text-primary">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            <span>{summary.sandboxVmId}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
