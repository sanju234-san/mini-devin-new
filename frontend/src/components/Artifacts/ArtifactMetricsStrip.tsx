'use client';

import React from 'react';
import type { ArtifactMetrics } from './artifactsUtils';

interface ArtifactMetricsStripProps {
  metrics: ArtifactMetrics;
}

export const ArtifactMetricsStrip: React.FC<ArtifactMetricsStripProps> = ({ metrics }) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-space-sm">
      {/* 1. Total Artifacts */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">TOTAL ARTIFACTS</span>
          <svg className="w-3.5 h-3.5 text-primary shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.totalArtifacts}</span>
          <span className="text-[11px] text-emerald-400 font-semibold">{metrics.indexedPercentage}% indexed</span>
        </div>
      </div>

      {/* 2. Plans & Docs */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">PLANS &amp; DOCS</span>
          <svg className="w-3.5 h-3.5 text-amber-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.plansAndDocsCount}</span>
          <span className="text-[11px] text-outline">{metrics.plansAndDocsSize}</span>
        </div>
      </div>

      {/* 3. Code Changes */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">CODE CHANGES</span>
          <svg className="w-3.5 h-3.5 text-emerald-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.codeChangesCount}</span>
          <span className="text-[11px] text-emerald-400 font-semibold">{metrics.codeChangesDelta}</span>
        </div>
      </div>

      {/* 4. Test Reports */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">TEST REPORTS</span>
          <svg className="w-3.5 h-3.5 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 2v7.31L4.36 19.34A2 2 0 0 0 6.07 22h11.86a2 2 0 0 0 1.71-2.66L14 9.31V2" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.testReportsCount}</span>
          <span className="text-[11px] text-outline">{metrics.testReportsFormat}</span>
        </div>
      </div>

      {/* 5. Screenshots */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">SCREENSHOTS</span>
          <svg className="w-3.5 h-3.5 text-purple-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.screenshotsCount}</span>
          <span className="text-[11px] text-outline">{metrics.screenshotsLabel}</span>
        </div>
      </div>

      {/* 6. AST & Logs */}
      <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col gap-1 shadow-xs">
        <div className="flex items-center justify-between text-outline text-[11px] font-mono">
          <span className="truncate">AST &amp; LOGS</span>
          <svg className="w-3.5 h-3.5 text-cyan-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        </div>
        <div className="flex items-baseline gap-1.5 font-mono">
          <span className="text-xl font-bold text-on-surface">{metrics.astAndLogsCount}</span>
          <span className="text-[11px] text-outline">{metrics.astAndLogsLabel}</span>
        </div>
      </div>
    </div>
  );
};
