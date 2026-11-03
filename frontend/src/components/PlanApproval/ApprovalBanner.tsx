import React from 'react';

interface ApprovalBannerProps {
  isAwaitingApproval: boolean;
  timeoutNote?: string;
}

export const ApprovalBanner: React.FC<ApprovalBannerProps> = ({
  isAwaitingApproval,
  timeoutNote,
}) => {
  if (!isAwaitingApproval) {
    return null;
  }

  return (
    <div
      role="alert"
      className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-space-md sm:p-space-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-200 shadow-sm"
    >
      <div className="flex items-start sm:items-center gap-3">
        <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400 flex-shrink-0 mt-0.5 sm:mt-0">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <div>
          <div className="font-semibold text-xs sm:text-sm tracking-wide text-amber-100 uppercase">
            Human Approval Required
          </div>
          <p className="text-xs text-amber-200/90 mt-0.5">
            Autonomous execution is paused at Gate 01. Code modification has not started and will not proceed until approved by a repository maintainer.
          </p>
        </div>
      </div>

      {timeoutNote && (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded bg-amber-500/20 border border-amber-500/30 text-[11px] font-mono text-amber-300 self-start sm:self-auto flex-shrink-0">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span>{timeoutNote}</span>
        </div>
      )}
    </div>
  );
};
