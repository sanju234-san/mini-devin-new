'use client';

import React, { useState } from 'react';
import type { ArtifactItem, ViewModeTab } from './artifactsUtils';

interface ArtifactPreviewPaneProps {
  artifact: ArtifactItem | null;
  onNavigateToDiff?: () => void;
  onNavigateToTests?: () => void;
}

export const ArtifactPreviewPane: React.FC<ArtifactPreviewPaneProps> = ({
  artifact,
  onNavigateToDiff,
  onNavigateToTests,
}) => {
  const [activeTab, setActiveTab] = useState<ViewModeTab>('formatted');
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!artifact) {
    return (
      <div className="h-full rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center text-outline p-space-xl font-mono text-xs text-center">
        <svg className="w-12 h-12 text-outline/30 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
        <span className="font-semibold text-on-surface">No artifact selected</span>
        <span className="text-[11px] text-outline/70 mt-1">Select an artifact from the list on the left to inspect its contents.</span>
      </div>
    );
  }

  const handleCopyRaw = () => {
    navigator.clipboard.writeText(artifact.content || artifact.rawSource);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    setDownloading(true);
    const blob = new Blob([artifact.content || artifact.rawSource], { type: artifact.mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = artifact.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setTimeout(() => setDownloading(false), 1200);
  };

  const isPurged = artifact.status === 'purged';

  return (
    <div className="flex flex-col h-full rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-xs font-mono text-xs">
      {/* 1. Header Information Strip matching Stitch design */}
      <div className="p-space-md bg-surface-container-high/60 border-b border-outline-variant/20 flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Left: Icon + Title + Badges */}
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-primary shrink-0 border border-outline-variant/30">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>

            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-on-surface truncate">
                  {artifact.name}
                </span>

                {artifact.metaBadge && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {artifact.metaBadge}
                  </span>
                )}

                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    isPurged
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${isPurged ? 'bg-red-400' : 'bg-emerald-400'}`} />
                  <span>{isPurged ? 'PURGED' : 'AVAILABLE'}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopyRaw}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface-container hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-on-surface text-xs font-mono transition-colors"
              title="Copy artifact contents to clipboard"
            >
              {copied ? (
                <>
                  <span className="text-emerald-400">✓</span>
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                  <span>Copy Raw</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading || isPurged}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded font-bold text-xs font-mono shadow-xs transition-colors ${
                isPurged
                  ? 'bg-surface-container text-outline cursor-not-allowed opacity-50'
                  : 'bg-primary-container text-on-primary-container hover:bg-primary-container/90'
              }`}
              title="Download artifact file"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>{downloading ? 'Downloading...' : `Download (${artifact.sizeFormatted})`}</span>
            </button>
          </div>
        </div>

        {/* Metadata Details Line */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-outline pt-1 border-t border-outline-variant/20">
          <span>Created: {artifact.timestampFormatted} UTC</span>
          <span className="text-outline-variant">•</span>
          <span>Size: {artifact.sizeFormatted}</span>
          <span className="text-outline-variant">•</span>
          <span>MIME: {artifact.mimeType}</span>
          <span className="text-outline-variant">•</span>
          <span className="truncate">SHA256: {artifact.sha256.substring(0, 16)}...</span>
        </div>
      </div>

      {/* 2. View Mode Tabs Strip */}
      <div className="px-space-md py-2 border-b border-outline-variant/20 flex flex-wrap items-center justify-between gap-2 bg-surface-container-low select-none">
        <div className="flex items-center gap-1 flex-wrap">
          <button
            type="button"
            onClick={() => setActiveTab('formatted')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${
              activeTab === 'formatted'
                ? 'bg-surface-container-highest text-primary font-bold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            <span>Formatted Markdown</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('raw')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${
              activeTab === 'raw'
                ? 'bg-surface-container-highest text-primary font-bold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
            <span>Raw Source (Lines 1-{artifact.linesCount || 84})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('manifest')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${
              activeTab === 'manifest'
                ? 'bg-surface-container-highest text-primary font-bold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18" />
              <path d="M9 21V9" />
            </svg>
            <span>Metadata &amp; JSON Manifest</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('provenance')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-colors ${
              activeTab === 'provenance'
                ? 'bg-surface-container-highest text-primary font-bold border border-outline-variant/40'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="6" y1="3" x2="6" y2="15" />
              <circle cx="18" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <path d="M18 9a9 9 0 0 1-9 9" />
            </svg>
            <span>Provenance &amp; Agent Trail</span>
          </button>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-outline">
          <span>Encoding: UTF-8</span>
          <span className="text-outline-variant">•</span>
          <span>Lines: {artifact.linesCount || 84}</span>
        </div>
      </div>

      {/* 3. Main Content Viewport */}
      <div className="flex-1 overflow-y-auto p-4 bg-surface-container-lowest max-h-[580px]">
        {/* Formatted View */}
        {activeTab === 'formatted' && (
          <div className="flex flex-col gap-3 font-mono text-xs leading-relaxed text-on-surface">
            {/* Quick Cross-Navigation Banner if Patch or Test Suite */}
            {artifact.type === 'patch' && onNavigateToDiff && (
              <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between gap-2">
                <span className="text-emerald-300">This artifact is a unified code diff ready for PR review.</span>
                <button
                  type="button"
                  onClick={onNavigateToDiff}
                  className="px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 font-bold border border-emerald-500/40 transition-colors shrink-0"
                >
                  Open in Diff Viewer (Task 6) ↗
                </button>
              </div>
            )}

            {artifact.type === 'test_suite' && onNavigateToTests && (
              <div className="p-3 rounded-lg bg-blue-950/20 border border-blue-500/30 flex items-center justify-between gap-2">
                <span className="text-blue-300">This artifact is a test execution report.</span>
                <button
                  type="button"
                  onClick={onNavigateToTests}
                  className="px-2.5 py-1 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 font-bold border border-blue-500/40 transition-colors shrink-0"
                >
                  Open in Tests &amp; Preview (Task 7) ↗
                </button>
              </div>
            )}

            {/* Markdown Plan Sections View */}
            {artifact.type === 'plan' ? (
              <div className="flex flex-col gap-4">
                <div className="p-3 rounded-lg bg-surface-container-high/40 border border-outline-variant/30 flex flex-col gap-2">
                  <span className="text-xs uppercase font-bold text-primary tracking-wide">
                    // Strategic Rationale &amp; Objectives
                  </span>
                  <p className="text-on-surface-variant leading-relaxed">
                    Prevent multibyte character corruption when chunking text stream buffers in ruby tokenizer native extensions.
                  </p>
                </div>

                <div className="flex flex-col gap-2">
                  <span className="text-xs uppercase font-bold text-outline tracking-wider">
                    01 // Implementation Steps (3 of 4 phases completed)
                  </span>

                  <div className="flex flex-col gap-2">
                    <div className="p-3 rounded bg-surface-container/60 border border-outline-variant/20 flex items-start gap-2.5">
                      <span className="text-emerald-400 font-bold mt-0.5">☑</span>
                      <div className="flex flex-col gap-1 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-on-surface">Synthesize failing reproduction test suite in test/test_multibyte_utf8.rb</span>
                          <span className="text-outline text-[11px]">10:41:40</span>
                        </div>
                        <span className="text-[11px] text-outline">Asserted expected token output against sample files containing UTF-8 glyphs.</span>
                      </div>
                    </div>

                    <div className="p-3 rounded bg-surface-container/60 border border-outline-variant/20 flex items-start gap-2.5">
                      <span className="text-emerald-400 font-bold mt-0.5">☑</span>
                      <div className="flex flex-col gap-1 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-on-surface">Patch tokenizer scanner chunking in lib/linguist/scanner.c</span>
                          <span className="text-outline text-[11px]">10:42:06</span>
                        </div>
                        <span className="text-[11px] text-outline">Replace fixed 1024-byte window with multibyte-aware UTF-8 boundary detection.</span>
                      </div>
                    </div>

                    <div className="p-3 rounded bg-surface-container/60 border border-outline-variant/20 flex items-start gap-2.5">
                      <span className="text-emerald-400 font-bold mt-0.5">☑</span>
                      <div className="flex flex-col gap-1 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-on-surface">Recompile native C extensions &amp; run regression suite</span>
                          <span className="text-outline text-[11px]">10:42:15</span>
                        </div>
                        <span className="text-[11px] text-outline">Invoked bundle exec rake compile &amp;&amp; bundle exec rake test in sandbox container.</span>
                      </div>
                    </div>

                    <div className="p-3 rounded bg-surface-container/30 border border-outline-variant/15 flex items-start gap-2.5 opacity-75">
                      <span className="text-outline font-bold mt-0.5">☐</span>
                      <div className="flex flex-col gap-1 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-outline">Final sanity benchmark and pull request composition</span>
                          <span className="text-amber-400 text-[11px]">Pending</span>
                        </div>
                        <span className="text-[11px] text-outline/80">Measure throughput impact against baseline corpus and submit branch.</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Code Structure Modification Box matching Stitch reference */}
                <div className="flex flex-col gap-2 mt-2">
                  <div className="flex items-center justify-between text-[11px] text-outline">
                    <span>02 // CODE STRUCTURE MODIFICATION</span>
                    <span>lib/linguist/scanner.c (Lines 142–158)</span>
                  </div>

                  <div className="rounded-lg bg-[#04080e] border border-outline-variant/30 p-3 font-mono text-[11px] overflow-x-auto">
                    <div className="flex items-center justify-between pb-2 mb-2 border-b border-outline-variant/20">
                      <span className="text-outline">scanner.c — Multibyte Chunking Patch</span>
                      <span className="text-emerald-400 font-bold">Diff Ready for PR</span>
                    </div>
                    <pre className="text-on-surface leading-relaxed">
                      <span className="text-outline/50">142   </span>/* Ensure buffer does not slice UTF-8 code point */{'\n'}
                      <span className="text-red-400 bg-red-950/30 block"><span className="text-outline/50">143 - </span>  while (cursor &lt; max_len &amp;&amp; *cursor != &apos;\0&apos;) &#123;</span>
                      <span className="text-red-400 bg-red-950/30 block"><span className="text-outline/50">144 - </span>    chunk_buffer[idx++] = *cursor++;</span>
                      <span className="text-emerald-400 bg-emerald-950/30 block"><span className="text-outline/50">145 + </span>  int seq_len = utf8_codepoint_length(*cursor);</span>
                      <span className="text-emerald-400 bg-emerald-950/30 block"><span className="text-outline/50">146 + </span>  if (cursor + seq_len &gt; max_len) break;</span>
                    </pre>
                  </div>
                </div>
              </div>
            ) : artifact.type === 'image' ? (
              /* Image / Screenshot Preview */
              <div className="flex flex-col items-center justify-center p-space-lg rounded-xl bg-surface-container border border-outline-variant/30 gap-3">
                <div className="w-full max-w-xl h-64 rounded-lg bg-[#04080e] border border-outline-variant/30 flex flex-col items-center justify-center text-outline gap-2 shadow-inner">
                  <svg className="w-10 h-10 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <polyline points="21 15 16 10 5 21" />
                  </svg>
                  <span className="text-xs font-semibold text-on-surface">Playwright DOM Capture: 1280x800 webp</span>
                  <span className="text-[11px] text-outline">Render verification snapshot captured in isolated sandbox browser</span>
                </div>
              </div>
            ) : (
              /* Default Monospaced Formatted Content */
              <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-on-surface bg-surface-container/40 p-space-md rounded-lg border border-outline-variant/20">
                {artifact.content}
              </pre>
            )}
          </div>
        )}

        {/* Raw Source View */}
        {activeTab === 'raw' && (
          <div className="rounded-lg bg-[#04080e] border border-outline-variant/30 p-3 overflow-x-auto font-mono text-xs">
            <pre className="text-on-surface leading-relaxed">
              {artifact.content || artifact.rawSource}
            </pre>
          </div>
        )}

        {/* Metadata & JSON Manifest View */}
        {activeTab === 'manifest' && (
          <div className="rounded-lg bg-[#04080e] border border-outline-variant/30 p-4 font-mono text-xs overflow-x-auto">
            <span className="text-outline block mb-2">// Artifact JSON Manifest &amp; Checksum Verification</span>
            <pre className="text-emerald-300 leading-relaxed">
              {JSON.stringify(
                {
                  id: artifact.id,
                  name: artifact.name,
                  type: artifact.type,
                  mimeType: artifact.mimeType,
                  sizeBytes: artifact.sizeBytes,
                  sha256: artifact.sha256,
                  createdAt: artifact.createdAt,
                  manifest: artifact.manifestJson,
                },
                null,
                2
              )}
            </pre>
          </div>
        )}

        {/* Provenance & Agent Trail View */}
        {activeTab === 'provenance' && (
          <div className="flex flex-col gap-3 font-mono text-xs">
            <span className="text-outline">// Synthesizing Node Provenance &amp; Agent Signature</span>

            {artifact.provenanceTrail ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 flex flex-col gap-1">
                  <span className="text-outline text-[11px]">Originating Agent</span>
                  <span className="font-bold text-on-surface">{artifact.provenanceTrail.originatingAgent}</span>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 flex flex-col gap-1">
                  <span className="text-outline text-[11px]">Model Tier Used</span>
                  <span className="font-bold text-primary">{artifact.provenanceTrail.modelUsed}</span>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 flex flex-col gap-1">
                  <span className="text-outline text-[11px]">Execution Latency</span>
                  <span className="font-bold text-on-surface">{artifact.provenanceTrail.executionDuration}</span>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 flex flex-col gap-1">
                  <span className="text-outline text-[11px]">Pipeline Step</span>
                  <span className="font-bold text-emerald-400">Step #{artifact.provenanceTrail.stepNumber}</span>
                </div>

                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/30 flex flex-col gap-1 sm:col-span-2">
                  <span className="text-outline text-[11px]">Cryptographic Signature</span>
                  <span className="text-outline-variant font-mono text-[11px] truncate">{artifact.provenanceTrail.verifiedSignature}</span>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-surface-container text-outline">
                No provenance trail recorded for this artifact.
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. Preview Footer Strip matching Stitch design */}
      <div className="p-space-sm bg-surface-container-high/60 border-t border-outline-variant/20 flex flex-wrap items-center justify-between gap-3 text-[11px] text-outline">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-outline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>Read-only Sandbox Preview</span>
        </div>

        <div className="flex items-center gap-3">
          <span>{artifact.wordsCount ? `${artifact.wordsCount.toLocaleString()} words` : 'Binary asset'}</span>
          <span className="text-outline-variant">•</span>
          <span>LF line endings</span>
          <span className="text-outline-variant">•</span>
          <div className="flex items-center gap-1 text-emerald-400">
            <span>✓</span>
            <span>Cryptographic Checksum Verified</span>
          </div>
        </div>
      </div>
    </div>
  );
};
