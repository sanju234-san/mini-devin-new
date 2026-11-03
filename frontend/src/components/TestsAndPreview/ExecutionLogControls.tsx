'use client';

import React, { useState } from 'react';
import type { LogFilterCategory } from './testsAndPreviewUtils';

interface ExecutionLogControlsProps {
  activeCategory: LogFilterCategory;
  onSelectCategory: (cat: LogFilterCategory) => void;
  categoryCounts: {
    all: number;
    stdout: number;
    stderr: number;
    test_runner: number;
  };
  filterText: string;
  onFilterChange: (text: string) => void;
  autoScroll: boolean;
  onToggleAutoScroll: () => void;
  onClear: () => void;
  onCopy: () => void;
  isLive: boolean;
}

export const ExecutionLogControls: React.FC<ExecutionLogControlsProps> = ({
  activeCategory,
  onSelectCategory,
  categoryCounts,
  filterText,
  onFilterChange,
  autoScroll,
  onToggleAutoScroll,
  onClear,
  onCopy,
  isLive,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col bg-surface-container-low border-b border-outline-variant/30">
      {/* 1. Window Chrome Strip */}
      <div className="px-3.5 py-2.5 bg-surface-container-high/60 border-b border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 text-xs font-mono select-none">
        {/* Left: Window Dots + Icon + Title */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#ff5f56] inline-block shadow-xs" />
            <span className="w-3 h-3 rounded-full bg-[#ffbd2e] inline-block shadow-xs" />
            <span className="w-3 h-3 rounded-full bg-[#27c93f] inline-block shadow-xs" />
          </div>

          <div className="flex items-center gap-1.5 text-on-surface font-semibold text-xs ml-1">
            <svg
              className="w-3.5 h-3.5 text-primary"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
            <span>Execution Logs</span>
          </div>
        </div>

        {/* Right: Live Stream Indicator + Auto-Scroll Toggle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px] font-mono">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isLive ? 'bg-emerald-400' : 'bg-outline'
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isLive ? 'bg-emerald-400' : 'bg-outline'
                }`}
              />
            </span>
            <span className={isLive ? 'text-emerald-400 font-medium' : 'text-outline'}>
              {isLive ? 'Live stream active (120 lines/sec)' : 'Stream Standby'}
            </span>
          </div>

          <button
            type="button"
            onClick={onToggleAutoScroll}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono border transition-colors ${
              autoScroll
                ? 'bg-primary-container/20 text-primary border-primary/40 font-semibold'
                : 'bg-surface-container border-outline-variant/30 text-outline hover:text-on-surface'
            }`}
            title="Toggle terminal auto-scroll to bottom on new lines"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                autoScroll ? 'bg-primary' : 'bg-outline'
              }`}
            />
            <span>Auto-scroll: {autoScroll ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </div>

      {/* 2. Filter Category Tabs */}
      <div className="px-3.5 pt-2 pb-1.5 flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant/20">
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            type="button"
            onClick={() => onSelectCategory('all')}
            className={`px-3 py-1 rounded-md text-xs font-mono transition-colors ${
              activeCategory === 'all'
                ? 'bg-surface-container-highest text-on-surface font-semibold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container-high/50'
            }`}
          >
            All Output ({categoryCounts.all})
          </button>

          <button
            type="button"
            onClick={() => onSelectCategory('stdout')}
            className={`px-3 py-1 rounded-md text-xs font-mono transition-colors ${
              activeCategory === 'stdout'
                ? 'bg-surface-container-highest text-on-surface font-semibold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container-high/50'
            }`}
          >
            stdout ({categoryCounts.stdout})
          </button>

          <button
            type="button"
            onClick={() => onSelectCategory('stderr')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono transition-colors ${
              activeCategory === 'stderr'
                ? 'bg-surface-container-highest text-on-surface font-semibold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container-high/50'
            }`}
          >
            <span>stderr</span>
            {categoryCounts.stderr > 0 && (
              <span className="px-1.5 py-0.2 rounded text-[10px] bg-red-500/20 text-red-400 font-bold border border-red-500/30">
                {categoryCounts.stderr}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => onSelectCategory('test_runner')}
            className={`px-3 py-1 rounded-md text-xs font-mono transition-colors ${
              activeCategory === 'test_runner'
                ? 'bg-surface-container-highest text-on-surface font-semibold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container-high/50'
            }`}
          >
            Test Runner ({categoryCounts.test_runner})
          </button>
        </div>
      </div>

      {/* 3. Search and Action Control Strip */}
      <div className="px-3.5 py-2 flex flex-wrap items-center justify-between gap-2">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-outline">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <input
            type="text"
            value={filterText}
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder="Filter logs (e.g. error, assertion, pass)..."
            className="w-full pl-8 pr-3 py-1 bg-surface-container-highest/60 border border-outline-variant/30 rounded text-xs font-mono text-on-surface placeholder:text-outline/60 focus:outline-hidden focus:border-primary transition-colors"
          />
          {filterText && (
            <button
              type="button"
              onClick={() => onFilterChange('')}
              className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-outline hover:text-on-surface"
            >
              &times;
            </button>
          )}
        </div>

        {/* Action Buttons: Copy Buffer + Clear Buffer */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-xs font-mono transition-colors"
            title="Copy displayed terminal log buffer to clipboard"
          >
            {copied ? (
              <>
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
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
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
                <span>Copy</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onClear}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-red-400 text-xs font-mono transition-colors"
            title="Clear displayed log buffer locally (does not alter backend logs)"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            <span>Clear</span>
          </button>
        </div>
      </div>
    </div>
  );
};
