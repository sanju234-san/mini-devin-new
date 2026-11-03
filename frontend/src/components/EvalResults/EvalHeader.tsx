import React, { useState } from 'react';
import type { EvalInspectMode, EvaluationSummary } from './evalResultsUtils';

interface EvalHeaderProps {
  summary: EvaluationSummary;
  inspectMode: EvalInspectMode;
  onSelectInspectMode: (mode: EvalInspectMode) => void;
}

export const EvalHeader: React.FC<EvalHeaderProps> = ({
  summary,
  inspectMode,
  onSelectInspectMode,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = () => {
    navigator.clipboard?.writeText(summary.runId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-3 pb-3 border-b border-outline-variant/30">
      {/* Top Main Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="w-5 h-5 text-primary flex items-center justify-center">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 3v18h18" />
                <path d="M18 9l-5 5-4-4-3 3" />
              </svg>
            </div>
            <h1 className="text-lg font-bold tracking-tight text-on-surface">
              Evaluation Results
            </h1>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider border ${
                inspectMode === 'passed'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : inspectMode === 'running'
                  ? 'bg-primary/10 text-primary border-primary/30 animate-pulse'
                  : 'bg-red-500/10 text-red-400 border-red-500/30'
              }`}
            >
              • {inspectMode === 'passed' ? 'ALL TESTS PASSED' : summary.status}
            </span>
            <span className="font-mono text-xs text-outline px-1.5 py-0.5 rounded bg-surface-container-high border border-outline-variant/30">
              {summary.duration}
            </span>
          </div>
          <p className="text-xs text-outline font-normal">
            Review agent performance, test outcomes, and run quality benchmarks across autonomous iterations.
          </p>
        </div>

        {/* Top Right Inspect Mode Switcher */}
        <div className="flex items-center bg-surface-container-lowest border border-outline-variant/40 rounded p-0.5 text-xs font-mono">
          <button
            type="button"
            onClick={() => onSelectInspectMode('passed')}
            className={`px-2.5 py-1 rounded transition-colors ${
              inspectMode === 'passed'
                ? 'bg-surface-container-high text-emerald-400 font-semibold'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            Passed
          </button>
          <button
            type="button"
            onClick={() => onSelectInspectMode('failed')}
            className={`px-2.5 py-1 rounded transition-colors ${
              inspectMode === 'failed'
                ? 'bg-surface-container-high text-red-400 font-semibold'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            Failed (Selected)
          </button>
          <button
            type="button"
            onClick={() => onSelectInspectMode('running')}
            className={`px-2.5 py-1 rounded transition-colors ${
              inspectMode === 'running'
                ? 'bg-surface-container-high text-primary font-semibold'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            Running
          </button>
          <button
            type="button"
            onClick={() => onSelectInspectMode('empty')}
            className={`px-2.5 py-1 rounded transition-colors ${
              inspectMode === 'empty'
                ? 'bg-surface-container-high text-on-surface font-semibold'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            Empty
          </button>
          <button
            type="button"
            onClick={() => onSelectInspectMode('unavailable')}
            className={`px-2.5 py-1 rounded transition-colors ${
              inspectMode === 'unavailable'
                ? 'bg-surface-container-high text-amber-400 font-semibold'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            Unavailable
          </button>
        </div>
      </div>

      {/* Subheader Metadata Row */}
      <div className="flex items-center justify-between gap-3 flex-wrap text-[11px] font-mono text-outline pt-1">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Run ID Pill */}
          <button
            type="button"
            onClick={handleCopyRunId}
            title="Click to copy Run ID"
            className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high/60 border border-outline-variant/40 text-on-surface hover:border-primary/50 transition-colors"
          >
            <span>Run ID:</span>
            <span className="text-primary font-semibold">#{summary.runId}</span>
            <span className="text-[10px] text-outline">{copied ? '✓' : '❐'}</span>
          </button>

          {/* Repo */}
          <div className="flex items-center gap-1">
            <span className="text-outline">Repo:</span>
            <span className="text-on-surface">{summary.repo}</span>
          </div>

          {/* Git Branch */}
          <div className="flex items-center gap-1">
            <span className="text-outline">git:</span>
            <span className="text-tertiary">{summary.branch}</span>
          </div>

          {/* Issue */}
          <div className="flex items-center gap-1">
            <span className="text-outline">Issue:</span>
            <span className="text-on-surface">{summary.issue}</span>
          </div>
        </div>

        {/* Benchmark Suite & Determinism */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-lowest border border-outline-variant/30">
            <span className="text-outline">Suite:</span>
            <span className="text-on-surface font-semibold">{summary.suite}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="font-semibold">Determinism: {summary.determinism}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
