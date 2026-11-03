import React from 'react';
import type { SocketConnectionState } from '../../hooks/types';
import type { FilterCategory } from './liveConsoleUtils';

interface ConsoleControlsProps {
  connectionState: SocketConnectionState;
  activeFilter: FilterCategory;
  onFilterChange: (filter: FilterCategory) => void;
  counts: { all: number; tools: number; thoughts: number; errors: number };
  autoScroll: boolean;
  onToggleAutoScroll: () => void;
  isPaused: boolean;
  onTogglePause: () => void;
  pausedNewCount: number;
  onClear: () => void;
  totalEvents: number;
}

export const ConsoleControls: React.FC<ConsoleControlsProps> = ({
  connectionState,
  activeFilter,
  onFilterChange,
  counts,
  autoScroll,
  onToggleAutoScroll,
  isPaused,
  onTogglePause,
  pausedNewCount,
  onClear,
  totalEvents,
}) => {
  const isConnected = connectionState === 'CONNECTED';
  const isConnecting = connectionState === 'CONNECTING' || connectionState === 'RECONNECTING';

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-space-sm rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs">
      {/* Left: Stream Status & Filter Pills */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Streaming Status Indicator */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full font-mono text-[11px] font-semibold border ${
            isConnected
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : isConnecting
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              : 'bg-surface-container-high text-outline border-outline-variant/30'
          }`}
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`inline-flex rounded-full h-2 w-2 ${
                isConnected
                  ? 'bg-emerald-400 animate-pulse'
                  : isConnecting
                  ? 'bg-amber-400 animate-ping'
                  : 'bg-outline'
              }`}
            />
          </span>
          <span>{isConnected ? 'Streaming Live' : connectionState}</span>
        </div>

        {/* Filter Pills */}
        <div className="inline-flex p-0.5 rounded-lg bg-surface-container border border-outline-variant/20 font-mono text-xs">
          {(
            [
              { id: 'all', label: 'All', count: counts.all },
              { id: 'tools', label: 'Tools', count: counts.tools },
              { id: 'thoughts', label: 'Thoughts', count: counts.thoughts },
              { id: 'errors', label: 'Errors', count: counts.errors },
            ] as const
          ).map((tab) => {
            const isActive = activeFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onFilterChange(tab.id)}
                className={`px-2.5 py-1 rounded transition-all flex items-center gap-1 ${
                  isActive
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1 py-0.2 rounded ${
                    isActive
                      ? 'bg-on-primary-container/20 text-on-primary-container'
                      : 'bg-surface-container-high text-outline'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: Stream Controls */}
      <div className="flex items-center gap-2 font-mono text-xs flex-wrap">
        {/* Auto-scroll Toggle */}
        <button
          type="button"
          onClick={onToggleAutoScroll}
          className={`flex items-center gap-1 px-2.5 py-1 rounded border text-[11px] transition-colors ${
            autoScroll
              ? 'bg-primary/10 border-primary/30 text-primary'
              : 'bg-surface-container-high border-outline-variant/30 text-outline'
          }`}
          title="Auto-scroll to latest incoming events"
        >
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="6 9 12 15 18 9" />
          </svg>
          <span>Auto-scroll: {autoScroll ? 'ON' : 'OFF'}</span>
        </button>

        {/* Pause Stream Toggle */}
        <button
          type="button"
          onClick={onTogglePause}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-colors ${
            isPaused
              ? 'bg-amber-500/20 border-amber-500/40 text-amber-300 font-semibold'
              : 'bg-surface-container-high hover:bg-surface-container-highest border-outline-variant/30 text-outline hover:text-on-surface'
          }`}
          title={isPaused ? 'Resume live event stream' : 'Pause stream (snapshot view)'}
        >
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {isPaused ? (
              <polygon points="5 3 19 12 5 21 5 3" />
            ) : (
              <>
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </>
            )}
          </svg>
          <span>{isPaused ? 'Resume Stream' : 'Pause Stream'}</span>
          {isPaused && pausedNewCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-amber-400 text-surface-container-lowest font-bold text-[10px]">
              +{pausedNewCount}
            </span>
          )}
        </button>

        {/* Clear Buffer */}
        <button
          type="button"
          onClick={onClear}
          disabled={totalEvents === 0}
          className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-[11px] disabled:opacity-40 transition-colors"
          title="Clear local in-memory event buffer"
        >
          Clear
        </button>
      </div>
    </div>
  );
};
