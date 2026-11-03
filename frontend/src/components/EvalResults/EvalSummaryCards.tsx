import React from 'react';
import type { EvaluationSummary } from './evalResultsUtils';

interface EvalSummaryCardsProps {
  summary: EvaluationSummary;
  isAllPassed?: boolean;
}

export const EvalSummaryCards: React.FC<EvalSummaryCardsProps> = ({
  summary,
  isAllPassed = false,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      {/* 1. Evaluation Status */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">EVALUATION STATUS</span>
          <span className="px-1.5 py-0.2 rounded bg-surface-container-high text-outline text-[10px]">
            {isAllPassed ? 'Stage 8 Complete' : 'Stage 6 Halted'}
          </span>
        </div>

        <div className="my-1">
          <span
            className={`text-xl font-bold font-mono ${
              isAllPassed ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            {isAllPassed ? 'PASSED (15/15)' : summary.statusBadge}
          </span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant truncate mb-1">
          {isAllPassed
            ? 'All criteria and regression suites satisfied'
            : 'Assertion failure in tokenize...'}
        </div>

        <div className="flex items-center gap-1.5 text-[10px] font-mono pt-1 border-t border-outline-variant/20">
          {isAllPassed ? (
            <span className="text-emerald-400 font-semibold flex items-center gap-1">
              <span>✔</span> Ready for PR Merge
            </span>
          ) : (
            <span className="text-red-400 font-semibold flex items-center gap-1">
              <span>⨂</span> Blocking Merge Gate
            </span>
          )}
        </div>
      </div>

      {/* 2. Task Success */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">TASK SUCCESS</span>
          <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold">
            {isAllPassed ? '+13.3%' : '+4.2%'}
          </span>
        </div>

        <div className="my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {isAllPassed ? '100.0%' : `${summary.taskSuccessPercentage}%`}
          </span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant mb-1">
          {isAllPassed
            ? '15 of 15 criteria satisfied'
            : `${summary.criteriaSatisfiedCount} of ${summary.criteriaTotalCount} criteria satisfied`}
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden pt-0.5">
          <div
            className="h-full bg-emerald-400 transition-all"
            style={{ width: `${isAllPassed ? 100 : summary.taskSuccessPercentage}%` }}
          />
        </div>
      </div>

      {/* 3. Test Pass Rate */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">TEST PASS RATE</span>
          <span className="text-[10px] font-mono text-outline">
            {summary.totalTests} Total
          </span>
        </div>

        <div className="my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {isAllPassed ? '100.0%' : `${summary.testPassPercentage.toFixed(1)}%`}
          </span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant mb-1 flex items-center gap-1.5 flex-wrap">
          <span className="text-emerald-400 font-semibold">
            {isAllPassed ? 15 : summary.passedCount} Passed
          </span>
          <span>•</span>
          <span className={isAllPassed ? 'text-outline' : 'text-red-400 font-semibold'}>
            {isAllPassed ? 0 : summary.failedCount} Failed
          </span>
          <span>•</span>
          <span className="text-outline">
            {isAllPassed ? 0 : summary.skippedCount} Skip
          </span>
        </div>

        {/* Segmented bar */}
        <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden flex pt-0.5">
          <div
            className="h-full bg-emerald-400"
            style={{ width: `${isAllPassed ? 100 : (summary.passedCount / summary.totalTests) * 100}%` }}
          />
          {!isAllPassed && (
            <>
              <div
                className="h-full bg-red-400"
                style={{ width: `${(summary.failedCount / summary.totalTests) * 100}%` }}
              />
              <div
                className="h-full bg-outline-variant"
                style={{ width: `${(summary.skippedCount / summary.totalTests) * 100}%` }}
              />
            </>
          )}
        </div>
      </div>

      {/* 4. Avg Latency */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">AVG LATENCY</span>
          <span className="px-1.5 py-0.2 rounded bg-primary/10 text-primary text-[10px] font-semibold">
            &lt;2.0s SLA
          </span>
        </div>

        <div className="my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {summary.avgLatencySec}s
          </span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant truncate mb-1">
          P95: {summary.p95LatencySec}s • Median: {summary.medianLatencyMs}ms
        </div>

        <div className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 pt-1 border-t border-outline-variant/20">
          <span>✔</span>
          <span>Within Target SLA</span>
        </div>
      </div>

      {/* 5. Tokens & Cost */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">TOKENS &amp; COST</span>
          <span className="text-[10px] font-mono text-emerald-400 font-semibold">
            {summary.cost}
          </span>
        </div>

        <div className="my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {summary.totalTokens.toLocaleString()}
          </span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant truncate mb-1">
          {summary.cachedTokensPercentage}% cached tokens
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-outline pt-1 border-t border-outline-variant/20">
          <span>Prompt: {(summary.promptTokens / 1000).toFixed(0)}k</span>
          <span>Comp: {(summary.completionTokens / 1000).toFixed(1)}k</span>
        </div>
      </div>
    </div>
  );
};
