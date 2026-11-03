'use client';

import React from 'react';
import type { TestSuiteSummary, PreviewState } from './testsAndPreviewUtils';

interface TestSummaryBannerProps {
  summary: TestSuiteSummary;
  activePreviewState: PreviewState;
  onSelectPreviewState: (state: PreviewState) => void;
  isLiveStream: boolean;
  onToggleLiveStream: () => void;
}

export const TestSummaryBanner: React.FC<TestSummaryBannerProps> = ({
  summary,
  activePreviewState,
  onSelectPreviewState,
  isLiveStream,
  onToggleLiveStream,
}) => {
  const isRunning = summary.status === 'RUNNING';
  const isPassed = summary.status === 'PASSED';
  const isFailed = summary.status === 'FAILED';

  return (
    <div className="flex flex-col gap-2">
      {/* 1. Main Suite Status Metric Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs font-mono">
        {/* Left: Overall Suite Status */}
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isRunning
                ? 'bg-blue-400 animate-pulse'
                : isPassed
                ? 'bg-emerald-400'
                : isFailed
                ? 'bg-red-400'
                : 'bg-outline'
            }`}
          />
          <span className="font-bold text-on-surface tracking-wide">
            SUITE STATUS: {summary.status}
          </span>
          <span className="text-outline">
            ({summary.executedTests}/{summary.totalTests} tests executed)
          </span>
        </div>

        {/* Center / Right: Metric Counters */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Passed Count */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 font-semibold">
            <svg
              className="w-3.5 h-3.5 text-emerald-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>{summary.passedCount} PASSED</span>
          </div>

          {/* Failed Count */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-semibold ${
              summary.failedCount > 0
                ? 'bg-red-500/15 border border-red-500/30 text-red-400'
                : 'bg-surface-container border border-outline-variant/20 text-outline'
            }`}
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            <span>{summary.failedCount} FAILED</span>
          </div>

          {/* Skipped Count */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-container border border-outline-variant/20 text-outline font-semibold">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="5 4 15 12 5 20 5 4" />
              <line x1="19" y1="5" x2="19" y2="19" />
            </svg>
            <span>{summary.skippedCount} SKIPPED</span>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-1.5 text-outline">
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
            <span>{summary.durationSec}s</span>
          </div>
        </div>
      </div>

      {/* 2. Preview States Selector (Matches Stitch screenshot for comprehensive UI testing) */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs font-mono">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] uppercase tracking-wider text-outline font-bold">
            PREVIEW STATES:
          </span>
          <div className="inline-flex rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 flex-wrap">
            {(['running', 'passed', 'failed', 'skeleton', 'offline'] as PreviewState[]).map(
              (st) => {
                const isActive = activePreviewState === st;
                return (
                  <button
                    key={st}
                    type="button"
                    onClick={() => onSelectPreviewState(st)}
                    className={`px-2.5 py-0.5 rounded text-[11px] capitalize transition-colors ${
                      isActive
                        ? 'bg-primary-container text-on-primary-container font-bold shadow-xs'
                        : 'text-outline hover:text-on-surface'
                    }`}
                  >
                    {st}
                  </button>
                );
              }
            )}
          </div>
        </div>

        {/* Live Hook vs Preview Mode Switch */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleLiveStream}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono border transition-colors ${
              isLiveStream
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-semibold'
                : 'bg-surface-container text-outline hover:text-on-surface border-outline-variant/30'
            }`}
            title="Toggle between Live WebSocket Client stream and Static Preview states"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isLiveStream ? 'bg-emerald-400 animate-pulse' : 'bg-outline'
              }`}
            />
            <span>{isLiveStream ? 'Live WebSocket Hook: ON' : 'Preview State Fixtures'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
