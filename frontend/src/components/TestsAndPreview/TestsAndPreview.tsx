'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { useAgentRunSocket, getWebSocketUri } from '../../hooks/useAgentRunSocket';
import { SandboxMetaHeader } from './SandboxMetaHeader';
import { TestSummaryBanner } from './TestSummaryBanner';
import { ExecutionLogControls } from './ExecutionLogControls';
import { TerminalOutput } from './TerminalOutput';
import { TestResultsPanel } from './TestResultsPanel';
import {
  type PreviewState,
  type LogFilterCategory,
  type LogLine,
  RUNNING_LOGS,
  PASSED_LOGS,
  FAILED_LOGS,
  RUNNING_TEST_CASES,
  PASSED_TEST_CASES,
  FAILED_TEST_CASES,
  RUNNING_SUMMARY,
  PASSED_SUMMARY,
  FAILED_SUMMARY,
  OFFLINE_SUMMARY,
} from './testsAndPreviewUtils';

interface TestsAndPreviewProps {
  runId?: string;
  onNavigateToDiff?: (targetFile?: string) => void;
}

export const TestsAndPreview: React.FC<TestsAndPreviewProps> = ({
  runId = 'run-8924a',
  onNavigateToDiff,
}) => {
  // Mode toggle: Live Hook vs Preview State
  const [isLiveStream, setIsLiveStream] = useState(false);
  const [activePreviewState, setActivePreviewState] = useState<PreviewState>('running');

  // Controls state
  const [activeCategory, setActiveCategory] = useState<LogFilterCategory>('all');
  const [filterText, setFilterText] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [clearedBuffer, setClearedBuffer] = useState(false);

  // Consume Task 3 WebSocket Client hook
  const {
    connectionState,
    events: liveEvents,
    telemetry,
    clearBuffer: clearSocketBuffer,
    error: socketError,
  } = useAgentRunSocket(runId, {
    autoConnect: true,
    bufferCap: 500,
  });

  const targetUri = getWebSocketUri(runId);

  // Derive active summary, test cases, and logs based on mode
  const currentSummary = useMemo(() => {
    if (isLiveStream) {
      if (connectionState === 'DISCONNECTED') return OFFLINE_SUMMARY;
      return {
        ...RUNNING_SUMMARY,
        status: (connectionState === 'CONNECTED' ? 'RUNNING' : 'OFFLINE') as 'RUNNING' | 'OFFLINE',
        executedTests: liveEvents.length,
      };
    }

    switch (activePreviewState) {
      case 'passed':
        return PASSED_SUMMARY;
      case 'failed':
        return FAILED_SUMMARY;
      case 'offline':
        return OFFLINE_SUMMARY;
      case 'skeleton':
        return RUNNING_SUMMARY;
      case 'running':
      default:
        return RUNNING_SUMMARY;
    }
  }, [isLiveStream, connectionState, liveEvents.length, activePreviewState]);

  const currentTestCases = useMemo(() => {
    if (isLiveStream) {
      // In live stream mode, real test results schema is currently a contract gap
      return RUNNING_TEST_CASES;
    }

    switch (activePreviewState) {
      case 'passed':
        return PASSED_TEST_CASES;
      case 'failed':
        return FAILED_TEST_CASES;
      case 'offline':
        return [];
      case 'skeleton':
        return RUNNING_TEST_CASES;
      case 'running':
      default:
        return RUNNING_TEST_CASES;
    }
  }, [isLiveStream, activePreviewState]);

  const baseLogs: LogLine[] = useMemo(() => {
    if (isLiveStream) {
      // Map live WebSocket events into readable terminal log lines
      if (liveEvents.length === 0) {
        return [
          {
            id: 'ws-init',
            timestamp: new Date().toLocaleTimeString(),
            tag: 'info',
            category: 'stdout',
            content: `Connected to ${targetUri}. Awaiting sandbox execution stream...`,
          },
        ];
      }

      return liveEvents.map((evt, idx) => {
        const time = evt.timestamp
          ? new Date(evt.timestamp).toLocaleTimeString()
          : new Date().toLocaleTimeString();
        const tag =
          evt.eventType === 'failed'
            ? 'fail'
            : evt.eventType === 'completed'
            ? 'pass'
            : evt.eventType === 'tool_call'
            ? 'test'
            : 'info';

        return {
          id: evt.id || `evt-${idx}`,
          timestamp: time,
          tag,
          category: tag === 'fail' ? 'stderr' : tag === 'test' ? 'test_runner' : 'stdout',
          content: `${evt.agent ? `[${evt.agent}] ` : ''}${
            evt.tool ? `tool: ${evt.tool} - ` : ''
          }${JSON.stringify(evt.payload || evt.raw || '')}`,
        };
      });
    }

    switch (activePreviewState) {
      case 'passed':
        return PASSED_LOGS;
      case 'failed':
        return FAILED_LOGS;
      case 'offline':
        return [];
      case 'skeleton':
        return [];
      case 'running':
      default:
        return RUNNING_LOGS;
    }
  }, [isLiveStream, liveEvents, targetUri, activePreviewState]);

  const activeLogs = clearedBuffer ? [] : baseLogs;

  // Category counts
  const categoryCounts = useMemo(() => {
    let stdout = 0;
    let stderr = 0;
    let test_runner = 0;

    activeLogs.forEach((l) => {
      if (l.category === 'stdout') stdout++;
      if (l.category === 'stderr') stderr++;
      if (l.category === 'test_runner') test_runner++;
    });

    return {
      all: activeLogs.length,
      stdout,
      stderr,
      test_runner,
    };
  }, [activeLogs]);

  // Local clear
  const handleClear = useCallback(() => {
    setClearedBuffer(true);
    if (isLiveStream) {
      clearSocketBuffer();
    }
  }, [isLiveStream, clearSocketBuffer]);

  // Copy to clipboard
  const handleCopyLogs = useCallback(() => {
    const text = activeLogs
      .map((l) => `[${l.timestamp}] [${l.tag.toUpperCase()}] ${l.content}`)
      .join('\n');
    navigator.clipboard.writeText(text);
  }, [activeLogs]);

  // Reset clear buffer state when switching preview states or logs
  const handleSelectPreviewState = (st: PreviewState) => {
    setActivePreviewState(st);
    setClearedBuffer(false);
  };

  const isSkeleton = !isLiveStream && activePreviewState === 'skeleton';
  const isOffline =
    (!isLiveStream && activePreviewState === 'offline') ||
    (isLiveStream && connectionState === 'DISCONNECTED');

  return (
    <div className="flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto p-space-md sm:p-space-lg animate-fadeIn">
      {/* 1. Header Context & Sandbox Meta */}
      <SandboxMetaHeader runId={runId} summary={currentSummary} />

      {/* 2. Suite Status & Preview State Selector Strip */}
      <TestSummaryBanner
        summary={currentSummary}
        activePreviewState={activePreviewState}
        onSelectPreviewState={handleSelectPreviewState}
        isLiveStream={isLiveStream}
        onToggleLiveStream={() => {
          setIsLiveStream((prev) => !prev);
          setClearedBuffer(false);
        }}
      />

      {/* 3. Honest Offline / Disconnected Notice Banner */}
      {isOffline && (
        <div className="p-space-md rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-200 text-xs font-mono flex items-start gap-3">
          <svg
            className="w-5 h-5 text-amber-400 shrink-0 mt-0.5"
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
          <div className="flex flex-col gap-1">
            <span className="font-bold text-amber-300">
              Sandbox Runner Offline / WebSocket Disconnected
            </span>
            <span className="text-[11px] text-amber-200/80 leading-relaxed">
              Target endpoint: <code>{targetUri}</code> is unreachable. Ensure the backend
              FastAPI server and Docker sandbox are running. In the meantime, you can explore
              all interface states using the <strong>PREVIEW STATES</strong> buttons above.
            </span>
            {socketError && (
              <span className="text-[10px] text-amber-300/70">
                Transport error: {socketError.message}
              </span>
            )}
          </div>
        </div>
      )}

      {/* 4. Split View: Terminal Execution Logs (Left, 7 cols) + Test Results (Right, 5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-stretch">
        {/* Left Column: Terminal Output Panel */}
        <div className="lg:col-span-7 flex flex-col rounded-xl border border-outline-variant/30 overflow-hidden shadow-md bg-surface-container-low min-h-[520px]">
          <ExecutionLogControls
            activeCategory={activeCategory}
            onSelectCategory={setActiveCategory}
            categoryCounts={categoryCounts}
            filterText={filterText}
            onFilterChange={setFilterText}
            autoScroll={autoScroll}
            onToggleAutoScroll={() => setAutoScroll((prev) => !prev)}
            onClear={handleClear}
            onCopy={handleCopyLogs}
            isLive={isLiveStream ? connectionState === 'CONNECTED' : activePreviewState === 'running'}
          />

          <TerminalOutput
            logs={activeLogs}
            autoScroll={autoScroll}
            filterText={filterText}
            activeCategory={activeCategory}
            isLive={isLiveStream ? connectionState === 'CONNECTED' : activePreviewState === 'running'}
            isSkeleton={isSkeleton}
          />
        </div>

        {/* Right Column: Test Results Panel */}
        <div className="lg:col-span-5 flex flex-col min-h-[520px]">
          <TestResultsPanel
            testCases={currentTestCases}
            summary={currentSummary}
            onNavigateToDiff={onNavigateToDiff}
            isSkeleton={isSkeleton}
          />
        </div>
      </div>
    </div>
  );
};
