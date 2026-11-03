'use client';

import React, { useState } from 'react';
import type { TestCaseResult, TestResultFilter, TestSuiteSummary } from './testsAndPreviewUtils';

interface TestResultsPanelProps {
  testCases: TestCaseResult[];
  summary: TestSuiteSummary;
  onNavigateToDiff?: (filePath?: string) => void;
  isSkeleton?: boolean;
}

export const TestResultsPanel: React.FC<TestResultsPanelProps> = ({
  testCases,
  summary,
  onNavigateToDiff,
  isSkeleton = false,
}) => {
  const [activeFilter, setActiveFilter] = useState<TestResultFilter>('all');
  const [downloadingXml, setDownloadingXml] = useState(false);

  const filteredTests = testCases.filter((tc) => {
    if (activeFilter === 'failed') return tc.status === 'failed';
    if (activeFilter === 'passed') return tc.status === 'passed';
    return true;
  });

  const failedCount = testCases.filter((tc) => tc.status === 'failed').length;
  const passedCount = testCases.filter((tc) => tc.status === 'passed').length;

  const handleDownloadJunitXml = () => {
    setDownloadingXml(true);
    // Generate a clean JUnit XML string client-side from real/preview test data
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="MiniDevin.SandboxSuite" tests="${summary.totalTests}" failures="${summary.failedCount}" skipped="${summary.skippedCount}" time="${summary.durationSec}">
${testCases
  .map(
    (tc) => `  <testcase name="${tc.name}" classname="${tc.filePath}" time="${(tc.durationMs / 1000).toFixed(3)}">
${
  tc.status === 'failed'
    ? `    <failure message="${tc.assertionError || 'Test failed'}">${tc.description || ''}</failure>`
    : ''
}${tc.status === 'skipped' ? '    <skipped/>' : ''}
  </testcase>`
  )
  .join('\n')}
</testsuite>`;

    const blob = new Blob([xml], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `junit-results-${summary.status.toLowerCase()}.xml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setTimeout(() => setDownloadingXml(false), 1500);
  };

  if (isSkeleton) {
    return (
      <div className="flex flex-col rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden p-space-md gap-3 animate-pulse">
        <div className="h-6 bg-surface-container-high rounded w-1/2" />
        <div className="h-8 bg-surface-container-high rounded w-full" />
        <div className="h-20 bg-surface-container-high rounded w-full" />
        <div className="h-20 bg-surface-container-high rounded w-full" />
        <div className="h-12 bg-surface-container-high rounded w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-xs">
      {/* 1. Header */}
      <div className="px-space-md py-3 bg-surface-container-high/60 border-b border-outline-variant/20 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-primary"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <span className="font-bold text-xs tracking-tight text-on-surface">
            Test Results
          </span>
          <span className="px-1.5 py-0.2 rounded text-[11px] font-mono bg-surface-container text-primary font-bold">
            {testCases.length}
          </span>
        </div>

        {/* JUnit XML Action Button */}
        <button
          type="button"
          onClick={handleDownloadJunitXml}
          disabled={downloadingXml}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-[11px] font-mono transition-colors"
          title="Download JUnit XML test report"
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
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>{downloadingXml ? 'Generating...' : 'JUnit XML'}</span>
        </button>
      </div>

      {/* 2. Filter Tabs */}
      <div className="px-space-md py-2 border-b border-outline-variant/20 flex items-center gap-1.5 font-mono text-xs">
        <button
          type="button"
          onClick={() => setActiveFilter('all')}
          className={`px-3 py-1 rounded-md transition-colors ${
            activeFilter === 'all'
              ? 'bg-surface-container-highest text-on-surface font-semibold border border-outline-variant/40'
              : 'text-outline hover:text-on-surface'
          }`}
        >
          All ({testCases.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveFilter('failed')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
            activeFilter === 'failed'
              ? 'bg-red-500/20 text-red-400 font-bold border border-red-500/40'
              : 'text-outline hover:text-red-400'
          }`}
        >
          <span>Failed</span>
          {failedCount > 0 && (
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block" />
          )}
          <span>({failedCount})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveFilter('passed')}
          className={`px-3 py-1 rounded-md transition-colors ${
            activeFilter === 'passed'
              ? 'bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/40'
              : 'text-outline hover:text-emerald-400'
          }`}
        >
          Passed ({passedCount})
        </button>
      </div>

      {/* 3. Test Cases List */}
      <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-2.5 max-h-[580px]">
        {filteredTests.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-outline text-xs font-mono">
            <span>No test cases in this view.</span>
          </div>
        ) : (
          filteredTests.map((tc) => {
            const isFailed = tc.status === 'failed';
            const isPassed = tc.status === 'passed';

            return (
              <div
                key={tc.id}
                className={`p-3 rounded-lg border transition-all ${
                  isFailed
                    ? 'bg-red-950/15 border-red-500/30'
                    : isPassed
                    ? 'bg-surface-container/60 border-outline-variant/20 hover:border-outline-variant/40'
                    : 'bg-surface-container/40 border-outline-variant/20'
                }`}
              >
                {/* Header: Status Icon + Test Name + Duration */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="mt-0.5 shrink-0">
                      {isFailed ? (
                        <svg
                          className="w-4 h-4 text-red-400"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <line x1="15" y1="9" x2="9" y2="15" />
                          <line x1="9" y1="9" x2="15" y2="15" />
                        </svg>
                      ) : isPassed ? (
                        <svg
                          className="w-4 h-4 text-emerald-400"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <polyline points="9 12 11 14 15 10" />
                        </svg>
                      ) : (
                        <svg
                          className="w-4 h-4 text-outline"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <polygon points="10 8 16 12 10 16 10 8" />
                        </svg>
                      )}
                    </span>

                    <div className="flex flex-col min-w-0">
                      <span
                        className={`text-xs font-mono font-bold break-all ${
                          isFailed ? 'text-red-300' : 'text-on-surface'
                        }`}
                      >
                        {tc.name}
                      </span>
                      <span className="text-[11px] font-mono text-outline truncate">
                        {tc.filePath}
                      </span>
                    </div>
                  </div>

                  <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-high text-outline">
                    {tc.durationMs}ms
                  </span>
                </div>

                {/* Expanded Failure Card */}
                {isFailed && (
                  <div className="mt-2.5 p-2.5 rounded bg-surface-container-lowest border border-red-500/25 flex flex-col gap-2 font-mono text-xs">
                    {tc.assertionError && (
                      <div className="flex items-start gap-1.5 text-red-400 font-medium">
                        <svg
                          className="w-4 h-4 shrink-0 mt-0.5"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="8" x2="12" y2="12" />
                          <line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                        <span>{tc.assertionError}</span>
                      </div>
                    )}

                    {tc.description && (
                      <p className="text-[11px] text-outline leading-relaxed">
                        {tc.description}
                      </p>
                    )}

                    {/* Inline Assertion Diff View */}
                    {tc.inlineDiff && (
                      <div className="p-2 rounded bg-[#04080e] border border-outline-variant/20 flex flex-col gap-0.5 text-[11px]">
                        <span className="text-[10px] uppercase tracking-wider text-outline select-none">
                          Inline Diff:
                        </span>
                        <span className="text-red-400 font-bold bg-red-950/40 px-1 py-0.5 rounded">
                          - [{tc.inlineDiff.expected}]
                        </span>
                        <span className="text-emerald-400 font-bold bg-emerald-950/40 px-1 py-0.5 rounded">
                          + [{tc.inlineDiff.actual}]
                        </span>
                      </div>
                    )}

                    {/* Stack Trace / Source File Location + Inspect in Diff Link */}
                    <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20 text-[11px]">
                      <span className="text-outline truncate">
                        {tc.stackTraceLocation || tc.filePath}
                      </span>

                      {onNavigateToDiff && (
                        <button
                          type="button"
                          onClick={() => onNavigateToDiff(tc.targetFile)}
                          className="flex items-center gap-1 text-primary hover:text-primary/80 font-bold hover:underline shrink-0 ml-2"
                          title="Open modified file in Diff Viewer (Task 6)"
                        >
                          <span>Inspect in Diff</span>
                          <svg
                            className="w-3 h-3"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Skipped Message */}
                {tc.status === 'skipped' && tc.description && (
                  <div className="mt-1.5 text-[11px] font-mono text-outline italic">
                    {tc.description}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 4. Sandbox Isolation Status & Concurrency Footer */}
      <div className="px-space-md py-2.5 bg-surface-container-high/60 border-t border-outline-variant/20 flex flex-col gap-1.5 font-mono text-[11px]">
        <div className="flex items-center justify-between text-outline">
          <span>Sandbox Isolation Status</span>
          <span className="text-emerald-400 font-bold">
            {summary.isolationStatus}
          </span>
        </div>
        <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${
              summary.isolationStatus === 'Healthy'
                ? 'bg-emerald-400'
                : summary.isolationStatus === 'Degraded'
                ? 'bg-amber-400'
                : 'bg-red-400'
            }`}
            style={{ width: '100%' }}
          />
        </div>

        <div className="flex items-center justify-between text-outline/80 pt-0.5 text-[10px]">
          <span>Concurrency: {summary.concurrency}</span>
          <span>
            Exit Code:{' '}
            {summary.exitCode === 0
              ? '0 (success)'
              : summary.exitCode !== null
              ? `${summary.exitCode} (${summary.status.toLowerCase()})`
              : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  );
};
