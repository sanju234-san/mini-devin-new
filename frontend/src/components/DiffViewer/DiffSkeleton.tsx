'use client';

import React from 'react';

export const DiffSkeleton: React.FC = () => {
  return (
    <div className="flex flex-col gap-space-md animate-pulse">
      {/* File selector skeleton */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex-shrink-0 h-9 w-52 rounded-lg bg-surface-container-high border border-outline-variant/20"
          />
        ))}
      </div>

      {/* Editor card skeleton */}
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-md flex flex-col">
        {/* Header bar skeleton */}
        <div className="px-space-md py-3 bg-surface-container-high/60 border-b border-outline-variant/20 flex items-center justify-between">
          <div className="h-4 w-48 bg-surface-container-highest rounded" />
          <div className="h-4 w-20 bg-surface-container-highest rounded" />
        </div>

        {/* Code lines skeleton */}
        <div className="p-space-lg flex flex-col gap-3 min-h-[480px] bg-[#0b1118]">
          <div className="h-3 w-32 bg-surface-container-highest/60 rounded" />
          <div className="h-3 w-44 bg-surface-container-highest/50 rounded ml-4" />
          <div className="h-3 w-64 bg-surface-container-highest/50 rounded ml-8" />
          <div className="h-3.5 w-80 bg-red-500/20 rounded ml-12" />
          <div className="h-3.5 w-72 bg-red-500/20 rounded ml-12" />
          <div className="h-3.5 w-96 bg-emerald-500/20 rounded ml-12" />
          <div className="h-3.5 w-84 bg-emerald-500/20 rounded ml-12" />
          <div className="h-3 w-20 bg-surface-container-highest/50 rounded ml-8" />
          <div className="h-3 w-16 bg-surface-container-highest/60 rounded ml-4" />
          <div className="h-3 w-12 bg-surface-container-highest/70 rounded" />
        </div>
      </div>
    </div>
  );
};
