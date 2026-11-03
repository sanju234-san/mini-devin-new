'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { DiffViewerData, DiffRenderMode, DiffViewerState, FileDiffItem } from './types';
import { SYNTHETIC_PREVIEW_DIFF, detectLanguage, parseUnifiedDiffText } from './diffUtils';
import { getArtifacts, getRunById } from '../../services/api';
import type { ApiError } from '../../services/types';
import { DiffHeader } from './DiffHeader';
import { DiffControls } from './DiffControls';
import { ChangeSummaryBar } from './ChangeSummaryBar';
import { FileSelector } from './FileSelector';
import { MonacoDiffEditor } from './MonacoDiffEditor';
import { DiffSkeleton } from './DiffSkeleton';

const isProduction = process.env.NODE_ENV === 'production';

interface DiffViewerProps {
  runId?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ runId = 'run-8924a' }) => {
  // In production, force 'real' API mode strictly. In development, default to 'preview-active' for Stitch fidelity.
  const [previewState, setPreviewState] = useState<DiffViewerState>(
    isProduction ? 'real' : 'preview-active'
  );
  const [renderMode, setRenderMode] = useState<DiffRenderMode>('inline');
  const [selectedFileIndex, setSelectedFileIndex] = useState<number>(0);

  // Real API State
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [realDiffData, setRealDiffData] = useState<DiffViewerData | null>(null);

  // Monaco Diff Navigator ref
  const navigatorRef = useRef<{ next: () => void; previous: () => void } | null>(null);

  // Fetch real diff from existing API interfaces (getRunById + getArtifacts)
  const fetchRealDiff = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch Run Metadata
      let repository: string | undefined;
      let issueId: string | undefined;
      let branch: string | undefined;

      try {
        const run = await getRunById(runId);
        repository = run.repository;
        issueId = run.issueId !== undefined && run.issueId !== null ? String(run.issueId) : undefined;
        branch = typeof run.branch === 'string' ? run.branch : undefined;
      } catch {
        // Non-fatal if run details endpoint is pending in backend contract
      }

      // 2. Fetch Artifacts for Diff
      const artifacts = await getArtifacts(runId);

      if (!artifacts.diff) {
        setRealDiffData({
          metadata: {
            runId,
            repository,
            issueId,
            branch,
          },
          files: [],
          totalAdditions: 0,
          totalDeletions: 0,
        });
        return;
      }

      // 3. Parse diff text or structured diff JSON matching Diff schema in docs/design/schemas.md
      let files: FileDiffItem[] = [];
      let totalAdditions = 0;
      let totalDeletions = 0;
      let planVersionId: string | undefined;
      let changeSummary: string | undefined;
      let testsAdded: string[] | undefined;

      let parsed: any = null;
      if (typeof artifacts.diff === 'string') {
        try {
          parsed = JSON.parse(artifacts.diff);
        } catch {
          parsed = null;
        }
      } else if (typeof artifacts.diff === 'object' && artifacts.diff !== null) {
        parsed = artifacts.diff;
      }

      if (parsed && parsed.file_changes && Array.isArray(parsed.file_changes)) {
        planVersionId = parsed.plan_version_id;
        changeSummary = parsed.change_summary;
        testsAdded = parsed.tests_added;

        files = parsed.file_changes.map((fc: any) => {
          const parsedDiff = parseUnifiedDiffText(fc.diff_text || '');
          totalAdditions += parsedDiff.additions;
          totalDeletions += parsedDiff.deletions;
          return {
            path: fc.path,
            changeType: fc.change_type || 'modify',
            language: detectLanguage(fc.path),
            diffText: fc.diff_text,
            originalCode: parsedDiff.originalCode,
            modifiedCode: parsedDiff.modifiedCode,
            additions: parsedDiff.additions,
            deletions: parsedDiff.deletions,
            requirementIds: fc.requirement_ids,
          };
        });
      } else if (typeof artifacts.diff === 'string') {
        // Raw unified diff string fallback
        const parsedDiff = parseUnifiedDiffText(artifacts.diff);
        totalAdditions = parsedDiff.additions;
        totalDeletions = parsedDiff.deletions;
        files = [
          {
            path: 'changes.diff',
            changeType: 'modify',
            language: 'plaintext',
            diffText: artifacts.diff,
            originalCode: parsedDiff.originalCode,
            modifiedCode: parsedDiff.modifiedCode,
            additions: parsedDiff.additions,
            deletions: parsedDiff.deletions,
          },
        ];
      }

      setRealDiffData({
        metadata: {
          runId,
          repository,
          issueId,
          branch,
          planVersionId,
          changeSummary,
          testsAdded,
        },
        files,
        totalAdditions,
        totalDeletions,
      });
      setSelectedFileIndex(0);
    } catch (err) {
      setError(err as ApiError);
      setRealDiffData(null);
    } finally {
      setIsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (previewState === 'real') {
      fetchRealDiff();
    }
  }, [previewState, fetchRealDiff]);

  // Determine active dataset based on state — zero mock fallback in production
  const activeData: DiffViewerData | null =
    !isProduction && previewState === 'preview-active'
      ? SYNTHETIC_PREVIEW_DIFF
      : previewState === 'real'
      ? realDiffData
      : null;

  const currentFile = activeData?.files[selectedFileIndex] || activeData?.files[0];

  const handlePrevChange = () => {
    navigatorRef.current?.previous();
  };

  const handleNextChange = () => {
    navigatorRef.current?.next();
  };

  return (
    <div className="flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto p-space-md sm:p-space-lg select-none">
      {/* 1. Header with Metadata Chips */}
      <DiffHeader
        metadata={
          activeData?.metadata ||
          (previewState === 'real' ? { runId } : SYNTHETIC_PREVIEW_DIFF.metadata)
        }
      />

      {/* 2. Top Controls: Inline/Side-by-Side + Prev/Next + Preview State Selector */}
      <DiffControls
        renderMode={renderMode}
        onChangeRenderMode={setRenderMode}
        onPrevChange={handlePrevChange}
        onNextChange={handleNextChange}
        previewState={previewState}
        onChangePreviewState={setPreviewState}
      />

      {/* Real API Error State */}
      {previewState === 'real' && error && (
        <div
          role="alert"
          className="rounded-xl bg-red-950/20 border border-red-500/30 p-space-md flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-red-200 shadow-sm"
        >
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <div className="flex flex-col gap-0.5 text-xs">
              <span className="font-semibold text-red-100 uppercase tracking-wide font-mono">
                {error.kind} — Backend Diff Ingestion Suspended
              </span>
              <p className="text-red-300/80 font-mono">{error.message}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={fetchRealDiff}
            className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200 text-xs font-mono transition-colors"
          >
            Retry Ingestion
          </button>
        </div>
      )}

      {/* Loading Skeleton View */}
      {(previewState === 'preview-loading' || (previewState === 'real' && isLoading)) && (
        <DiffSkeleton />
      )}

      {/* Empty State View */}
      {(previewState === 'preview-empty' ||
        (previewState === 'real' && !isLoading && !error && (!activeData?.files || activeData.files.length === 0))) && (
        <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-xl flex flex-col items-center justify-center text-center gap-3 shadow-sm min-h-[360px]">
          <div className="p-3 rounded-full bg-surface-container-high text-outline">
            <svg className="w-8 h-8 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          <span className="font-semibold text-sm text-on-surface">No Code Changes Registered</span>
          <p className="text-xs text-on-surface-variant font-mono max-w-md">
            The Coder Agent has not yet produced a verified diff for run{' '}
            <code className="text-primary">{runId}</code>.
          </p>
        </div>
      )}

      {/* Active Diff Content View */}
      {previewState !== 'preview-loading' &&
        previewState !== 'preview-empty' &&
        !(previewState === 'real' && (isLoading || error || !activeData?.files.length)) &&
        activeData &&
        currentFile && (
          <div className="flex flex-col gap-space-sm">
            {/* 3. Change Summary Bar (3 Files Changed, +42, -18, AST Context) */}
            <ChangeSummaryBar
              filesCount={activeData.files.length}
              totalAdditions={activeData.totalAdditions}
              totalDeletions={activeData.totalDeletions}
            />

            {/* 4. Selectable Changed Files Bar */}
            <FileSelector
              files={activeData.files}
              selectedIndex={selectedFileIndex}
              onSelectIndex={setSelectedFileIndex}
            />

            {/* 5. Monaco Diff Editor Card */}
            <MonacoDiffEditor
              file={currentFile}
              renderMode={renderMode}
              onMountNavigator={(nav) => {
                navigatorRef.current = nav;
              }}
            />
          </div>
        )}
    </div>
  );
};
