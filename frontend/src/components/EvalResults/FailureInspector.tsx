import React, { useState } from 'react';
import type { FailureDetails } from './evalResultsUtils';

interface FailureInspectorProps {
  failure: FailureDetails;
  onNavigateToDiff?: () => void;
  onExportJson?: () => void;
  onPromptAgentToFix?: () => void;
}

export const FailureInspector: React.FC<FailureInspectorProps> = ({
  failure,
  onNavigateToDiff,
  onExportJson,
  onPromptAgentToFix,
}) => {
  const [copiedTrace, setCopiedTrace] = useState(false);

  const handleCopyTrace = () => {
    const trace = `${failure.failureDescription}\n${failure.callStack.join('\n')}`;
    navigator.clipboard?.writeText(trace);
    setCopiedTrace(true);
    setTimeout(() => setCopiedTrace(false), 2000);
  };

  return (
    <div className="flex flex-col gap-3 p-4 bg-surface-container-lowest border border-outline-variant/30 rounded-lg h-full">
      {/* Header: Title + Severity Badges */}
      <div className="flex items-center justify-between gap-2 border-b border-outline-variant/20 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-red-400 font-bold">⨂</span>
          <span className="text-xs font-mono font-bold text-on-surface">
            Failure Inspector
          </span>
        </div>

        <div className="flex items-center gap-1.5 font-mono text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-outline border border-outline-variant/30">
            Exit 1
          </span>
          <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30 font-semibold">
            High Severity
          </span>
        </div>
      </div>

      {/* Failure Symbol & Description */}
      <div className="flex flex-col gap-1 font-mono">
        <span className="text-xs font-bold text-red-400">
          {failure.testSymbol}
        </span>
        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          {failure.failureDescription}
        </p>
      </div>

      {/* Test File Location & Copy Trace */}
      <div className="flex items-center justify-between text-[11px] font-mono text-outline pt-1 border-t border-outline-variant/20">
        <span className="text-primary truncate">
          📄 {failure.testFilePath}:{failure.lineNumber}
        </span>
        <button
          type="button"
          onClick={handleCopyTrace}
          className="text-[10px] text-outline hover:text-on-surface transition-colors shrink-0"
        >
          {copiedTrace ? '✓ Copied' : '❐ Copy Trace'}
        </button>
      </div>

      {/* Diff snippet */}
      <div className="p-2.5 rounded bg-surface-container-low/60 border border-outline-variant/20 font-mono text-[11px]">
        <div className="text-[10px] text-outline uppercase tracking-wider mb-1 font-semibold">
          Diff:
        </div>
        <div className="space-y-0.5">
          {failure.diffSnippet.removed.map((line, idx) => (
            <div key={`rm_${idx}`} className="text-emerald-400 bg-emerald-500/10 px-1 py-0.5 rounded">
              <code>{line}</code>
            </div>
          ))}
          {failure.diffSnippet.added.map((line, idx) => (
            <div key={`add_${idx}`} className="text-red-400 bg-red-500/10 px-1 py-0.5 rounded">
              <code>{line}</code>
            </div>
          ))}
        </div>
      </div>

      {/* Call Stack */}
      <div className="flex flex-col gap-1 font-mono text-[11px]">
        <div className="text-[10px] text-outline uppercase tracking-wider font-semibold">
          Call Stack:
        </div>
        <div className="p-2 rounded bg-surface-container-low/40 border border-outline-variant/20 space-y-1 text-on-surface-variant text-[10px] overflow-x-auto max-h-48">
          {failure.callStack.map((frame, idx) => (
            <div key={idx} className="whitespace-pre font-mono">
              {frame}
            </div>
          ))}
        </div>
      </div>

      {/* Target Source File & Cross-Navigation to Diff Viewer */}
      <div className="p-2.5 rounded bg-surface-container-low/50 border border-outline-variant/30 flex items-center justify-between gap-2 font-mono text-xs">
        <div className="flex flex-col min-w-0">
          <span className="text-on-surface font-semibold truncate">
            {failure.sourceFile}
          </span>
          <span className="text-[10px] text-outline truncate">
            Ragel / Multi-byte State Machine
          </span>
        </div>

        {onNavigateToDiff && (
          <button
            type="button"
            onClick={onNavigateToDiff}
            className="px-2.5 py-1 rounded bg-primary/10 border border-primary/30 text-primary text-[11px] font-semibold hover:bg-primary/20 transition-colors shrink-0 flex items-center gap-1"
          >
            <span>Diff Viewer</span>
            <span>↗</span>
          </button>
        )}
      </div>

      {/* Agent Synthesis & Next Action Box */}
      <div className="p-3 rounded-lg bg-surface-container-low border border-primary/20 flex flex-col gap-2 font-mono">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-primary">
          <span>🤖</span>
          <span>AGENT SYNTHESIS &amp; NEXT ACTION</span>
        </div>

        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          {failure.agentSynthesis.summary}
        </p>

        <div className="flex items-center justify-between text-[10px] pt-1 border-t border-outline-variant/20 flex-wrap gap-1">
          <span className="px-1.5 py-0.5 rounded bg-primary text-on-primary font-semibold">
            Patch fix available
          </span>
          <span className="text-emerald-400 font-medium">
            Confidence: {failure.agentSynthesis.confidencePercentage}%
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2 pt-2 border-t border-outline-variant/20 flex-wrap font-mono text-xs">
        <button
          type="button"
          onClick={onExportJson}
          className="px-3 py-1.5 rounded bg-surface-container-high border border-outline-variant/40 text-on-surface hover:bg-surface-container-highest transition-colors text-[11px] flex items-center gap-1"
        >
          <span>↓</span>
          <span>Export JSON</span>
        </button>

        <button
          type="button"
          className="px-3 py-1.5 rounded bg-surface-container-high border border-outline-variant/40 text-on-surface hover:bg-surface-container-highest transition-colors text-[11px] flex items-center gap-1"
        >
          <span>▷</span>
          <span>Sandbox Preview</span>
        </button>

        <button
          type="button"
          onClick={onPromptAgentToFix}
          className="flex-1 px-3 py-1.5 rounded bg-primary text-on-primary hover:bg-primary/90 transition-colors text-[11px] font-semibold text-center flex items-center justify-center gap-1"
        >
          <span>⚡</span>
          <span>Prompt Agent to Fix</span>
        </button>
      </div>
    </div>
  );
};
