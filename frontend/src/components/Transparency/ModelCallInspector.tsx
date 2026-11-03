import React from 'react';
import type { CallInspectorData, SafetyGuardrailsData } from './transparencyUtils';

interface ModelCallInspectorProps {
  callData: CallInspectorData;
  guardrailsData: SafetyGuardrailsData;
}

export const ModelCallInspector: React.FC<ModelCallInspectorProps> = ({
  callData,
  guardrailsData,
}) => {
  return (
    <div className="flex flex-col gap-3">
      {/* 1. Call Inspector Box */}
      <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col gap-3">
        {/* Header: Title + Status */}
        <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 pb-2">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
            <span className="text-xs font-mono font-bold text-on-surface">
              Call Inspector: {callData.callId}
            </span>
          </div>

          <span
            className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold tracking-wider uppercase border ${
              callData.status === 'SUCCESS'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-red-500/10 text-red-400 border-red-500/30'
            }`}
          >
            {callData.status}
          </span>
        </div>

        {/* Model Meta Parameters */}
        <div className="grid grid-cols-1 gap-1.5 text-[11px] font-mono">
          <div className="flex items-center justify-between">
            <span className="text-outline">Model ID:</span>
            <span className="text-primary font-medium">{callData.modelId}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Parameters:</span>
            <span className="text-on-surface-variant">
              temperature: {callData.parameters.temperature.toFixed(2)} • top_p:{' '}
              {callData.parameters.top_p.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Stop Reason:</span>
            <span className="text-on-surface-variant">{callData.stopReason}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">System Prompt SHA:</span>
            <span className="text-outline-variant">{callData.systemPromptSha}</span>
          </div>
        </div>

        {/* Token Accounting Grid */}
        <div className="p-2.5 rounded bg-surface-container-low/50 border border-outline-variant/30 flex flex-col gap-2">
          <div className="flex items-center justify-between text-[10px] font-mono">
            <span className="uppercase text-outline font-semibold tracking-wider">
              TOKEN ACCOUNTING
            </span>
            <span className="text-emerald-400 font-semibold">
              {callData.tokenAccounting.savedViaCache}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center font-mono">
            <div className="p-1.5 rounded bg-surface-container-high/60 border border-outline-variant/20">
              <div className="text-[10px] text-outline">Input Tokens</div>
              <div className="text-xs font-bold text-on-surface">
                {callData.tokenAccounting.inputTokens.toLocaleString()}
              </div>
            </div>
            <div className="p-1.5 rounded bg-surface-container-high/60 border border-outline-variant/20">
              <div className="text-[10px] text-outline">Output Tokens</div>
              <div className="text-xs font-bold text-on-surface">
                {callData.tokenAccounting.outputTokens.toLocaleString()}
              </div>
            </div>
            <div className="p-1.5 rounded bg-surface-container-high/60 border border-outline-variant/20">
              <div className="text-[10px] text-outline">Cache Read</div>
              <div className="text-xs font-bold text-emerald-400">
                {callData.tokenAccounting.cacheReadTokens.toLocaleString()}
              </div>
            </div>
          </div>
        </div>

        {/* Emitted Tool Invocations */}
        <div className="flex flex-col gap-1.5 font-mono text-[11px]">
          <div className="text-[10px] text-outline font-semibold uppercase tracking-wider">
            EMITTED TOOL INVOCATIONS ({callData.emittedTools.length})
          </div>
          <div className="space-y-1">
            {callData.emittedTools.map((tool) => (
              <div
                key={tool.name}
                className="flex items-center justify-between p-1.5 rounded bg-surface-container-lowest border border-outline-variant/20"
              >
                <span className="text-on-surface text-xs font-medium">
                  {tool.name}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    tool.status === 'Executed'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-surface-container-high text-outline'
                  }`}
                >
                  {tool.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* System Persona Excerpt */}
        <div className="flex flex-col gap-1 font-mono text-[10px]">
          <div className="flex items-center justify-between text-outline">
            <span>System Persona Excerpt</span>
            <span className="text-primary hover:underline cursor-pointer">View JSON</span>
          </div>
          <pre className="p-2 rounded bg-surface-container-lowest border border-outline-variant/20 text-on-surface-variant overflow-x-auto text-[10px] leading-relaxed whitespace-pre-wrap">
            {callData.systemPersonaExcerpt}
          </pre>
        </div>
      </div>

      {/* 2. Safety & Guardrails Box */}
      <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 pb-2">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="text-xs font-mono font-bold text-on-surface">
              Safety &amp; Guardrails
            </span>
          </div>

          <span className="px-2 py-0.5 rounded font-mono text-[10px] font-bold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            {guardrailsData.passedCount}/{guardrailsData.totalCount} Passed
          </span>
        </div>

        {/* Guardrail Invariants Checklist Grid */}
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
          {guardrailsData.checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center gap-1.5 p-1.5 rounded bg-surface-container-low/40 border border-outline-variant/20 text-on-surface"
            >
              <span className="text-emerald-400 font-bold">✔</span>
              <span className="truncate">{check.name}</span>
            </div>
          ))}
        </div>

        {/* Hallucination Risk Score */}
        <div className="flex items-center justify-between p-2 rounded bg-surface-container-low/40 border border-outline-variant/20 text-xs font-mono">
          <div className="flex flex-col">
            <span className="text-[10px] text-outline uppercase tracking-wider font-semibold">
              HALLUCINATION RISK
            </span>
            <span className="font-bold text-emerald-400 text-sm">
              {guardrailsData.hallucinationRisk.score}{' '}
              <span className="text-xs font-normal">
                ({guardrailsData.hallucinationRisk.label})
              </span>
            </span>
          </div>

          {/* Mini sparkline visualization */}
          <div className="flex items-end gap-1 h-6">
            <span className="w-1.5 h-2 rounded bg-emerald-500/40" />
            <span className="w-1.5 h-3 rounded bg-emerald-500/50" />
            <span className="w-1.5 h-1.5 rounded bg-emerald-500/60" />
            <span className="w-1.5 h-2 rounded bg-emerald-400" />
          </div>
        </div>

        {/* Agent Scratchpad Variables */}
        <div className="flex flex-col gap-1.5 font-mono text-[11px]">
          <div className="flex items-center justify-between text-[10px] text-outline font-semibold uppercase tracking-wider">
            <span>AGENT SCRATCHPAD VARIABLES</span>
            <span>{guardrailsData.scratchpadVariables.length} ITEMS</span>
          </div>

          <div className="space-y-1">
            {guardrailsData.scratchpadVariables.map((variable) => (
              <div
                key={variable.key}
                className="flex items-center justify-between p-1.5 rounded bg-surface-container-lowest border border-outline-variant/20 text-[10px]"
              >
                <span className="text-primary font-medium">{variable.key}</span>
                <span className="text-on-surface-variant font-mono">
                  {variable.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
