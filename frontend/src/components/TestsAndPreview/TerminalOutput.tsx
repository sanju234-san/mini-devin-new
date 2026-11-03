'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { LogLine } from './testsAndPreviewUtils';
import { formatLogLineForXterm } from './testsAndPreviewUtils';

interface TerminalOutputProps {
  logs: LogLine[];
  autoScroll: boolean;
  filterText: string;
  activeCategory: 'all' | 'stdout' | 'stderr' | 'test_runner';
  isLive: boolean;
  isSkeleton?: boolean;
}

export const TerminalOutput: React.FC<TerminalOutputProps> = ({
  logs,
  autoScroll,
  filterText,
  activeCategory,
  isLive,
  isSkeleton = false,
}) => {
  const terminalRef = useRef<HTMLDivElement | null>(null);
  const xtermInstance = useRef<any>(null);
  const [terminalReady, setTerminalReady] = useState(false);
  const [activeViewMode, setActiveViewMode] = useState<'xterm' | 'interactive'>('interactive');
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Filter logs by category and search text
  const filteredLogs = logs.filter((line) => {
    if (activeCategory !== 'all' && line.category !== activeCategory) {
      return false;
    }
    if (filterText.trim()) {
      const q = filterText.toLowerCase();
      const matchContent = line.content.toLowerCase().includes(q);
      const matchTag = line.tag.toLowerCase().includes(q);
      const matchExpected = line.details?.expected?.toLowerCase().includes(q);
      const matchActual = line.details?.actual?.toLowerCase().includes(q);
      return matchContent || matchTag || matchExpected || matchActual;
    }
    return true;
  });

  // Calculate buffer size
  const totalBufferSizeKb = Math.max(
    1,
    Math.round(logs.reduce((acc, l) => acc + l.content.length + 30, 0) / 1024)
  );

  // Initialize xterm client-side
  useEffect(() => {
    let isMounted = true;

    async function initXterm() {
      if (!terminalRef.current || xtermInstance.current) return;

      try {
        const { Terminal } = await import('xterm');

        if (!isMounted || !terminalRef.current) return;

        const term = new Terminal({
          theme: {
            background: '#080f17',
            foreground: '#dce3f0',
            cursor: '#adc6ff',
            cursorAccent: '#080f17',
            selectionBackground: '#2e353f',
            black: '#151c25',
            red: '#ffb4ab',
            green: '#10b981',
            yellow: '#fde047',
            blue: '#adc6ff',
            magenta: '#c0c1ff',
            cyan: '#4cd7f6',
            white: '#dce3f0',
            brightBlack: '#424754',
            brightRed: '#ffdad6',
            brightGreen: '#34d399',
            brightYellow: '#fef08a',
            brightBlue: '#c0c1ff',
            brightMagenta: '#e0e7ff',
            brightCyan: '#67e8f9',
            brightWhite: '#ffffff',
          },
          fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
          fontSize: 12,
          lineHeight: 1.5,
          cursorBlink: false,
          disableStdin: true, // STRICT READ-ONLY
          convertEol: true,
          scrollback: 5000,
          allowTransparency: true,
        });

        term.open(terminalRef.current);
        xtermInstance.current = term;
        setTerminalReady(true);

        // Auto resize calculation
        const handleResize = () => {
          if (!terminalRef.current || !term) return;
          const charWidth = 7.5;
          const charHeight = 18;
          const cols = Math.max(40, Math.floor(terminalRef.current.clientWidth / charWidth));
          const rows = Math.max(10, Math.floor(terminalRef.current.clientHeight / charHeight));
          try {
            term.resize(cols, rows);
          } catch {
            // Ignore resize errors during render
          }
        };

        handleResize();
        resizeObserverRef.current = new ResizeObserver(() => handleResize());
        resizeObserverRef.current.observe(terminalRef.current);
      } catch (err) {
        // Fallback to rich HTML view if xterm fails to load
        console.warn('xterm.js dynamic load notice, using standard rich log viewport', err);
      }
    }

    if (activeViewMode === 'xterm') {
      initXterm();
    }

    return () => {
      isMounted = false;
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
      if (xtermInstance.current) {
        try {
          xtermInstance.current.dispose();
        } catch {
          // Dispose safely
        }
        xtermInstance.current = null;
      }
      setTerminalReady(false);
    };
  }, [activeViewMode]);

  // Write logs to xterm when logs or filters change
  useEffect(() => {
    if (activeViewMode === 'xterm' && xtermInstance.current && terminalReady) {
      xtermInstance.current.reset();
      filteredLogs.forEach((line, index) => {
        xtermInstance.current.write(formatLogLineForXterm(line, index));
      });
      if (autoScroll) {
        xtermInstance.current.scrollToBottom();
      }
    }
  }, [filteredLogs, activeViewMode, terminalReady, autoScroll]);

  // Handle auto-scroll for interactive HTML view
  const interactiveScrollRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (autoScroll && interactiveScrollRef.current) {
      interactiveScrollRef.current.scrollTop = interactiveScrollRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  if (isSkeleton) {
    return (
      <div className="flex-1 flex flex-col bg-surface-container-lowest p-4 gap-3 animate-pulse font-mono text-xs">
        <div className="h-4 bg-surface-container-high rounded w-3/4" />
        <div className="h-4 bg-surface-container-high rounded w-1/2" />
        <div className="h-4 bg-surface-container-high rounded w-5/6" />
        <div className="h-4 bg-surface-container-high rounded w-2/3" />
        <div className="h-4 bg-surface-container-high rounded w-4/5" />
        <div className="h-4 bg-surface-container-high rounded w-3/5" />
        <div className="h-4 bg-surface-container-high rounded w-4/6" />
        <div className="mt-auto h-4 bg-surface-container-high rounded w-full" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-surface-container-lowest overflow-hidden relative">
      {/* View Switcher: High-Fidelity Rich Log Viewport vs Raw xterm.js Engine */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-surface-container-high/80 backdrop-blur-xs p-0.5 rounded border border-outline-variant/30 text-[10px] font-mono">
        <button
          type="button"
          onClick={() => setActiveViewMode('interactive')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeViewMode === 'interactive'
              ? 'bg-primary-container text-on-primary-container font-semibold'
              : 'text-outline hover:text-on-surface'
          }`}
          title="Enhanced formatted view with inline diff blocks"
        >
          Rich Log View
        </button>
        <button
          type="button"
          onClick={() => setActiveViewMode('xterm')}
          className={`px-2 py-0.5 rounded transition-colors ${
            activeViewMode === 'xterm'
              ? 'bg-primary-container text-on-primary-container font-semibold'
              : 'text-outline hover:text-on-surface'
          }`}
          title="Standard xterm.js terminal stream"
        >
          xterm.js
        </button>
      </div>

      {activeViewMode === 'xterm' ? (
        <div
          ref={terminalRef}
          className="w-full h-full min-h-[460px] p-space-sm overflow-hidden"
          style={{ backgroundColor: '#080f17' }}
        />
      ) : (
        /* Rich Interactive View matching Stitch reference precisely */
        <div
          ref={interactiveScrollRef}
          className="w-full flex-1 min-h-[460px] max-h-[580px] overflow-y-auto p-3 font-mono text-[12px] leading-relaxed selection:bg-surface-container-highest"
        >
          {filteredLogs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-outline text-xs gap-2 py-16">
              <span>No logs found matching current filter.</span>
              <span className="text-[11px] text-outline/60">
                Category: {activeCategory} | Search: &quot;{filterText}&quot;
              </span>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {filteredLogs.map((line, idx) => {
                const lineNum = String(idx + 1).padStart(2, '0');
                const isFail = line.tag === 'fail';
                const isPass = line.tag === 'pass';
                const isWarn = line.tag === 'warn';
                const isTest = line.tag === 'test';

                return (
                  <div
                    key={line.id || idx}
                    className={`flex flex-col rounded px-2 py-1 transition-colors ${
                      isFail
                        ? 'bg-red-950/20 border-l-2 border-red-500'
                        : isPass
                        ? 'hover:bg-surface-container-low/40'
                        : 'hover:bg-surface-container-low/30'
                    }`}
                  >
                    <div className="flex items-start gap-2.5 flex-wrap sm:flex-nowrap">
                      {/* Line Number */}
                      <span className="text-outline/50 select-none text-[11px] w-6 shrink-0 text-right">
                        {lineNum}
                      </span>

                      {/* Timestamp */}
                      <span className="text-outline/70 select-none text-[11px] shrink-0">
                        [{line.timestamp}]
                      </span>

                      {/* Tag Badge */}
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.2 rounded shrink-0 select-none ${
                          isFail
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : isPass
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : isWarn
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : isTest
                            ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                            : 'bg-surface-container-high text-outline'
                        }`}
                      >
                        [{line.tag}]
                      </span>

                      {/* Log Message Content */}
                      <span
                        className={`font-mono break-all ${
                          isFail
                            ? 'text-red-300 font-semibold'
                            : isPass
                            ? 'text-emerald-300'
                            : isWarn
                            ? 'text-amber-300'
                            : isTest
                            ? 'text-cyan-300'
                            : 'text-on-surface'
                        }`}
                      >
                        {line.content}
                      </span>
                    </div>

                    {/* Inline Assertion Diff Box for Test Failures */}
                    {line.details && (
                      <div className="ml-8 sm:ml-12 my-2 p-2.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 text-xs font-mono flex flex-col gap-1.5 shadow-xs">
                        {line.details.expected && (
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-outline">
                              Expected: <span className="text-emerald-400">{line.details.expected}</span>
                            </span>
                            <span className="text-[11px] text-outline">
                              Actual: <span className="text-red-400">{line.details.actual}</span>
                            </span>
                          </div>
                        )}

                        <div className="p-2 rounded bg-[#04080e] border border-outline-variant/20 flex flex-col gap-0.5 text-[11px]">
                          <span className="text-[10px] uppercase tracking-wider text-outline select-none">
                            Inline Diff:
                          </span>
                          <span className="text-red-400 font-bold bg-red-950/40 px-1 py-0.5 rounded">
                            - [{line.details.expected}]
                          </span>
                          <span className="text-emerald-400 font-bold bg-emerald-950/40 px-1 py-0.5 rounded">
                            + [{line.details.actual}]
                          </span>
                        </div>

                        {line.details.location && (
                          <span className="text-[11px] text-outline flex items-center gap-1">
                            <span className="text-red-400">&#8599;</span> at {line.details.location}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Terminal Footer Strip matching Stitch screenshot */}
      <div className="px-3 py-2 bg-surface-container-high/60 border-t border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-outline select-none">
        <div className="flex items-center gap-2">
          <span>
            Showing lines 1-{filteredLogs.length} of {logs.length}
          </span>
          <span className="text-outline-variant">|</span>
          <span>Buffer: {totalBufferSizeKb} KB</span>
          <span className="text-outline-variant">|</span>
          <span>UTF-8</span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-outline">
            <svg
              className="w-3.5 h-3.5 text-outline"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Read-only stream</span>
          </div>
        </div>
      </div>
    </div>
  );
};
