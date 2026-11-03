import React from 'react';
import type { ModelMetrics } from './transparencyUtils';

interface ModelMetricsStripProps {
  metrics: ModelMetrics;
}

export const ModelMetricsStrip: React.FC<ModelMetricsStripProps> = ({ metrics }) => {
  const { tokenIngestion, invocations, contextWindow, reasoning } = metrics;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {/* 1. Token Ingestion */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">TOKEN INGESTION</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold text-[10px]">
            {tokenIngestion.cachePercentage}% Cache
          </span>
        </div>

        <div className="flex items-baseline gap-1.5 my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {tokenIngestion.total.toLocaleString()}
          </span>
          <span className="text-xs text-outline font-normal">tokens</span>
        </div>

        {/* Progress bar: prompt vs completion */}
        <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden flex my-1.5">
          <div
            className="h-full bg-primary"
            style={{
              width: `${(tokenIngestion.prompt / tokenIngestion.total) * 100}%`,
            }}
            title={`Prompt: ${(tokenIngestion.prompt / 1000).toFixed(1)}k`}
          />
          <div
            className="h-full bg-tertiary"
            style={{
              width: `${(tokenIngestion.completion / tokenIngestion.total) * 100}%`,
            }}
            title={`Completion: ${(tokenIngestion.completion / 1000).toFixed(1)}k`}
          />
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-outline">
          <span>Prompt: {(tokenIngestion.prompt / 1000).toFixed(1)}k</span>
          <span>Completion: {(tokenIngestion.completion / 1000).toFixed(1)}k</span>
        </div>
      </div>

      {/* 2. Model Invocations */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">MODEL INVOCATIONS</span>
          <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-semibold text-[10px]">
            {invocations.slaPercentage}% SLA
          </span>
        </div>

        <div className="flex items-baseline gap-1.5 my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {invocations.total}
          </span>
          <span className="text-xs text-outline font-normal">API calls</span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant flex items-center justify-between my-1">
          <span>Avg Latency: {invocations.avgLatencyMs.toLocaleString()}ms</span>
          <span className="text-emerald-400 font-semibold">{invocations.failures} failures</span>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-outline">
          <span>P95: {invocations.p95Ms.toLocaleString()}ms</span>
          <span className="truncate">Sonnet 3.5: 8 calls</span>
        </div>
      </div>

      {/* 3. Context Window Saturation */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">CONTEXT WINDOW</span>
          <span className="text-[10px] text-outline font-mono">
            {(contextWindow.maxTokens / 1000).toFixed(0)}k max
          </span>
        </div>

        <div className="flex items-baseline gap-1.5 my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {contextWindow.saturationPercentage}%
          </span>
          <span className="text-xs text-outline font-mono">
            ({(contextWindow.currentTokens / 1000).toFixed(1)}k tk)
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-surface-container-highest overflow-hidden my-1.5">
          <div
            className={`h-full transition-all ${
              contextWindow.saturationPercentage > 80
                ? 'bg-amber-400'
                : 'bg-primary'
            }`}
            style={{ width: `${contextWindow.saturationPercentage}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-outline">
          <span>Frame: {(contextWindow.currentTokens / 1000).toFixed(1)}k</span>
          <span>Headroom: {(contextWindow.headroomTokens / 1000).toFixed(1)}k</span>
        </div>
      </div>

      {/* 4. Reasoning & Branches */}
      <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between">
        <div className="flex items-center justify-between text-[11px] font-mono text-outline mb-1">
          <span className="uppercase tracking-wider font-semibold">REASONING &amp; BRANCHES</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold text-[10px]">
            {reasoning.confidencePercentage}% Conf
          </span>
        </div>

        <div className="flex items-baseline gap-1.5 my-1">
          <span className="text-xl font-bold font-mono text-on-surface">
            {reasoning.decisionsCount}
          </span>
          <span className="text-xs text-outline font-normal">decisions logged</span>
        </div>

        <div className="text-[11px] font-mono text-on-surface-variant flex items-center justify-between my-1">
          <span>Rollbacks: {reasoning.rollbacks}</span>
          <span>Active Tree Depth: {reasoning.treeDepth}</span>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-outline">
          <span className="text-emerald-400">
            Guardrail checks: {reasoning.guardrailsPassRate}% pass
          </span>
        </div>
      </div>
    </div>
  );
};
