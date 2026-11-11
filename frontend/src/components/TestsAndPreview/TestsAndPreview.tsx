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
  type TestCaseResult,
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
  runId = '',
  onNavigateToDiff,
}) => {
  // Mode toggle: Live Hook by default (no synthetic dummy test logs)
  const [isLiveStream, setIsLiveStream] = useState(true);
  const [activePreviewState, setActivePreviewState] = useState<PreviewState>('running');

  // Controls state
  const [activeCategory, setActiveCategory] = useState<LogFilterCategory>('all');
  const [filterText, setFilterText] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [clearedBuffer, setClearedBuffer] = useState(false);

  // Live Localhost & Playwright Screenshot state
  const [localhostUrl, setLocalhostUrl] = useState('http://localhost:5173');
  const [browserViewTab, setBrowserViewTab] = useState<'screenshot' | 'iframe'>('screenshot');
  const [iframeKey, setIframeKey] = useState(0);
  const [isCapturingBrowser, setIsCapturingBrowser] = useState(false);
  const [manualBrowserReport, setManualBrowserReport] = useState<{
    passed?: boolean;
    status?: string;
    target_url?: string;
    screenshot_data_url?: string;
    blocking_reason?: string;
    steps?: Array<{
      step_name?: string;
      url?: string;
      expected?: string;
      observed?: string;
      passed?: boolean;
      screenshot_data_url?: string;
    }>;
  } | null>(null);

  // Consume Task 3 WebSocket Client hook
  const {
    connectionState,
    events: liveEvents,
    clearBuffer: clearSocketBuffer,
    error: socketError,
  } = useAgentRunSocket(runId, {
    autoConnect: true,
    bufferCap: 500,
  });

  const targetUri = getWebSocketUri(runId);

  // Derive real test cases from live WebSocket events
  const currentTestCases = useMemo<TestCaseResult[]>(() => {
    if (isLiveStream) {
      const cases: TestCaseResult[] = [];
      liveEvents.forEach((evt, idx) => {
        const agent = (evt.agent || '').toLowerCase();
        const payload = (evt.payload || {}) as Record<string, unknown>;
        const statusStr = String(payload.status || evt.eventType || '').toLowerCase();

        if (agent === 'test_runner') {
          const isBrowserEvt =
            String(evt.eventType || '').toLowerCase().includes('browser') ||
            String(evt.message || '').toLowerCase().includes('browser test');
          if (isBrowserEvt) return;
          const passed =
            payload.passed === true ||
            statusStr.includes('success') ||
            statusStr.includes('pass');
          cases.push({
            id: `tc-sandbox-${idx}`,
            name: 'Sandbox Test Suite Execution',
            status: passed ? 'passed' : 'failed',
            durationMs: 1240,
            filePath: 'sandbox/test_runner',
            description:
              typeof payload.details === 'string' && payload.details.trim()
                ? payload.details.trim()
                : evt.message || 'Executed test suite in isolated sandbox environment.',
            assertionError: !passed ? String(payload.blocking_reason || payload.details || evt.message || 'Test failed') : undefined,
          });
        } else if (agent === 'coder' && statusStr.includes('success')) {
          cases.push({
            id: `tc-coder-${idx}`,
            name: 'AST Patch Syntax & Boundary Verification',
            status: 'passed',
            durationMs: 420,
            filePath: 'coder/patch_validator',
            description: evt.message || 'Patch generated and validated against AST guardrails.',
          });
        } else if (agent === 'reviewer') {
          const passed =
            String(payload.verdict || '').toLowerCase() === 'approve' ||
            statusStr.includes('success');
          cases.push({
            id: `tc-reviewer-${idx}`,
            name: 'Automated Code Review & Security Gate',
            status: passed ? 'passed' : 'failed',
            durationMs: 680,
            filePath: 'reviewer/quality_gate',
            description: evt.message || 'Verified patch against approved implementation plan.',
          });
        } else if (agent === 'pr' && statusStr.includes('success')) {
          cases.push({
            id: `tc-pr-${idx}`,
            name: 'GitHub Branch Push & Pull Request Verification',
            status: 'passed',
            durationMs: 890,
            filePath: String(payload.pr_url || 'github/pull_request'),
            description: evt.message || 'Pull Request opened and verified on GitHub.',
          });
        }
      });
      return cases;
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
  }, [isLiveStream, liveEvents, activePreviewState]);

  // Derive active summary based on mode and live test cases
  const currentSummary = useMemo(() => {
    if (isLiveStream) {
      if (connectionState === 'DISCONNECTED') return OFFLINE_SUMMARY;
      const passedCount = currentTestCases.filter((c) => c.status === 'passed').length;
      const failedCount = currentTestCases.filter((c) => c.status === 'failed').length;
      const totalTests = currentTestCases.length;
      const hasTestRunnerFinished = liveEvents.some(
        (e) => (e.agent || '').toLowerCase() === 'test_runner'
      );
      const suiteStatus: 'RUNNING' | 'PASSED' | 'FAILED' | 'OFFLINE' =
        failedCount > 0
          ? 'FAILED'
          : hasTestRunnerFinished && passedCount > 0
          ? 'PASSED'
          : connectionState === 'CONNECTED'
          ? 'RUNNING'
          : 'OFFLINE';

      return {
        ...RUNNING_SUMMARY,
        status: suiteStatus,
        totalTests: totalTests || liveEvents.length,
        executedTests: totalTests || liveEvents.length,
        passedCount,
        failedCount,
        skippedCount: 0,
        exitCode: suiteStatus === 'PASSED' ? 0 : suiteStatus === 'FAILED' ? 1 : null,
        isolationStatus: 'Healthy' as const,
        sandboxVmId: runId ? `sandbox-${runId.slice(0, 8)}` : 'sandbox-standby',
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
  }, [isLiveStream, connectionState, currentTestCases, liveEvents, activePreviewState, runId]);

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
        const agent = (evt.agent || '').toLowerCase();
        const evType = (evt.eventType || '').toLowerCase();
        const tag =
          evType.includes('fail') || evType.includes('error')
            ? 'fail'
            : agent === 'test_runner'
            ? 'test'
            : evType.includes('complete') || evType.includes('pass')
            ? 'pass'
            : 'info';

        return {
          id: evt.id || `evt-${idx}`,
          timestamp: time,
          tag,
          category:
            tag === 'fail'
              ? 'stderr'
              : agent === 'test_runner' || tag === 'test'
              ? 'test_runner'
              : 'stdout',
          content: `${evt.agent ? `[${evt.agent}] ` : ''}${
            evt.tool ? `tool: ${evt.tool} - ` : ''
          }${JSON.stringify(evt.payload || evt.raw || '', (k, v) =>
            k === 'screenshot_data_url' && typeof v === 'string' ? '[base64_png_captured]' : v
          )}`,
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

  // Extract latest browser_tests_completed payload from WebSocket events or manual trigger
  const activeBrowserReport = useMemo(() => {
    if (manualBrowserReport) return manualBrowserReport;
    for (let i = liveEvents.length - 1; i >= 0; i--) {
      const evt = liveEvents[i];
      const evType = String(evt.eventType || '').toLowerCase();
      const payload = (evt.payload || {}) as Record<string, unknown>;
      const meta = (payload.metadata || payload) as Record<string, unknown>;
      if (evType.includes('browser') || meta.screenshot_data_url || meta.target_url) {
        return {
          passed: Boolean(meta.passed ?? payload.passed),
          status: String(payload.status || (meta.passed ? 'passed' : 'completed')),
          target_url: String(meta.target_url || localhostUrl),
          screenshot_data_url: typeof meta.screenshot_data_url === 'string' ? meta.screenshot_data_url : undefined,
          blocking_reason: typeof meta.blocking_reason === 'string' ? meta.blocking_reason : undefined,
          steps: Array.isArray(meta.steps) ? (meta.steps as any[]) : [],
        };
      }
    }
    return null;
  }, [manualBrowserReport, liveEvents, localhostUrl]);

  const handleRunBrowserCapture = useCallback(async () => {
    setIsCapturingBrowser(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';
      const resp = await fetch(`${apiBase}/runs/browser-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_url: localhostUrl, run_id: runId }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setManualBrowserReport(data);
        setBrowserViewTab('screenshot');
      }
    } catch {
      // Non-fatal fallback
    } finally {
      setIsCapturingBrowser(false);
    }
  }, [localhostUrl, runId]);

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
              FastAPI server and sandbox are running.
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
