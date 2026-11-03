import React from 'react';
import { PlayIcon, BookIcon } from '../icons/Icons';

export const EmptyDatasetState: React.FC = () => {
  return (
    <div
      className="rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-sm"
      aria-label="Empty dataset state"
    >
      {/* State Header Bar */}
      <div className="px-space-md py-2.5 bg-surface-container/60 border-b border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-secondary/10 text-secondary border border-secondary/30 font-semibold">
            STATE 02
          </span>
          <span className="font-semibold text-on-surface">
            Empty Dataset / Zero Runs Found
          </span>
          <span className="font-mono text-[11px] text-outline hidden sm:inline">
            HTTP 200 OK — [ data: [], total: 0 ]
          </span>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-outline border border-outline-variant/30">
          Target: Standby
        </span>
      </div>

      {/* Main Empty State Container */}
      <div className="p-space-lg md:p-space-xl flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-12">
        {/* Empty State Icon */}
        <div className="w-16 h-16 rounded-2xl bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-primary/80 mb-space-md shadow-sm">
          <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            <line x1="12" y1="11" x2="12" y2="17" />
            <line x1="9" y1="14" x2="15" y2="14" />
          </svg>
        </div>

        <h3 className="text-lg sm:text-xl font-semibold text-on-surface mb-2">
          No Autonomous Runs Recorded
        </h3>

        <p className="text-sm text-on-surface-variant leading-relaxed mb-space-lg max-w-lg">
          No Mini-Devin execution runs found for repository. Start an autonomous coding task targeting an open issue or dispatch an ad-hoc run.
        </p>

        {/* Action Buttons (Disabled Placeholders) */}
        <div className="flex flex-col sm:flex-row items-center gap-space-sm w-full justify-center mb-space-xl">
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-space-lg py-2.5 rounded-lg bg-primary-container/60 text-on-primary-container font-semibold text-sm cursor-not-allowed opacity-75 shadow-sm"
            title="Dispatch New Run (Placeholder - Not yet connected)"
          >
            <PlayIcon className="w-4 h-4 text-on-primary-container" />
            <span>Dispatch New Run (Configuration)</span>
          </button>

          <button
            type="button"
            disabled
            aria-disabled="true"
            className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-space-md py-2.5 rounded-lg bg-surface-container-high/60 border border-outline-variant/30 text-on-surface-variant/70 text-xs cursor-not-allowed opacity-80"
            title="Quickstart & Agent Docs (Placeholder)"
          >
            <BookIcon className="w-3.5 h-3.5" />
            <span>Quickstart &amp; Agent Docs</span>
          </button>
        </div>

        {/* Alternative Intake Triggers Info Callout */}
        <div className="w-full rounded-lg bg-surface-container/70 border border-outline-variant/20 p-space-md text-left text-xs font-mono">
          <div className="flex items-center gap-2 text-primary font-semibold mb-2">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            <span>Alternative Intake Triggers</span>
          </div>
          <ul className="flex flex-col gap-1 text-outline pl-5 list-disc">
            <li>
              Automated triage via GitHub Webhook on issue label{' '}
              <span className="text-secondary font-semibold">devin:plan</span>
            </li>
            <li>
              Direct dispatch via CLI runtime:{' '}
              <span className="text-teal-400 font-semibold">
                mini-devin run --issue 482 --target main
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};
