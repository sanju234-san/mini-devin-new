import React from 'react';
import type {
  ScoreTrendPoint,
  OutcomeBreakdownData,
  ResourceTelemetryData,
} from './evalResultsUtils';

interface EvalTrendsAndBreakdownProps {
  scoreTrend: ScoreTrendPoint[];
  outcomeBreakdown: OutcomeBreakdownData;
  telemetry: ResourceTelemetryData;
}

export const EvalTrendsAndBreakdown: React.FC<EvalTrendsAndBreakdownProps> = ({
  scoreTrend,
  outcomeBreakdown,
  telemetry,
}) => {
  // SVG Chart Dimensions
  const chartWidth = 360;
  const chartHeight = 120;
  const paddingX = 30;
  const paddingY = 20;

  // Calculate coordinates for Score Trend line
  const minScore = 60;
  const maxScore = 100;

  const points = scoreTrend.map((pt, idx) => {
    const x =
      paddingX + (idx / (scoreTrend.length - 1)) * (chartWidth - paddingX * 2);
    const y =
      chartHeight -
      paddingY -
      ((pt.score - minScore) / (maxScore - minScore)) * (chartHeight - paddingY * 2);
    return { ...pt, x, y };
  });

  const linePath = points.reduce((acc, pt, idx) => {
    return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
  }, '');

  const areaPath = `${linePath} L ${points[points.length - 1].x} ${
    chartHeight - 10
  } L ${points[0].x} ${chartHeight - 10} Z`;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {/* 1. Score Trend Panel */}
      <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs font-mono text-outline mb-1">
          <div className="flex items-center gap-1.5 font-bold text-on-surface">
            <span>📈</span>
            <span>Score Trend</span>
          </div>
          <span className="text-[10px]">Last 8 Runs</span>
        </div>

        {/* Pure SVG Line Chart */}
        <div className="w-full my-1 relative">
          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            className="w-full h-28 overflow-visible"
          >
            <defs>
              <linearGradient id="scoreAreaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Grid line */}
            <line
              x1={paddingX}
              y1={chartHeight - 10}
              x2={chartWidth - paddingX}
              y2={chartHeight - 10}
              stroke="currentColor"
              className="text-outline-variant/20"
              strokeDasharray="2 2"
            />

            {/* Shaded Area */}
            <path d={areaPath} fill="url(#scoreAreaGradient)" />

            {/* Trend Line */}
            <path
              d={linePath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Points */}
            {points.map((pt) => (
              <g key={pt.runId}>
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={pt.isCurrent ? 4 : 2.5}
                  className={
                    pt.isCurrent
                      ? 'fill-primary stroke-white stroke-2'
                      : 'fill-[#38bdf8]'
                  }
                />
                {pt.isCurrent && (
                  <text
                    x={pt.x}
                    y={pt.y - 8}
                    textAnchor="middle"
                    className="text-[9px] font-mono font-bold fill-primary"
                  >
                    86.7% Curr
                  </text>
                )}
              </g>
            ))}
          </svg>
        </div>

        {/* Labels under the points */}
        <div className="flex items-center justify-between text-[9px] font-mono text-outline px-1">
          {scoreTrend.map((pt) => (
            <span
              key={pt.runId}
              className={pt.isCurrent ? 'text-primary font-bold' : ''}
            >
              {pt.label}
            </span>
          ))}
        </div>
      </div>

      {/* 2. Outcome Breakdown Panel */}
      <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs font-mono text-outline mb-1">
          <div className="flex items-center gap-1.5 font-bold text-on-surface">
            <span>⨁</span>
            <span>Outcome Breakdown</span>
          </div>
          <span className="text-[10px]">{outcomeBreakdown.total} Total</span>
        </div>

        {/* Segmented Top Bar */}
        <div className="w-full h-2 rounded-full bg-surface-container-highest overflow-hidden flex my-2">
          <div
            className="h-full bg-emerald-400"
            style={{
              width: `${(outcomeBreakdown.passed / outcomeBreakdown.total) * 100}%`,
            }}
            title={`Passed: ${outcomeBreakdown.passed}`}
          />
          <div
            className="h-full bg-red-400"
            style={{
              width: `${(outcomeBreakdown.failed / outcomeBreakdown.total) * 100}%`,
            }}
            title={`Failed: ${outcomeBreakdown.failed}`}
          />
          <div
            className="h-full bg-outline-variant"
            style={{
              width: `${(outcomeBreakdown.skipped / outcomeBreakdown.total) * 100}%`,
            }}
            title={`Skipped: ${outcomeBreakdown.skipped}`}
          />
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between text-[10px] font-mono mb-2">
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            {outcomeBreakdown.passed} Passed (80.0%)
          </span>
          <span className="text-red-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            {outcomeBreakdown.failed} Failed (13.3%)
          </span>
          <span className="text-outline flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant" />
            {outcomeBreakdown.skipped} Skip (6.7%)
          </span>
        </div>

        {/* Subcategories Breakdown List */}
        <div className="space-y-1.5 text-[11px] font-mono pt-1 border-t border-outline-variant/20">
          {outcomeBreakdown.categories.map((cat) => (
            <div key={cat.name} className="flex items-center justify-between">
              <span className="text-on-surface-variant truncate mr-2">
                {cat.name}
              </span>
              <span
                className={`font-semibold shrink-0 ${
                  cat.failed
                    ? 'text-red-400'
                    : cat.skipped
                    ? 'text-outline'
                    : 'text-emerald-400'
                }`}
              >
                {cat.skipped
                  ? `1 ${cat.note || 'Skipped'}`
                  : cat.failed
                  ? `${cat.passed} / ${cat.total} (${cat.failed} Failed)`
                  : `${cat.passed} / ${cat.total} Passed`}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Resource Telemetry Panel */}
      <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs font-mono text-outline mb-1">
          <div className="flex items-center gap-1.5 font-bold text-on-surface">
            <span>📊</span>
            <span>Resource Telemetry</span>
          </div>
          <span className="text-emerald-400 font-semibold text-[10px]">Healthy</span>
        </div>

        <div className="space-y-2 font-mono text-[11px] my-1">
          {/* Model Latency */}
          <div>
            <div className="flex items-center justify-between text-[10px] text-outline mb-0.5">
              <span>Model Latency</span>
              <span className="text-on-surface">
                {telemetry.modelLatencySec}s / {telemetry.modelLatencyMaxSec.toFixed(2)}s
              </span>
            </div>
            <div className="w-full h-1 rounded-full bg-surface-container-highest overflow-hidden">
              <div
                className="h-full bg-primary"
                style={{
                  width: `${(telemetry.modelLatencySec / telemetry.modelLatencyMaxSec) * 100}%`,
                }}
              />
            </div>
          </div>

          {/* Memory High-Water */}
          <div>
            <div className="flex items-center justify-between text-[10px] text-outline mb-0.5">
              <span>Memory High-Water</span>
              <span className="text-on-surface">
                {telemetry.memoryMb} MB / {telemetry.memoryMaxMb} MB
              </span>
            </div>
            <div className="w-full h-1 rounded-full bg-surface-container-highest overflow-hidden">
              <div
                className="h-full bg-primary"
                style={{
                  width: `${(telemetry.memoryMb / telemetry.memoryMaxMb) * 100}%`,
                }}
              />
            </div>
          </div>

          {/* Token Budget */}
          <div>
            <div className="flex items-center justify-between text-[10px] text-outline mb-0.5">
              <span>Token Budget</span>
              <span className="text-on-surface">
                {(telemetry.tokenBudget / 1000).toFixed(1)}k / {(telemetry.tokenBudgetMax / 1000).toFixed(0)}k
              </span>
            </div>
            <div className="w-full h-1 rounded-full bg-surface-container-highest overflow-hidden">
              <div
                className="h-full bg-primary"
                style={{
                  width: `${(telemetry.tokenBudget / telemetry.tokenBudgetMax) * 100}%`,
                }}
              />
            </div>
          </div>

          {/* Cost per Benchmark */}
          <div>
            <div className="flex items-center justify-between text-[10px] text-outline mb-0.5">
              <span>Cost per Benchmark</span>
              <span className="text-on-surface">
                ${telemetry.cost.toFixed(3)} / ${telemetry.costMax.toFixed(3)}
              </span>
            </div>
            <div className="w-full h-1 rounded-full bg-surface-container-highest overflow-hidden">
              <div
                className="h-full bg-emerald-400"
                style={{
                  width: `${(telemetry.cost / telemetry.costMax) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>

        <div className="text-[10px] font-mono text-outline pt-1 border-t border-outline-variant/20 flex items-center justify-between">
          <span>v8-isolate runtime limit:</span>
          <span>{telemetry.isolateLimitSec}s</span>
        </div>
      </div>
    </div>
  );
};
