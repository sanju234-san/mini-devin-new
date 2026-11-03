import React, { useState, useMemo } from 'react';
import { useAgentRunSocket } from '../../hooks/useAgentRunSocket';
import {
  TransparencyInspectMode,
  SAMPLE_STAGES,
  SAMPLE_METRICS,
  SAMPLE_CALL_INSPECTOR,
  SAMPLE_SAFETY_GUARDRAILS,
  SAMPLE_ACTIVITY_EVENTS,
  convertEnvelopesToTransparencyEvents,
  TransparencyEvent,
} from './transparencyUtils';
import { TransparencyHeader } from './TransparencyHeader';
import { AgentWorkflowPipeline } from './AgentWorkflowPipeline';
import { ModelMetricsStrip } from './ModelMetricsStrip';
import { AgentActivityFeed } from './AgentActivityFeed';
import { ModelCallInspector } from './ModelCallInspector';

interface TransparencyDashboardProps {
  runId?: string;
}

export const TransparencyDashboard: React.FC<TransparencyDashboardProps> = ({
  runId = 'run-8924a',
}) => {
  const [inspectMode, setInspectMode] = useState<TransparencyInspectMode>('completed');
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>('evt_tr_01');
  const [selectedStageId, setSelectedStageId] = useState<string | undefined>('test_runner');

  // Single WebSocket connection hook
  const {
    events: liveEnvelopes,
    connectionState,
    connect,
  } = useAgentRunSocket(runId, {
    autoConnect: inspectMode === 'live',
  });

  // Convert live envelopes to transparency events when in live mode
  const liveEvents = useMemo(() => {
    return convertEnvelopesToTransparencyEvents(liveEnvelopes);
  }, [liveEnvelopes]);

  // Determine current active events and telemetry
  const displayEvents: TransparencyEvent[] = useMemo(() => {
    if (inspectMode === 'completed') {
      return SAMPLE_ACTIVITY_EVENTS;
    }
    if (inspectMode === 'live') {
      return liveEvents;
    }
    return [];
  }, [inspectMode, liveEvents]);

  // Selected event
  const currentSelectedEvent = useMemo(() => {
    return displayEvents.find((e) => e.id === selectedEventId) || displayEvents[0];
  }, [displayEvents, selectedEventId]);

  // Export audit trace
  const handleExportAuditJson = () => {
    const dataToExport = {
      runId,
      exportedAt: new Date().toISOString(),
      inspectMode,
      metrics: SAMPLE_METRICS,
      stages: SAMPLE_STAGES,
      events: displayEvents,
      activeCall: SAMPLE_CALL_INSPECTOR,
      guardrails: SAMPLE_SAFETY_GUARDRAILS,
    };
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mini-devin-transparency-audit-${runId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Copy trace
  const handleCopyTrace = () => {
    const traceSummary = JSON.stringify(displayEvents, null, 2);
    navigator.clipboard?.writeText(traceSummary);
  };

  return (
    <div className="flex flex-col gap-space-lg p-space-md sm:p-space-lg w-full max-w-[1600px] mx-auto text-on-surface">
      {/* 1. Header with Metadata, Inspect Switcher & Controls */}
      <TransparencyHeader
        runId={runId}
        inspectMode={inspectMode}
        onSelectInspectMode={setInspectMode}
        isStreaming={isStreaming}
        onToggleStreaming={() => setIsStreaming(!isStreaming)}
        activeStageNumber={6}
        totalStages={8}
        totalTokens={SAMPLE_METRICS.tokenIngestion.total}
        cost="$0.042"
        modelsSummary="Claude 3.5 Sonnet + GPT-4o"
        repo="octocat/linguist"
        issue="#482: UTF-8 multibyte parser bug"
        branch="fix/parser-multibyte"
      />

      {/* Illustrative Preview Notice when in Completed Demo Mode */}
      {inspectMode === 'completed' && (
        <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs font-mono text-amber-200">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>
              <strong>ILLUSTRATIVE PREVIEW MODE</strong> — Displaying verified offline sample audit trace. Real WebSocket stream is not engaged.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setInspectMode('live')}
            className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest text-primary text-[11px] border border-outline-variant/30 transition-colors"
          >
            Switch to Live Mode
          </button>
        </div>
      )}

      {/* Honest Live Stream Waiting State */}
      {inspectMode === 'live' && liveEvents.length === 0 && (
        <div className="p-space-md rounded-lg bg-surface-container-low border border-outline-variant/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono text-outline">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span>
              <strong>Live Stream Subscribed ({connectionState})</strong> — Awaiting real-time agent step events from `/ws/runs/{runId}`.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setInspectMode('completed')}
            className="text-primary hover:underline text-[11px] shrink-0"
          >
            Inspect Sample Completed Trace →
          </button>
        </div>
      )}

      {/* DISCONNECTED STATE VIEW */}
      {inspectMode === 'disconnected' && (
        <div className="flex flex-col items-center justify-center p-12 my-6 bg-surface-container-lowest border border-red-500/30 rounded-xl text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mb-3">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
              <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
              <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
              <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
              <line x1="12" y1="20" x2="12.01" y2="20" />
            </svg>
          </div>
          <h2 className="text-base font-bold text-on-surface mb-1">
            Backend WebSocket Disconnected
          </h2>
          <p className="text-xs text-outline max-w-md mb-4 font-mono">
            Live agent transparency stream is currently offline. Status: {connectionState}.
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={connect}
              className="px-4 py-1.5 rounded bg-primary text-on-primary text-xs font-semibold hover:bg-primary/90 transition-colors"
            >
              Retry Connection
            </button>
            <button
              type="button"
              onClick={() => setInspectMode('completed')}
              className="px-4 py-1.5 rounded bg-surface-container-high border border-outline-variant/40 text-on-surface text-xs font-medium hover:bg-surface-container-highest transition-colors"
            >
              View Completed State
            </button>
          </div>
        </div>
      )}

      {/* EMPTY STATE VIEW */}
      {inspectMode === 'empty' && (
        <div className="flex flex-col items-center justify-center p-12 my-6 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-center">
          <div className="w-12 h-12 rounded-full bg-surface-container-high border border-outline-variant/40 text-outline flex items-center justify-center mb-3">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-base font-bold text-on-surface mb-1">
            No Model Telemetry or Agent Events
          </h2>
          <p className="text-xs text-outline max-w-md mb-4 font-mono">
            No agent steps, tool calls, or model invocations have been recorded for run #{runId}.
          </p>
          <button
            type="button"
            onClick={() => setInspectMode('completed')}
            className="px-4 py-1.5 rounded bg-surface-container-high border border-outline-variant/40 text-primary text-xs font-semibold hover:bg-surface-container-highest transition-colors"
          >
            Load Sample Completed Trace
          </button>
        </div>
      )}

      {/* ACTIVE / COMPLETED / LIVE MAIN DASHBOARD */}
      {(inspectMode === 'completed' || inspectMode === 'live') && (
        <>
          {/* 2. 8-Stage Agent Workflow Pipeline Strip */}
          <AgentWorkflowPipeline
            stages={SAMPLE_STAGES}
            activeStageId={selectedStageId}
            onSelectStage={setSelectedStageId}
          />

          {/* 3. 4 Summary Metric Cards */}
          <ModelMetricsStrip metrics={SAMPLE_METRICS} />

          {/* 4. 2-Column Split Layout: Left Activity Feed & Right Call Inspector */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            {/* Left Column: Activity Feed (7 cols) */}
            <div className="lg:col-span-7 h-full">
              <AgentActivityFeed
                events={displayEvents}
                selectedEventId={selectedEventId}
                onSelectEvent={(evt) => setSelectedEventId(evt.id)}
                onExportAuditJson={handleExportAuditJson}
                onCopyTrace={handleCopyTrace}
              />
            </div>

            {/* Right Column: Model Call Inspector & Safety Guardrails (5 cols) */}
            <div className="lg:col-span-5 flex flex-col gap-3">
              <ModelCallInspector
                callData={{
                  ...SAMPLE_CALL_INSPECTOR,
                  modelId: currentSelectedEvent?.model || SAMPLE_CALL_INSPECTOR.modelId,
                }}
                guardrailsData={SAMPLE_SAFETY_GUARDRAILS}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};
