'use client';

import React from 'react';
import type { FileDiffItem } from './types';

interface FileSelectorProps {
  files: FileDiffItem[];
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}

export const FileSelector: React.FC<FileSelectorProps> = ({
  files,
  selectedIndex,
  onSelectIndex,
}) => {
  return (
    <div
      className="flex items-center gap-2 overflow-x-auto pb-1 pt-0.5 no-scrollbar"
      role="tablist"
      aria-label="Changed files"
    >
      {files.map((file, idx) => {
        const isSelected = idx === selectedIndex;

        let statusBadge = 'M';
        let statusColor = 'bg-amber-500/20 text-amber-300 border-amber-500/40';

        if (file.changeType === 'add') {
          statusBadge = 'A';
          statusColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
        } else if (file.changeType === 'delete') {
          statusBadge = 'D';
          statusColor = 'bg-red-500/20 text-red-400 border-red-500/40';
        }

        return (
          <button
            key={file.path}
            type="button"
            role="tab"
            aria-selected={isSelected}
            onClick={() => onSelectIndex(idx)}
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
              isSelected
                ? 'bg-surface-container-high border-primary/50 text-on-surface shadow-xs'
                : 'bg-surface-container-low/70 border-outline-variant/30 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/60'
            }`}
          >
            {/* Status Indicator (M / A / D) */}
            <span
              className={`w-4 h-4 rounded text-[10px] font-bold flex items-center justify-center border ${statusColor}`}
            >
              {statusBadge}
            </span>

            {/* File Path */}
            <span className="truncate max-w-[240px] sm:max-w-xs">{file.path}</span>

            {/* Additions / Deletions mini counts */}
            <div className="flex items-center gap-1 text-[11px] ml-1">
              <span className="text-emerald-400 font-semibold">+{file.additions}</span>
              <span className="text-red-400/90 font-semibold">-{file.deletions}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
};
