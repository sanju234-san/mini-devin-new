'use client';

import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import type { FileDiffItem, DiffRenderMode } from './types';
import { CopyIcon, CheckIcon } from './diffUtils';

// Dynamically import Monaco DiffEditor for client-side rendering only
const DynamicDiffEditor = dynamic(
  () => import('@monaco-editor/react').then((mod) => mod.DiffEditor),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-[520px] bg-surface-container-lowest flex items-center justify-center font-mono text-xs text-outline animate-pulse">
        <span>Initializing Monaco Diff Engine...</span>
      </div>
    ),
  }
);

interface MonacoDiffEditorProps {
  file: FileDiffItem;
  renderMode: DiffRenderMode;
  onMountNavigator?: (nav: { next: () => void; previous: () => void }) => void;
}

export const MonacoDiffEditor: React.FC<MonacoDiffEditorProps> = ({
  file,
  renderMode,
  onMountNavigator,
}) => {
  const [copied, setCopied] = useState(false);
  const [wordWrap, setWordWrap] = useState<'on' | 'off'>('off');
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(file.modifiedCode || file.originalCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleEditorMount = (editor: any, monaco: any) => {
    // Define high-fidelity dark theme consistent with Mini-Devin Stitch tokens
    monaco.editor.defineTheme('miniDevinTheme', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#0b1118',
        'editorGutter.background': '#080f17',
        'diffEditor.insertedTextBackground': 'rgba(16, 185, 129, 0.22)',
        'diffEditor.removedTextBackground': '#93000a50',
        'diffEditor.insertedLineBackground': 'rgba(16, 185, 129, 0.12)',
        'diffEditor.removedLineBackground': '#3b121960',
        'editorLineNumber.foreground': '#4e5564',
        'editorLineNumber.activeForeground': '#adc6ff',
      },
    });
    monaco.editor.setTheme('miniDevinTheme');

    // Setup Monaco diff navigator
    if (onMountNavigator && monaco.editor.createDiffNavigator) {
      try {
        const navigator = monaco.editor.createDiffNavigator(editor, {
          followsCaret: true,
          ignoreCharChanges: true,
        });
        onMountNavigator({
          next: () => navigator.next(),
          previous: () => navigator.previous(),
        });
      } catch {
        // Fallback gracefully if navigator creation is unavailable
      }
    }
  };

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-md flex flex-col">
      {/* Editor Subheader Strip Matching Stitch Reference */}
      <div className="px-space-md py-2.5 bg-surface-container-high/60 border-b border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
        {/* Left: Code Icon + File Path + Language Badge */}
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="text-red-400 font-bold font-mono text-sm leading-none">&#123;&#125;</span>
          <span className="font-semibold text-on-surface truncate">{file.path}</span>
          {file.language && (
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-mono bg-surface-container border border-outline-variant/30 text-outline">
              {file.language}
            </span>
          )}
        </div>

        {/* Right: Word Wrap Toggle + Copy File Code */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setWordWrap((prev) => (prev === 'on' ? 'off' : 'on'))}
            className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors ${
              wordWrap === 'on'
                ? 'bg-primary-container/20 text-primary border-primary/30'
                : 'bg-surface-container border-outline-variant/30 text-outline hover:text-on-surface'
            }`}
            title="Toggle word wrap"
          >
            Wrap: {wordWrap.toUpperCase()}
          </button>

          <button
            type="button"
            onClick={handleCopyCode}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-[11px] transition-colors"
            title="Copy modified file code"
          >
            {copied ? (
              <>
                <CheckIcon className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <CopyIcon className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Monaco DiffEditor Viewport */}
      <div className="relative w-full h-[540px] sm:h-[600px] lg:h-[650px] bg-[#0b1118]">
        {isMounted ? (
          <DynamicDiffEditor
            original={file.originalCode}
            modified={file.modifiedCode}
            language={file.language || 'plaintext'}
            theme="miniDevinTheme"
            onMount={handleEditorMount}
            options={{
              readOnly: true,
              renderSideBySide: renderMode === 'side-by-side',
              wordWrap,
              automaticLayout: true,
              scrollBeyondLastLine: false,
              lineNumbers: 'on',
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: 'JetBrains Mono, ui-monospace, Menlo, Monaco, Consolas, monospace',
              renderOverviewRuler: false,
              contextmenu: false,
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center font-mono text-xs text-outline">
            Loading Diff Viewport...
          </div>
        )}
      </div>
    </div>
  );
};
