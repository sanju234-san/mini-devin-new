import React from 'react';
import type { IssueContext } from './types';

interface IssueContextCardProps {
  issue?: IssueContext;
}

export const IssueContextCard: React.FC<IssueContextCardProps> = ({ issue }) => {
  if (!issue) {
    return (
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg text-outline text-xs font-mono">
        Issue context not provided in current run data.
      </div>
    );
  }

  const priorityLabel = issue.priority || 'n/a';
  const repoLabel = issue.repository || 'n/a';
  const issueNum = issue.issueNumber !== undefined ? `#${issue.issueNumber}` : '';
  const reporterLabel = issue.reporter ? `Reported by @${issue.reporter}` : 'Reporter: n/a';

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-3 shadow-sm">
      {/* Top Metadata Badges */}
      <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-red-500/20 text-red-300 border border-red-500/30 font-semibold">
            {priorityLabel}
          </span>
          <span className="font-mono text-xs text-on-surface font-medium">
            {repoLabel}
            {issueNum && <span className="text-primary font-semibold ml-0.5">{issueNum}</span>}
          </span>
          <span className="text-outline text-xs">·</span>
          <span className="text-outline text-xs font-mono">{reporterLabel}</span>
        </div>

        {issue.category && (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-high text-on-surface-variant border border-outline-variant/30">
            {issue.category}
          </span>
        )}
      </div>

      {/* Issue Title */}
      <h2 className="text-base sm:text-lg font-bold text-on-surface tracking-tight leading-snug">
        {issue.title || 'Untitled Issue Context'}
      </h2>

      {/* Issue Description */}
      {issue.description && (
        <p className="text-xs sm:text-sm text-on-surface-variant leading-relaxed font-sans bg-surface-container/40 p-space-sm rounded-lg border border-outline-variant/20">
          {issue.description}
        </p>
      )}

      {/* Extracted Labels */}
      {issue.labels && issue.labels.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap pt-1">
          <span className="font-mono text-[10px] uppercase tracking-wider text-outline">
            Extracted Labels:
          </span>
          {issue.labels.map((label) => (
            <span
              key={label}
              className="px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-high text-primary border border-primary/20"
            >
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
