import React from 'react';

export const LoadingSkeletonState: React.FC = () => {
  return (
    <div
      className="rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-sm"
      aria-busy="true"
      aria-label="Loading REST API state"
    >
      {/* State Header Bar */}
      <div className="px-space-md py-2.5 bg-surface-container/60 border-b border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-teal-500/10 text-teal-400 border border-teal-500/30 font-semibold">
            STATE 01
          </span>
          <span className="font-semibold text-on-surface">
            Pending Request / Active Polling Suspense
          </span>
          <span className="font-mono text-[11px] text-outline hidden sm:inline">
            GET /api/v1/runs?status=all
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-outline">
          <span className="inline-flex items-center gap-1.5 text-tertiary">
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse" />
            SUSPENSE ACTIVE
          </span>
          <span className="text-outline-variant hidden md:inline">|</span>
          <span className="hidden md:inline text-outline">Preserving Layout Geometry</span>
        </div>
      </div>

      {/* Skeleton Content Grid */}
      <div className="p-space-lg flex flex-col gap-space-lg animate-pulse">
        {/* Row 1: Four Metric/Filter Skeleton Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-space-md">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-2"
            >
              <div className="h-3 w-16 bg-surface-container-highest rounded" />
              <div className="h-5 w-24 bg-surface-container-highest/80 rounded" />
            </div>
          ))}
        </div>

        {/* Row 2: Pipeline Progress Track Skeleton */}
        <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="h-3 w-28 bg-surface-container-highest rounded" />
            <div className="h-3 w-16 bg-surface-container-highest rounded" />
          </div>
          <div className="h-2 w-full bg-surface-container-highest/60 rounded-full overflow-hidden">
            <div className="h-full w-2/5 bg-primary/30 rounded-full" />
          </div>
          <div className="flex justify-between">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-2 w-12 bg-surface-container-highest/50 rounded" />
            ))}
          </div>
        </div>

        {/* Row 3: Split Work Area Skeletons */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-md">
          {/* Left: Task Tree Skeleton */}
          <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-2.5">
            <div className="h-3.5 w-32 bg-surface-container-highest rounded mb-1" />
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded bg-surface-container-highest/70 flex-shrink-0" />
                <div className="h-3 w-full bg-surface-container-highest/50 rounded" />
              </div>
            ))}
          </div>

          {/* Right: Terminal Telemetry Skeleton */}
          <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-2">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="w-2.5 h-2.5 rounded-full bg-surface-container-highest" />
              <span className="w-2.5 h-2.5 rounded-full bg-surface-container-highest" />
              <span className="w-2.5 h-2.5 rounded-full bg-surface-container-highest" />
              <div className="h-3 w-36 bg-surface-container-highest/80 rounded ml-2" />
            </div>
            <div className="h-2.5 w-5/6 bg-surface-container-highest/50 rounded" />
            <div className="h-2.5 w-3/4 bg-surface-container-highest/40 rounded" />
            <div className="h-2.5 w-4/5 bg-surface-container-highest/45 rounded" />
            <div className="h-2.5 w-2/3 bg-surface-container-highest/35 rounded" />
          </div>
        </div>
      </div>

      {/* Layout Invariance Footer Note */}
      <div className="px-space-md py-2 bg-surface-container/40 border-t border-outline-variant/20 flex items-center gap-2 text-outline font-mono text-[11px]">
        <svg className="w-3.5 h-3.5 text-primary flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>
          Layout Invariance: Skeletons map 1:1 with execution card dimensions, avoiding Cumulative Layout Shift (CLS = 0.00) during REST hydration cycles.
        </span>
      </div>
    </div>
  );
};
