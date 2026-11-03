'use client';

import React from 'react';
import type { DiffRenderMode, DiffViewerState } from './types';

interface DiffControlsProps {
  renderMode: DiffRenderMode;
  onChangeRenderMode: (mode: DiffRenderMode) => void;
  onPrevChange: () => void;
  onNextChange: () => void;
  previewState: DiffViewerState;
  onChangePreviewState: (state: DiffViewerState) => void;
}

export const DiffControls: React.FC<DiffControlsProps> = ({
  renderMode,
  onChangeRenderMode,
  onPrevChange,
  onNextChange,
  previewState,
  onChangePreviewState,
}) => {
  return (
    <div className="flex flex-col gap-2.5 pt-1">
      {/* Top Controls Row: View Mode + Diff Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        {/* Inline vs Side-by-Side Mode Toggle */}
        <div className="inline-flex items-center rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 text-xs">
          <button
            type="button"
            onClick={() => onChangeRenderMode('inline')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
              renderMode === 'inline'
                ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            title="Inline diff view"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="6" rx="1" />
              <rect x="3" y="14" width="18" height="6" rx="1" />
            </svg>
            <span>Inline</span>
          </button>

          <button
            type="button"
            onClick={() => onChangeRenderMode('side-by-side')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors ${
              renderMode === 'side-by-side'
                ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            title="Side-by-side split diff view"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="8" height="16" rx="1" />
              <rect x="13" y="4" width="8" height="16" rx="1" />
            </svg>
            <span>Side-by-Side</span>
          </button>
        </div>

        {/* Previous / Next Change Buttons */}
        <div className="inline-flex items-center gap-1 rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 text-xs font-mono">
          <button
            type="button"
            onClick={onPrevChange}
            className="p-1.5 rounded-md hover:bg-surface-container-highest text-outline hover:text-on-surface transition-colors"
            title="Jump to previous change"
            aria-label="Previous change"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          </button>
          <div className="w-[1px] h-3.5 bg-outline-variant/30" />
          <button
            type="button"
            onClick={onNextChange}
            className="p-1.5 rounded-md hover:bg-surface-container-highest text-outline hover:text-on-surface transition-colors"
            title="Jump to next change"
            aria-label="Next change"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>
      </div>

      {/* Developer Preview State Strip Matching Stitch Screenshot (Dev only, zero production mock fallback) */}
      {process.env.NODE_ENV !== 'production' && (
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="font-mono text-[10px] uppercase tracking-wider text-outline">
            PREVIEW STATE:
          </span>
          <div className="inline-flex rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 text-xs">
            <button
              type="button"
              onClick={() => onChangePreviewState('preview-active')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                previewState === 'preview-active'
                  ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Active Diff
            </button>
            <button
              type="button"
              onClick={() => onChangePreviewState('preview-loading')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                previewState === 'preview-loading'
                  ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Loading Skeleton
            </button>
            <button
              type="button"
              onClick={() => onChangePreviewState('preview-empty')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                previewState === 'preview-empty'
                  ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Empty State
            </button>
            <button
              type="button"
              onClick={() => onChangePreviewState('real')}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                previewState === 'real'
                  ? 'bg-teal-500 text-surface-container-lowest font-bold shadow-xs'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
              title="Switch to live API ingestion (GET /api/v1/runs/:id/artifacts)"
            >
              Live API
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
