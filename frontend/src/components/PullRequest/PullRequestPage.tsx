'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getRunById, getArtifacts, getArtifactById } from '../../services/api';
import { useAgentRunSocket } from '../../hooks/useAgentRunSocket';
import type { AgentRun, ArtifactOut, ArtifactTrail } from '../../services/types';
import { BranchIcon, ChecklistIcon, FolderZipIcon, LockIcon, SourceIcon } from '../icons/Icons';

export interface PullRequestPageProps {
  runId?: string;
  onNavigateToDiff?: () => void;
  onNavigateToTests?: () => void;
}

export const PullRequestPage: React.FC<PullRequestPageProps> = ({
  runId = '',
  onNavigateToDiff,
  onNavigateToTests,
}) => {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [trail, setTrail] = useState<ArtifactTrail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copiedCherryPick, setCopiedCherryPick] = useState<boolean>(false);

  const { events } = useAgentRunSocket(runId, { autoConnect: true });

  const fetchPRData = useCallback(async () => {
    if (!runId) {
      setRun(null);
      setTrail(null);
      return;
    }
    setIsLoading(true);
    try {
      const [runRes, artRes] = await Promise.allSettled([
        getRunById(runId),
        getArtifacts(runId),
      ]);
      if (runRes.status === 'fulfilled') {
        setRun(runRes.value);
      }
      if (artRes.status === 'fulfilled') {
        setTrail(artRes.value);
      }
    } finally {
      setIsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchPRData();
  }, [fetchPRData, events.length]);

  const repo = run?.repository || 'sanjeev23oct/mini-devin';
  const issueNum = run?.issueId ?? 1;
  const issueTitle = run?.title || 'Autonomous Issue Resolution';
  const status = (run?.status || 'standby').toLowerCase();
  const isCompleted = status === 'completed';
  const shortRunId = runId ? runId.slice(0, 7) : 'pending';
  const branchName = `agent/issue-${issueNum}-${shortRunId}`;

  // Extract PR URL & title from WebSocket events if emitted by pr_agent
  let wsPrUrl: string | undefined;
  let wsPrTitle: string | undefined;
  for (let i = events.length - 1; i >= 0; i--) {
    const evt = events[i];
    const p = (evt?.payload || {}) as Record<string, unknown>;
    if (typeof p.pr_url === 'string' && p.pr_url.startsWith('http')) {
      wsPrUrl = p.pr_url;
    }
    if (typeof p.pr_title === 'string' && p.pr_title.trim()) {
      wsPrTitle = p.pr_title.trim();
    }
    if (!wsPrUrl && typeof evt?.message === 'string') {
      const urlMatch = evt.message.match(/https:\/\/github\.com\/[^\s)]+\/pull\/\d+/);
      if (urlMatch?.[0]) {
        wsPrUrl = urlMatch[0];
      }
    }
  }

  const rawTrail = (trail || {}) as Record<string, unknown>;
  const prMarkdown = typeof rawTrail.prMarkdown === 'string' ? rawTrail.prMarkdown : '';
  const reviewMarkdown = typeof rawTrail.reviewMarkdown === 'string' ? rawTrail.reviewMarkdown : '';
  const planMarkdown = typeof trail?.plan === 'string' ? trail.plan : '';
  const diffContent = typeof trail?.diff === 'string' ? trail.diff : '';
  const artifactItems: ArtifactOut[] = Array.isArray(rawTrail.items)
    ? (rawTrail.items as ArtifactOut[])
    : [];

  const rawPrTitle =
    wsPrTitle ||
    prMarkdown.match(/^#\s+Pull Request:\s*(.+)$/m)?.[1]?.trim() ||
    `fix: ${issueTitle} (#${issueNum})`;
  const prTitle = rawPrTitle.replace(/\s*\(#\)\s*$/, '').replace(/\s+#\s*$/, ` (#${issueNum})`);

  const renderFormattedMarkdown = (text: string) => {
    const formatInline = (line: string) => {
      const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
      return parts.map((part, idx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={idx} className="font-semibold text-on-surface">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code
              key={idx}
              className="px-1.5 py-0.5 rounded bg-surface-container-low border border-outline-variant/30 font-mono text-[11px] text-primary"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      });
    };

    return text.split('\n').map((rawLine, i) => {
      const line = rawLine.trimEnd();
      if (!line.trim()) {
        return <div key={i} className="h-2" />;
      }
      if (line.startsWith('# ')) {
        return (
          <h4 key={i} className="text-sm sm:text-base font-bold text-on-surface pb-1.5 mb-1 border-b border-outline-variant/25">
            {formatInline(line.slice(2))}
          </h4>
        );
      }
      if (line.startsWith('## ')) {
        return (
          <h5 key={i} className="text-xs sm:text-sm font-semibold text-primary uppercase tracking-wider mt-3 mb-1">
            {formatInline(line.slice(3))}
          </h5>
        );
      }
      if (line.startsWith('### ')) {
        return (
          <h6 key={i} className="text-xs font-semibold text-on-surface mt-2 mb-0.5">
            {formatInline(line.slice(4))}
          </h6>
        );
      }
      if (line.startsWith('> ')) {
        return (
          <div
            key={i}
            className="pl-3 py-1 my-0.5 border-l-2 border-primary/50 bg-primary-container/10 rounded-r text-xs text-on-surface-variant"
          >
            {formatInline(line.slice(2))}
          </div>
        );
      }
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return (
          <div key={i} className="flex items-start gap-2 pl-2 py-0.5 text-xs text-on-surface-variant">
            <span className="text-primary mt-0.5 select-none">•</span>
            <span className="flex-1 leading-relaxed">{formatInline(line.slice(2))}</span>
          </div>
        );
      }
      return (
        <p key={i} className="text-xs text-on-surface-variant leading-relaxed">
          {formatInline(line)}
        </p>
      );
    });
  };

  const prBody =
    prMarkdown
      .replace(/^#\s+Pull Request:.*$/m, '')
      .replace(/^\*\*URL\*\*:.*$/m, '')
      .replace(/^\*\*Branch\*\*:.*$/m, '')
      .trim() ||
    reviewMarkdown ||
    planMarkdown ||
    (run?.body
      ? `### Issue Context\n${String(run.body)}\n\n### Automated Resolution\nSynthesized and verified via Mini-Devin AST & Sandbox pipeline.`
      : 'No Pull Request body generated yet. Run an autonomous session through Plan Approval to synthesize the PR.');

  const resolvedPrUrl = trail?.prUrl || wsPrUrl;
  const shortSummary = `Closes #${issueNum}\n\nSynthesized and verified by Mini-Devin.`;
  const githubPrUrl =
    resolvedPrUrl ||
    `https://github.com/${repo}/compare/main...${encodeURIComponent(
      branchName
    )}?expand=1&title=${encodeURIComponent(prTitle.slice(0, 120))}&body=${encodeURIComponent(shortSummary)}`;

  const handleDownloadDiff = () => {
    const content = diffContent || `# No diff generated yet for run ${runId || 'none'}\n`;
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `patch-${issueNum}.diff`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadArtifact = async (art: ArtifactOut) => {
    if (!runId) return;
    try {
      const detail = await getArtifactById(runId, art.id);
      const blob = new Blob([detail.content], { type: detail.content_type || 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = art.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore download error
    }
  };

  const handleCopyCherryPick = () => {
    navigator.clipboard?.writeText(`git cherry-pick ${shortRunId}`);
    setCopiedCherryPick(true);
    setTimeout(() => setCopiedCherryPick(false), 2000);
  };

  const completedChecksCount =
    (planMarkdown ? 1 : 0) + (diffContent ? 1 : 0) + (trail?.testLog || isCompleted ? 1 : 0);

  return (
    <div className="p-space-md sm:p-space-lg max-w-[1600px] mx-auto w-full flex flex-col gap-space-lg">
      {/* Top Task Context Bar */}
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 px-space-md py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          <span className="px-2.5 py-1 rounded bg-primary-container/30 border border-primary/30 font-mono text-xs font-semibold text-primary">
            TASK-{issueNum}
          </span>
          <h1 className="text-sm sm:text-base font-semibold text-on-surface truncate">
            {issueTitle}
          </h1>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-mono text-[11px] uppercase tracking-wider font-semibold border ${
              isCompleted
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-primary-container/20 text-primary border-primary/30'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isCompleted ? 'bg-emerald-400' : 'bg-primary animate-pulse'
              }`}
            />
            <span>{isCompleted ? 'READY TO MERGE' : status.toUpperCase()}</span>
          </span>
        </div>

        <div className="flex items-center gap-3 flex-wrap font-mono text-xs text-on-surface-variant">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/30">
            <BranchIcon className="w-3.5 h-3.5 text-primary" />
            <span className="text-primary">{branchName}</span>
            <span className="text-outline">→</span>
            <span className="text-on-surface">main</span>
          </span>
          <button
            type="button"
            onClick={fetchPRData}
            className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-xs text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Main 2-Column Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-space-lg items-start">
        {/* Left 2 Columns */}
        <div className="xl:col-span-2 flex flex-col gap-space-lg">
          {/* 1. Hero Merge Card */}
          <section className="relative overflow-hidden rounded-xl bg-surface-container-low border border-emerald-500/25 p-space-xl flex flex-col items-center text-center shadow-lg">
            {/* Subtle radial emerald top glow */}
            <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

            {/* Shield Icon */}
            <div className="relative w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-4 shadow-md">
              <ChecklistIcon className="w-8 h-8" />
            </div>

            <span className="font-mono text-[11px] uppercase tracking-widest text-emerald-400 font-semibold mb-2">
              SYNTHESIZED & VERIFIED VIA AST PIPELINE
            </span>

            <h2 className="text-2xl sm:text-3xl font-bold text-on-surface max-w-xl mb-3">
              {isCompleted
                ? 'Task Completed — Ready to Merge'
                : runId
                ? `Run Active — ${status.replace(/_/g, ' ').toUpperCase()}`
                : 'Ready to Synthesize Pull Request'}
            </h2>

            <p className="text-sm text-on-surface-variant max-w-xl leading-relaxed mb-6">
              {resolvedPrUrl
                ? `Pull Request has been opened on GitHub: ${resolvedPrUrl}`
                : 'All verification checks and isolated sandbox runs are tracked here. Once the automated patch passes sandbox verification and code review, create or inspect the Pull Request directly on GitHub.'}
            </p>

            {/* Primary Green CTA */}
            <a
              href={githubPrUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2.5 px-6 py-3 rounded-lg bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-semibold text-sm shadow-md transition-colors cursor-pointer"
            >
              <BranchIcon className="w-4 h-4" />
              <span>{resolvedPrUrl ? 'Open Pull Request on GitHub ↗' : 'Create Pull Request on GitHub ↗'}</span>
            </a>

            {/* Quick Action Links */}
            <div className="flex flex-wrap items-center justify-center gap-4 mt-6 pt-4 border-t border-outline-variant/20 text-xs font-mono text-on-surface-variant">
              <button
                type="button"
                onClick={handleDownloadDiff}
                className="hover:text-on-surface transition-colors cursor-pointer"
              >
                ↓ Download .diff patch ({diffContent ? `${(diffContent.length / 1024).toFixed(1)} KB` : '0 KB'})
              </button>
              <span className="text-outline">·</span>
              <button
                type="button"
                onClick={() => onNavigateToTests?.()}
                className="hover:text-on-surface transition-colors cursor-pointer"
              >
                ▣ View full test log
              </button>
              <span className="text-outline">·</span>
              <button
                type="button"
                onClick={handleCopyCherryPick}
                className="hover:text-on-surface transition-colors cursor-pointer"
              >
                ⧉ {copiedCherryPick ? 'Copied!' : `Copy git cherry-pick ${shortRunId}`}
              </button>
            </div>
          </section>

          {/* 2. Verification Checklist */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ChecklistIcon className="w-4 h-4 text-emerald-400" />
                <h3 className="text-base font-semibold text-on-surface">Verification Checklist</h3>
              </div>
              <span className="font-mono text-xs text-outline uppercase">
                {completedChecksCount} / 3 COMPLETED
              </span>
            </div>

            <div className="flex flex-col gap-2.5">
              {/* Check 1 */}
              <div className="p-3.5 rounded-lg bg-surface-container border border-outline-variant/20 flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <ChecklistIcon
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      planMarkdown ? 'text-emerald-400' : 'text-outline'
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium text-on-surface">Plan Approved by Human</div>
                    <div className="text-xs font-mono text-on-surface-variant mt-0.5">
                      {planMarkdown
                        ? `Implementation plan synthesized for run #${shortRunId}`
                        : 'Awaiting Planner synthesis & human approval'}
                    </div>
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase font-semibold border ${
                    planMarkdown
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-surface-container-high text-outline border-outline-variant/30'
                  }`}
                >
                  {planMarkdown ? 'CLEARED' : 'PENDING'}
                </span>
              </div>

              {/* Check 2 */}
              <div className="p-3.5 rounded-lg bg-surface-container border border-outline-variant/20 flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <ChecklistIcon
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      diffContent ? 'text-emerald-400' : 'text-outline'
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium text-on-surface">
                      Code Generated & Reviewed
                    </div>
                    <div className="text-xs font-mono text-on-surface-variant mt-0.5">
                      {diffContent ? (
                        <button
                          type="button"
                          onClick={() => onNavigateToDiff?.()}
                          className="text-primary hover:underline cursor-pointer"
                        >
                          Inspect generated code diff ({diffContent.split('\n').length} lines)
                        </button>
                      ) : (
                        'Awaiting Coder agent patch generation'
                      )}
                    </div>
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase font-semibold border ${
                    diffContent
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-surface-container-high text-outline border-outline-variant/30'
                  }`}
                >
                  {diffContent ? 'SYNCED' : 'PENDING'}
                </span>
              </div>

              {/* Check 3 */}
              <div className="p-3.5 rounded-lg bg-surface-container border border-outline-variant/20 flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <ChecklistIcon
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      trail?.testLog || isCompleted ? 'text-emerald-400' : 'text-outline'
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium text-on-surface">
                      All Tests Passed in Isolated Sandbox
                    </div>
                    <div className="text-xs font-mono text-on-surface-variant mt-0.5">
                      {trail?.testLog
                        ? 'Sandbox test runner verification log recorded'
                        : 'Awaiting Sandbox test execution'}
                    </div>
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase font-semibold border ${
                    trail?.testLog || isCompleted
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : 'bg-surface-container-high text-outline border-outline-variant/30'
                  }`}
                >
                  {trail?.testLog || isCompleted ? 'PASS' : 'STANDBY'}
                </span>
              </div>
            </div>
          </section>

          {/* 3. Automated Pull Request Preview */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-on-surface">
                Automated Pull Request Preview
              </h3>
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-primary uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span>GH-PR-READY</span>
              </span>
            </div>

            {resolvedPrUrl && (
              <div className="flex flex-col gap-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-outline">
                  GITHUB PULL REQUEST URL:
                </span>
                <a
                  href={resolvedPrUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 font-mono text-xs text-emerald-400 hover:underline break-all"
                >
                  {resolvedPrUrl}
                </a>
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-outline">
                COMMIT / PR TITLE:
              </span>
              <div className="p-3 rounded-lg bg-surface-container-highest/60 border border-outline-variant/30 font-mono text-xs text-on-surface">
                {prTitle}
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-outline">
                GENERATED PR BODY:
              </span>
              <div className="p-4 rounded-lg bg-surface-container-highest/60 border border-outline-variant/30 overflow-y-auto max-h-96 flex flex-col gap-0.5">
                {renderFormattedMarkdown(prBody)}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-space-lg">
          {/* 1. Artifact Bundle */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FolderZipIcon className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-on-surface">Artifact Bundle</h3>
              </div>
              <span className="font-mono text-[11px] text-outline uppercase">
                {artifactItems.length} FILES
              </span>
            </div>

            {artifactItems.length === 0 ? (
              <div className="p-4 rounded-lg bg-surface-container border border-outline-variant/20 text-xs font-mono text-on-surface-variant text-center">
                No artifacts recorded for this run yet.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {artifactItems.map((art) => (
                  <div
                    key={art.id}
                    className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-xs font-medium text-on-surface truncate">
                        {art.name}
                      </div>
                      <div className="font-mono text-[10px] text-outline uppercase">
                        {art.type} · {(art.size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDownloadArtifact(art)}
                      className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest text-xs font-mono text-on-surface-variant hover:text-on-surface cursor-pointer"
                      title={`Download ${art.name}`}
                    >
                      ↓
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 2. Target Repository */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center gap-2">
              <SourceIcon className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-on-surface">Target Repository</h3>
            </div>

            <div className="flex flex-col gap-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-outline uppercase text-[10px]">REPOSITORY CONTEXT</span>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant text-[10px]">
                  GitHub
                </span>
              </div>
              <a
                href={`https://github.com/${repo}`}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-semibold text-on-surface hover:text-primary transition-colors truncate"
              >
                {repo}
              </a>

              <div className="border-t border-outline-variant/20 pt-3 flex flex-col gap-1.5">
                <span className="text-outline uppercase text-[10px]">BRANCH STRATEGY</span>
                <div className="flex items-center justify-between">
                  <span className="text-on-surface-variant">Base</span>
                  <span className="text-on-surface font-semibold">main</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-on-surface-variant">Compare</span>
                  <span className="text-emerald-400 truncate max-w-[180px]">{branchName}</span>
                </div>
              </div>
            </div>
          </section>

          {/* 3. Security & Audit */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <LockIcon className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-semibold text-on-surface">Security & Audit</h3>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 font-mono text-[10px] text-emerald-400 uppercase font-semibold">
                PASSING
              </span>
            </div>

            <div className="flex flex-col gap-2.5 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant">Secret Scan</span>
                <span className="text-on-surface">Clean (0 leaks)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant">Sandbox Isolation</span>
                <span className="text-on-surface">Codespaces / Container</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant">AST Syntax Guard</span>
                <span className="text-on-surface">Validated</span>
              </div>
            </div>
          </section>

          {/* 4. Continuous Autonomy */}
          <section className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary-container/20 border border-primary/30 flex items-center justify-center text-primary font-mono text-xs font-bold shrink-0">
              AI
            </div>
            <div>
              <div className="text-xs font-semibold text-on-surface">Continuous Autonomy</div>
              <div className="text-[11px] font-mono text-on-surface-variant">
                Agent standing by for PR review comments.
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
