import React from 'react';
import { PipelineTracker } from './PipelineTracker';
import {
  TreeIcon,
  PlayIcon,
  BookIcon,
  SchemaIcon,
  SourceIcon,
  BranchIcon,
  LockIcon,
} from '../icons/Icons';

export const EmptyStatePanel: React.FC = () => {
  return (
    <section className="relative overflow-hidden rounded-xl bg-surface-container-low border border-outline-variant/30 shadow-md">
      {/* Background Ambient Glow Accents */}
      <div className="absolute -right-20 -top-20 w-80 h-80 bg-primary/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -left-20 -bottom-20 w-80 h-80 bg-tertiary/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative p-space-lg md:p-space-xl flex flex-col xl:flex-row items-start xl:items-center justify-between gap-space-xl">
        <div className="flex flex-col md:flex-row gap-space-lg items-start">
          {/* Flow Icon Visualizer */}
          <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-primary shadow-sm">
            <TreeIcon className="w-7 h-7" />
          </div>

          <div className="flex flex-col gap-space-xs max-w-3xl">
            {/* Pipeline Step Tracker */}
            <PipelineTracker />

            <h2 className="text-xl sm:text-2xl font-semibold text-on-surface">
              No Active Autonomous Run
            </h2>

            <p className="text-sm text-on-surface-variant leading-relaxed">
              Initialize a new agent session by targeting a repository issue. Mini-Devin will
              automatically inspect repository files, synthesize an architectural plan, implement
              changes, verify with tests, and submit a pull request.
            </p>

            {/* Contextual Metadata Chips */}
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                <SourceIcon className="w-3.5 h-3.5 text-outline/80" />
                <span>Repo: Pending Selection</span>
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                <BranchIcon className="w-3.5 h-3.5 text-outline/80" />
                <span>Branch: None</span>
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                <LockIcon className="w-3.5 h-3.5 text-outline/80" />
                <span>Runtime: Sandbox Isolated</span>
              </span>
            </div>
          </div>
        </div>

        {/* Action Panel */}
        <div className="flex flex-col sm:flex-row xl:flex-col gap-space-sm w-full xl:w-auto flex-shrink-0">
          <div className="relative group">
            <button
              type="button"
              disabled
              aria-disabled="true"
              className="w-full sm:w-auto xl:w-full flex items-center justify-center gap-2 px-space-lg py-2.5 rounded-lg bg-primary-container/60 text-on-primary-container font-semibold text-sm cursor-not-allowed opacity-75 shadow-sm"
              title="Initialize Agent Run (Placeholder - Not yet connected)"
            >
              <PlayIcon className="w-4 h-4 text-on-primary-container" />
              <span>Initialize Agent Run</span>
            </button>
            <div className="text-center mt-1">
              <span className="font-mono text-[10px] text-outline tracking-tight uppercase">
                PLACEHOLDER - NOT YET CONNECTED
              </span>
            </div>
          </div>

          <div className="flex items-center gap-space-sm w-full">
            <button
              type="button"
              disabled
              aria-disabled="true"
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high/60 border border-outline-variant/30 text-on-surface-variant/70 text-xs cursor-not-allowed opacity-80"
              title="Documentation (Placeholder)"
            >
              <BookIcon className="w-3.5 h-3.5" />
              <span>Documentation</span>
            </button>
            <button
              type="button"
              disabled
              aria-disabled="true"
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high/60 border border-outline-variant/30 text-on-surface-variant/70 text-xs cursor-not-allowed opacity-80"
              title="Workflow Guide (Placeholder)"
            >
              <SchemaIcon className="w-3.5 h-3.5" />
              <span>Workflow Guide</span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
