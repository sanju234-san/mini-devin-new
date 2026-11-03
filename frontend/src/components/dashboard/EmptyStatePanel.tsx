import React, { useState } from 'react';
import { PipelineTracker } from './PipelineTracker';
import { ingestIssue } from '../../services/api';
import {
  TreeIcon,
  PlayIcon,
  BookIcon,
  SchemaIcon,
  SourceIcon,
  BranchIcon,
  LockIcon,
} from '../icons/Icons';

interface EmptyStatePanelProps {
  onRunCreated?: (runId: string) => void;
}

function parseGitHubInput(input: string): { repo: string; issueNumber?: string } {
  const trimmed = input.trim();
  const urlMatch = trimmed.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+?)(?:\.git)?(?:\/issues\/(\d+))?(?:\/.*)?$/i
  );
  if (urlMatch && urlMatch[1]) {
    return {
      repo: urlMatch[1],
      issueNumber: urlMatch[2],
    };
  }
  return { repo: trimmed };
}

export const EmptyStatePanel: React.FC<EmptyStatePanelProps> = ({ onRunCreated }) => {
  const [showForm, setShowForm] = useState(false);
  const [repo, setRepo] = useState('sanjeev23oct/mini-devin');
  const [issueNumber, setIssueNumber] = useState('1');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRepoChange = (val: string) => {
    const parsed = parseGitHubInput(val);
    setRepo(parsed.repo);
    if (parsed.issueNumber) {
      setIssueNumber(parsed.issueNumber);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseGitHubInput(repo);
    const normalizedRepo = parsed.repo;
    const effectiveIssueNum = parsed.issueNumber || issueNumber.trim();

    if (!normalizedRepo || !title.trim() || !body.trim()) {
      setError('Repository, Issue Title, and Issue Body are required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const parsedNum = effectiveIssueNum ? parseInt(effectiveIssueNum, 10) : 1;
      const run = await ingestIssue({
        repo: normalizedRepo,
        issue_number: !Number.isNaN(parsedNum) && parsedNum >= 1 ? parsedNum : 1,
        title: title.trim(),
        body: body.trim(),
      });
      setShowForm(false);
      onRunCreated?.(run.id);
    } catch (err) {
      const apiMsg =
        err && typeof err === 'object' && 'message' in err && typeof (err as { message: unknown }).message === 'string'
          ? (err as { message: string }).message
          : 'Failed to ingest issue';
      setError(apiMsg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="relative overflow-hidden rounded-xl bg-surface-container-low border border-outline-variant/30 shadow-md">
      {/* Background Ambient Glow Accents */}
      <div className="absolute -right-20 -top-20 w-80 h-80 bg-primary/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -left-20 -bottom-20 w-80 h-80 bg-tertiary/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative p-space-lg md:p-space-xl flex flex-col gap-space-lg">
        <div className="flex flex-col xl:flex-row items-start xl:items-center justify-between gap-space-xl">
          <div className="flex flex-col md:flex-row gap-space-lg items-start">
            {/* Flow Icon Visualizer */}
            <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-primary shadow-sm">
              <TreeIcon className="w-7 h-7" />
            </div>

            <div className="flex flex-col gap-space-xs max-w-3xl">
              {/* Pipeline Step Tracker */}
              <PipelineTracker />

              <h2 className="text-xl sm:text-2xl font-semibold text-on-surface">
                Autonomous Issue Intake
              </h2>

              <p className="text-sm text-on-surface-variant leading-relaxed">
                Initialize a new agent session by targeting a repository issue. Mini-Devin will
                automatically inspect repository files, synthesize an architectural plan, implement
                changes, verify with tests, and submit a pull request.
              </p>

              {/* Contextual Metadata Chips */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                  <SourceIcon className="w-3.5 h-3.5 text-outline/80" />
                  <span>Repo: {repo || 'Pending Selection'}</span>
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                  <BranchIcon className="w-3.5 h-3.5 text-outline/80" />
                  <span>Endpoint: POST /issues/ingest</span>
                </span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest/40 border border-outline-variant/20 font-mono text-xs text-outline">
                  <LockIcon className="w-3.5 h-3.5 text-outline/80" />
                  <span>Runtime: Sandbox Isolated</span>
                </span>
              </div>
            </div>
          </div>

          {/* Action Panel */}
          <div className="flex flex-col sm:flex-row xl:flex-col gap-space-sm w-full xl:w-auto flex-shrink-0">
            <button
              type="button"
              onClick={() => setShowForm((prev) => !prev)}
              className="w-full sm:w-auto xl:w-full flex items-center justify-center gap-2 px-space-lg py-2.5 rounded-lg bg-primary-container hover:bg-primary-container/90 text-on-primary-container font-semibold text-sm cursor-pointer shadow-sm transition-colors"
            >
              <PlayIcon className="w-4 h-4 text-on-primary-container" />
              <span>{showForm ? 'Close Intake Form' : 'Initialize Agent Run'}</span>
            </button>

            <div className="flex items-center gap-space-sm w-full">
              <a
                href="http://127.0.0.1:8001/docs"
                target="_blank"
                rel="noreferrer"
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-on-surface-variant text-xs transition-colors"
              >
                <BookIcon className="w-3.5 h-3.5" />
                <span>FastAPI Docs</span>
              </a>
              <a
                href="http://127.0.0.1:8001/openapi.json"
                target="_blank"
                rel="noreferrer"
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-on-surface-variant text-xs transition-colors"
              >
                <SchemaIcon className="w-3.5 h-3.5" />
                <span>OpenAPI Spec</span>
              </a>
            </div>
          </div>
        </div>

        {/* Collapsible Issue Intake Form */}
        {showForm && (
          <form
            onSubmit={handleSubmit}
            className="border-t border-outline-variant/30 pt-space-lg flex flex-col gap-space-md"
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
              <div className="md:col-span-2 flex flex-col gap-1.5">
                <label className="text-xs font-mono uppercase tracking-wider text-on-surface-variant">
                  GitHub Repository (owner/repo or GitHub Issue URL) *
                </label>
                <input
                  type="text"
                  value={repo}
                  onChange={(e) => handleRepoChange(e.target.value)}
                  placeholder="owner/repo or https://github.com/owner/repo/issues/1"
                  className="px-3 py-2 rounded-lg bg-surface-container-highest border border-outline-variant/40 text-sm text-on-surface font-mono focus:outline-none focus:border-primary"
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-mono uppercase tracking-wider text-on-surface-variant">
                  Issue Number (optional)
                </label>
                <input
                  type="number"
                  min={1}
                  value={issueNumber}
                  onChange={(e) => setIssueNumber(e.target.value)}
                  placeholder="1"
                  className="px-3 py-2 rounded-lg bg-surface-container-highest border border-outline-variant/40 text-sm text-on-surface font-mono focus:outline-none focus:border-primary"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-on-surface-variant">
                Issue Title *
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Fix ZeroDivisionError in calculation handler"
                className="px-3 py-2 rounded-lg bg-surface-container-highest border border-outline-variant/40 text-sm text-on-surface focus:outline-none focus:border-primary"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono uppercase tracking-wider text-on-surface-variant">
                Issue Description / Body *
              </label>
              <textarea
                rows={4}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Describe the bug, expected behavior, or feature request..."
                className="px-3 py-2 rounded-lg bg-surface-container-highest border border-outline-variant/40 text-sm text-on-surface focus:outline-none focus:border-primary"
                required
              />
            </div>

            {error && (
              <div className="px-3 py-2 rounded-lg bg-error-container/30 border border-error/40 text-error text-xs font-mono">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-space-sm">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface-variant text-xs font-medium hover:text-on-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-primary-container text-on-primary-container font-semibold text-xs cursor-pointer disabled:opacity-50"
              >
                <PlayIcon className="w-3.5 h-3.5" />
                <span>{submitting ? 'Starting Autonomous Run...' : 'Submit Issue & Start Run'}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
};
