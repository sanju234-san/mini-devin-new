import React from 'react';
import type { AffectedFile } from './types';

interface AffectedFilesMatrixProps {
  files?: AffectedFile[];
}

export const AffectedFilesMatrix: React.FC<AffectedFilesMatrixProps> = ({ files = [] }) => {
  let netAdded = 0;
  let netDeleted = 0;

  files.forEach((f) => {
    if (f.delta) {
      netAdded += f.delta.added || 0;
      netDeleted += f.delta.deleted || 0;
    }
  });

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-3 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
            <polyline points="13 2 13 9 20 9" />
          </svg>
          <h3 className="font-bold text-xs sm:text-sm text-on-surface uppercase tracking-wider font-mono">
            Affected Files Inspection Matrix
          </h3>
        </div>

        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-high text-outline border border-outline-variant/30">
          {files.length} {files.length === 1 ? 'file' : 'files'} targeted
        </span>
      </div>

      {/* Table Container with independent horizontal scrolling */}
      <div className="overflow-x-auto rounded-lg border border-outline-variant/20 bg-surface-container-lowest/60">
        <table className="w-full text-left text-xs font-mono border-collapse min-w-[500px]">
          <thead>
            <tr className="border-b border-outline-variant/30 text-[10px] text-outline uppercase tracking-wider bg-surface-container-high/40">
              <th className="py-2.5 px-3 font-semibold">File Path</th>
              <th className="py-2.5 px-3 font-semibold w-24">Status</th>
              <th className="py-2.5 px-3 font-semibold w-28">Delta</th>
              <th className="py-2.5 px-3 font-semibold">Target Scope</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/15 text-[11px]">
            {files.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-6 text-center text-outline">
                  No affected files declared in current plan.
                </td>
              </tr>
            ) : (
              files.map((file, idx) => {
                let statusBadge = (
                  <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-semibold bg-surface-container-high text-outline border border-outline-variant/30">
                    {file.status}
                  </span>
                );

                if (file.status === 'MODIFIED') {
                  statusBadge = (
                    <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                      MODIFIED
                    </span>
                  );
                } else if (file.status === 'ADDED') {
                  statusBadge = (
                    <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                      ADDED
                    </span>
                  );
                } else if (file.status === 'DELETED') {
                  statusBadge = (
                    <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-semibold bg-red-500/10 text-red-300 border border-red-500/30">
                      DELETED
                    </span>
                  );
                }

                return (
                  <tr key={`${file.path}-${idx}`} className="hover:bg-surface-container-high/30 transition-colors">
                    <td className="py-2 px-3 text-on-surface flex items-center gap-1.5">
                      <span className="text-outline">&lt;&gt;</span>
                      <span className="truncate max-w-xs">{file.path}</span>
                    </td>
                    <td className="py-2 px-3">{statusBadge}</td>
                    <td className="py-2 px-3">
                      {file.delta ? (
                        <span className="text-emerald-400 font-semibold">
                          +{file.delta.added}{' '}
                          <span className="text-red-400 font-normal">-{file.delta.deleted}</span>
                        </span>
                      ) : (
                        <span className="text-outline">n/a</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-on-surface-variant truncate max-w-xs">
                      {file.targetScope || 'n/a'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Notes */}
      <div className="flex items-center justify-between flex-wrap gap-2 text-[10px] font-mono text-outline pt-1">
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>Monaco Side-by-Side Diff Viewer is activated upon stage approval (separate feature).</span>
        </div>

        {files.length > 0 && (
          <span className="font-semibold text-on-surface-variant">
            Net: <span className="text-emerald-400">+{netAdded}</span> /{' '}
            <span className="text-red-400">-{netDeleted}</span> net lines
          </span>
        )}
      </div>
    </div>
  );
};
