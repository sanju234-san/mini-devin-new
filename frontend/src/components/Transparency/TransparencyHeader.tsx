import React from 'react';
import type { TransparencyInspectMode } from './transparencyUtils';

interface TransparencyHeaderProps {
  runId: string;
  inspectMode: TransparencyInspectMode;
  onSelectInspectMode: (mode: TransparencyInspectMode) => void;
  isStreaming: boolean;
  onToggleStreaming: () => void;
  activeStageNumber?: number;
  totalStages?: number;
  totalTokens?: number;
  cost?: string;
  modelsSummary?: string;
  repo?: string;
  issue?: string;
  branch?: string;
}

export const TransparencyHeader: React.FC<TransparencyHeaderProps> = ({
  runId,
  inspectMode,
  onSelectInspectMode,
  isStreaming,
  onToggleStreaming,
  activeStageNumber = 6,
  totalStages = 8,
  totalTokens = 148290,
  cost = '$0.042',
  modelsSummary = 'Claude 3.5 Sonnet + GPT-4o',
  repo = 'octocat/linguist',
  issue = '#482: UTF-8 multibyte parser bug',
  branch = 'fix/parser-multibyte',
}) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopyRunId = () => {
    navigator.clipboard?.writeText(runId);
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
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
                <path d="M2 12h20" />
              </svg>
            </div>
            <h1 className="text-lg font-bold tracking-tight text-on-surface">
              Model &amp; Agent Transparency
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-surface-container-high border border-outline-variant/40 text-primary">
              STAGE {activeStageNumber}/{totalStages}
            </span>
          </div>
          <p className="text-xs text-outline font-normal">
            Observe real-time multi-agent decision branches, chain-of-thought traces, prompt token telemetry, and execution safety invariants.
          </p>
        </div>

        {/* Top Right Controls & State Switcher */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Live vs Pause Button */}
          <button
            type="button"
            onClick={onToggleStreaming}
            className={`px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 transition-colors ${
              isStreaming
                ? 'bg-primary text-on-primary border-primary shadow-sm'
                : 'bg-surface-container-high text-on-surface border-outline-variant/40 hover:bg-surface-container-highest'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-white animate-pulse' : 'bg-outline'}`} />
            <span>{isStreaming ? 'Live Stream' : 'Paused'}</span>
          </button>

          {/* Inspect Mode Selector */}
          <div className="flex items-center bg-surface-container-lowest border border-outline-variant/40 rounded p-0.5 text-xs">
            <button
              type="button"
              onClick={() => onSelectInspectMode('completed')}
              className={`px-2.5 py-1 rounded transition-colors ${
                inspectMode === 'completed'
                  ? 'bg-surface-container-high text-primary font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Completed View
            </button>
            <button
              type="button"
              onClick={() => onSelectInspectMode('live')}
              className={`px-2.5 py-1 rounded transition-colors ${
                inspectMode === 'live'
                  ? 'bg-surface-container-high text-primary font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Live Socket
            </button>
            <button
              type="button"
              onClick={() => onSelectInspectMode('empty')}
              className={`px-2 py-1 rounded transition-colors ${
                inspectMode === 'empty'
                  ? 'bg-surface-container-high text-primary font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Empty
            </button>
            <button
              type="button"
              onClick={() => onSelectInspectMode('disconnected')}
              className={`px-2 py-1 rounded transition-colors ${
                inspectMode === 'disconnected'
                  ? 'bg-surface-container-high text-red-400 font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Offline
            </button>
          </div>
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
            <span>Run:</span>
            <span className="text-primary font-semibold">#{runId}</span>
            <span className="text-[10px] text-outline">{copied ? '✓' : '❐'}</span>
          </button>

          {/* Repo */}
          <div className="flex items-center gap-1">
            <span className="text-outline">Repo:</span>
            <span className="text-on-surface">{repo}</span>
          </div>

          {/* Issue */}
          <div className="flex items-center gap-1">
            <span className="text-outline">Issue:</span>
            <span className="text-on-surface">{issue}</span>
          </div>

          {/* Branch */}
          <div className="flex items-center gap-1">
            <span className="text-outline">Branch:</span>
            <span className="text-tertiary">{branch}</span>
          </div>
        </div>

        {/* Telemetry Metrics: Models, Tokens, Cost */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-lowest border border-outline-variant/30">
            <span className="text-outline">Models:</span>
            <span className="text-on-surface font-semibold">{modelsSummary}</span>
          </div>

          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-lowest border border-outline-variant/30">
            <span className="text-outline">Total Tokens:</span>
            <span className="text-primary font-semibold">{totalTokens.toLocaleString()}</span>
          </div>

          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <span>Cost:</span>
            <span className="font-semibold">{cost}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
