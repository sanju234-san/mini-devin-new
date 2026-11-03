import React, { useState, useEffect } from 'react';
import { getMetrics } from '../../services/api';
import {
  EvalInspectMode,
  SAMPLE_EVAL_SUMMARY,
  SAMPLE_SCORE_TREND,
  SAMPLE_OUTCOME_BREAKDOWN,
  SAMPLE_RESOURCE_TELEMETRY,
  SAMPLE_EVAL_ITEMS,
  SAMPLE_FAILURE_DETAILS,
  EvalItem,
  EvaluationSummary,
  OutcomeBreakdownData,
  ScoreTrendPoint,
  ResourceTelemetryData,
  parseRealMetrics,
} from './evalResultsUtils';
import { EvalHeader } from './EvalHeader';
import { EvalSummaryCards } from './EvalSummaryCards';
import { EvalTrendsAndBreakdown } from './EvalTrendsAndBreakdown';
import { EvalItemsTable } from './EvalItemsTable';
import { FailureInspector } from './FailureInspector';

interface EvalResultsProps {
  onNavigateToDiff?: () => void;
  runId?: string;
}

export const EvalResults: React.FC<EvalResultsProps> = ({
  onNavigateToDiff,
  runId = 'run-8924a',
}) => {
  // Mode: 'live' (binds to real backend API) vs 'preview' (explicit illustrative preview)
  const [dataMode, setDataMode] = useState<'live' | 'preview'>('live');

  // Live REST API state
  const [liveStatus, setLiveStatus] = useState<'loading' | 'success' | 'empty' | 'unavailable'>('loading');
  const [apiErrorMessage, setApiErrorMessage] = useState<string | null>(null);

  // Real data state derived from backend
  const [realSummary, setRealSummary] = useState<EvaluationSummary | null>(null);
  const [realItems, setRealItems] = useState<EvalItem[]>([]);
  const [realBreakdown, setRealBreakdown] = useState<OutcomeBreakdownData | null>(null);
  const [realTrend, setRealTrend] = useState<ScoreTrendPoint[]>([]);
  const [realTelemetry, setRealTelemetry] = useState<ResourceTelemetryData | null>(null);

  // Preview sub-mode: 'failed' | 'passed' | 'running'
  const [previewSubMode, setPreviewSubMode] = useState<EvalInspectMode>('failed');
  const [selectedItemId, setSelectedItemId] = useState<string>('eval_item_01');

  // Fetch real evaluation metrics from REST client on mount
  useEffect(() => {
    let isMounted = true;
    setLiveStatus('loading');
    setApiErrorMessage(null);

    getMetrics()
      .then((data) => {
        if (!isMounted) return;
        const parsed = parseRealMetrics(data, runId);
        if (parsed && parsed.items.length > 0) {
          setRealSummary(parsed.summary);
          setRealItems(parsed.items);
          setRealBreakdown(parsed.breakdown);
          setRealTrend(parsed.trend);
          setRealTelemetry(parsed.telemetry);
          setLiveStatus('success');
        } else {
          setLiveStatus('empty');
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setLiveStatus('unavailable');
        setApiErrorMessage(
          err instanceof Error
            ? err.message
            : 'GET /api/v1/metrics route not found in backend/app/main.py (HTTP 404)'
        );
      });

    return () => {
      isMounted = false;
    };
  }, [runId]);

  // Export JSON handler
  const handleExportJson = () => {
    const isPreview = dataMode === 'preview';
    const exportBundle = {
      runId,
      exportedAt: new Date().toISOString(),
      dataSource: isPreview ? 'PREVIEW_ILLUSTRATIVE_STITCH_FIXTURE' : 'REAL_BACKEND_DATA',
      summary: isPreview ? SAMPLE_EVAL_SUMMARY : realSummary,
      trend: isPreview ? SAMPLE_SCORE_TREND : realTrend,
      outcome: isPreview ? SAMPLE_OUTCOME_BREAKDOWN : realBreakdown,
      telemetry: isPreview ? SAMPLE_RESOURCE_TELEMETRY : realTelemetry,
      items: isPreview ? SAMPLE_EVAL_ITEMS : realItems,
      failure: isPreview ? SAMPLE_FAILURE_DETAILS : null,
    };
    const blob = new Blob([JSON.stringify(exportBundle, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `eval-results-${runId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-space-lg p-space-md sm:p-space-lg w-full max-w-[1600px] mx-auto text-on-surface">
      {/* PREVIEW MODE WARNING BANNER */}
      {dataMode === 'preview' ? (
        <div className="p-3 rounded-lg bg-amber-500/15 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono">
          <div className="flex items-center gap-2 text-amber-300">
            <span className="font-bold">⚠️ PREVIEW MODE</span>
            <span>
              All numbers, test names, scores, and stack traces displayed below are illustrative placeholders from the Stitch design spec for UI evaluation only.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setDataMode('live')}
            className="px-3 py-1 rounded bg-surface-container-high border border-outline-variant/40 text-on-surface hover:bg-surface-container-highest transition-colors font-semibold shrink-0"
          >
            ← Return to Live Mode
          </button>
        </div>
      ) : (
        /* Real Mode Source Indicator */
        <div className="flex items-center justify-between text-xs font-mono text-outline px-1">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${liveStatus === 'success' ? 'bg-emerald-400' : liveStatus === 'loading' ? 'bg-primary animate-pulse' : 'bg-amber-400'}`} />
            <span>Live Data Mode: {liveStatus.toUpperCase()} (Connected to REST client GET /api/v1/metrics)</span>
          </div>
          <button
            type="button"
            onClick={() => setDataMode('preview')}
            className="text-[11px] text-primary hover:underline"
          >
            Inspect Illustrative Stitch Preview →
          </button>
        </div>
      )}

      {/* =========================================================================
          REAL DATA PATH
          ========================================================================= */}
      {dataMode === 'live' && (
        <>
          {/* 1. LOADING STATE */}
          {liveStatus === 'loading' && (
            <div className="p-12 my-6 bg-surface-container-lowest border border-outline-variant/30 rounded-xl flex flex-col items-center justify-center text-center font-mono">
              <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin mb-3" />
              <div className="text-sm font-semibold text-on-surface">Fetching Live Evaluation Metrics...</div>
              <div className="text-xs text-outline mt-1">Calling GET /api/v1/metrics</div>
            </div>
          )}

          {/* 2. HONEST UNAVAILABLE / ERROR STATE */}
          {liveStatus === 'unavailable' && (
            <div className="flex flex-col items-center justify-center p-12 my-6 bg-surface-container-lowest border border-amber-500/30 rounded-xl text-center">
              <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center mb-3">
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <h2 className="text-base font-bold text-on-surface mb-1">
                Evaluation Data Unavailable
              </h2>
              <p className="text-xs text-outline max-w-md mb-2 font-mono">
                {apiErrorMessage || 'GET /api/v1/metrics route not found in backend/app/main.py (HTTP 404).'}
              </p>
              <div className="p-3 rounded bg-surface-container-high/60 border border-outline-variant/20 max-w-lg mb-4 text-[11px] font-mono text-on-surface-variant text-left leading-relaxed">
                <div><span className="text-primary font-bold">Ownership Limitation:</span></div>
                <div>• <span className="font-semibold text-on-surface">Tamanna (Backend Owner):</span> Needs to expose <code className="text-primary">GET /api/v1/metrics</code> in FastAPI.</div>
                <div>• <span className="font-semibold text-on-surface">Sanjeevni (Evaluation Owner):</span> Needs to execute test suites and compute fix accuracy and pass rates.</div>
                <div>• <span className="font-semibold text-on-surface">Nikunj (Frontend):</span> Strictly displaying real data without fabricating false success results.</div>
              </div>
              <button
                type="button"
                onClick={() => setDataMode('preview')}
                className="px-4 py-2 rounded bg-surface-container-high border border-outline-variant/40 text-primary text-xs font-semibold hover:bg-surface-container-highest transition-colors"
              >
                Inspect Illustrative Stitch Preview (Placeholder Layout)
              </button>
            </div>
          )}

          {/* 3. HONEST EMPTY STATE */}
          {liveStatus === 'empty' && (
            <div className="flex flex-col items-center justify-center p-12 my-6 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-center">
              <div className="w-12 h-12 rounded-full bg-surface-container-high border border-outline-variant/40 text-outline flex items-center justify-center mb-3">
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="8" y1="12" x2="16" y2="12" />
                </svg>
              </div>
              <h2 className="text-base font-bold text-on-surface mb-1">
                No Evaluation Data Found
              </h2>
              <p className="text-xs text-outline max-w-md mb-4 font-mono">
                The backend returned 200 OK, but no evaluation criteria or benchmark metrics have been recorded for run #{runId}.
              </p>
              <button
                type="button"
                onClick={() => setDataMode('preview')}
                className="px-4 py-1.5 rounded bg-surface-container-high border border-outline-variant/40 text-primary text-xs font-semibold hover:bg-surface-container-highest transition-colors"
              >
                Inspect Illustrative Stitch Preview
              </button>
            </div>
          )}

          {/* 4. REAL DATA SUCCESS VIEW */}
          {liveStatus === 'success' && realSummary && realBreakdown && realTelemetry && (
            <>
              <EvalHeader
                summary={realSummary}
                inspectMode="passed"
                onSelectInspectMode={() => {}}
              />
              <EvalSummaryCards
                summary={realSummary}
                isAllPassed={realSummary.failedCount === 0}
              />
              <EvalTrendsAndBreakdown
                scoreTrend={realTrend}
                outcomeBreakdown={realBreakdown}
                telemetry={realTelemetry}
              />
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
                <div className="lg:col-span-7 h-full">
                  <EvalItemsTable
                    items={realItems}
                    selectedItemId={selectedItemId}
                    onSelectItem={(item: EvalItem) => setSelectedItemId(item.id)}
                  />
                </div>
                <div className="lg:col-span-5 h-full">
                  <div className="p-6 rounded-lg bg-surface-container-lowest border border-outline-variant/30 text-center font-mono text-xs text-outline">
                    Select a failed item from the criteria table to inspect trace details.
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* =========================================================================
          ISOLATED PREVIEW MODE (Stitch Reference Fixtures)
          ========================================================================= */}
      {dataMode === 'preview' && (
        <>
          {/* Header with Preview Inspect Switcher */}
          <EvalHeader
            summary={SAMPLE_EVAL_SUMMARY}
            inspectMode={previewSubMode}
            onSelectInspectMode={setPreviewSubMode}
          />

          {/* Running notice banner if in running mode */}
          {previewSubMode === 'running' && (
            <div className="p-3 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-between font-mono text-xs text-primary animate-pulse">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary" />
                <span>Test Runner Agent currently executing suite: SWE-bench / Ruby Minitest Regression v2.4...</span>
              </div>
              <span>42% complete</span>
            </div>
          )}

          {/* 5 Summary Metric Cards */}
          <EvalSummaryCards
            summary={SAMPLE_EVAL_SUMMARY}
            isAllPassed={previewSubMode === 'passed'}
          />

          {/* Middle Panels: Score Trend, Outcome Breakdown, Resource Telemetry */}
          <EvalTrendsAndBreakdown
            scoreTrend={SAMPLE_SCORE_TREND}
            outcomeBreakdown={
              previewSubMode === 'passed'
                ? {
                    ...SAMPLE_OUTCOME_BREAKDOWN,
                    passed: 15,
                    failed: 0,
                    skipped: 0,
                    categories: SAMPLE_OUTCOME_BREAKDOWN.categories.map((c) => ({
                      ...c,
                      passed: c.total,
                      failed: 0,
                    })),
                  }
                : SAMPLE_OUTCOME_BREAKDOWN
            }
            telemetry={SAMPLE_RESOURCE_TELEMETRY}
          />

          {/* Bottom 2-Column Split: Criteria Table (7 cols) & Failure Inspector (5 cols) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            {/* Criteria Table */}
            <div className="lg:col-span-7 h-full">
              <EvalItemsTable
                items={
                  previewSubMode === 'passed'
                    ? SAMPLE_EVAL_ITEMS.map((item) => ({
                        ...item,
                        status: 'PASSED' as const,
                        score: 1.0,
                        errorMessage: undefined,
                      }))
                    : SAMPLE_EVAL_ITEMS
                }
                selectedItemId={selectedItemId}
                onSelectItem={(item: EvalItem) => setSelectedItemId(item.id)}
              />
            </div>

            {/* Failure Inspector */}
            <div className="lg:col-span-5 h-full">
              {previewSubMode === 'passed' ? (
                <div className="p-6 rounded-lg bg-surface-container-lowest border border-emerald-500/30 flex flex-col items-center justify-center text-center h-full min-h-[420px]">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mb-3 text-xl font-bold">
                    ✔
                  </div>
                  <h3 className="text-base font-bold text-on-surface mb-1">
                    All Tests &amp; Invariants Passed
                  </h3>
                  <p className="text-xs text-outline font-mono max-w-sm mb-4">
                    Zero test failures detected. The current diff satisfies all 15 benchmark criteria with 100% determinism.
                  </p>
                  {onNavigateToDiff && (
                    <button
                      type="button"
                      onClick={onNavigateToDiff}
                      className="px-4 py-2 rounded bg-primary text-on-primary text-xs font-semibold hover:bg-primary/90 transition-colors"
                    >
                      Review Diff &amp; PR Draft
                    </button>
                  )}
                </div>
              ) : (
                <FailureInspector
                  failure={SAMPLE_FAILURE_DETAILS}
                  onNavigateToDiff={onNavigateToDiff}
                  onExportJson={handleExportJson}
                  onPromptAgentToFix={() => {
                    alert('Prompt sent to Debugger Agent to synthesize patch for test_multibyte_utf8_boundary.');
                  }}
                />
              )}
            </div>
          </div>
        </>
      )}

      {/* Bottom Context Window Telemetry Pill */}
      <div className="fixed bottom-4 left-72 z-20 hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high/90 border border-outline-variant/40 text-[11px] font-mono text-outline shadow-lg backdrop-blur-sm">
        <span className="text-on-surface font-semibold">Context Window</span>
        <div className="w-16 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
          <div className="h-full bg-primary" style={{ width: '42%' }} />
        </div>
        <span>42% (54k/128k)</span>
      </div>
    </div>
  );
};
