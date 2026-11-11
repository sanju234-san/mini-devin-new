'use client';

import React, { useState } from 'react';
import { ingestIssue } from '../../services/api';
import {
  TerminalIcon,
  ChecklistIcon,
  DiffIcon,
  ScienceIcon,
  BranchIcon,
  LockIcon,
} from '../icons/Icons';

export type WorkbenchTargetView =
  | 'dashboard'
  | 'live-console'
  | 'plan-approval'
  | 'diff-viewer'
  | 'tests-and-preview'
  | 'pull-request'
  | 'artifacts'
  | 'transparency'
  | 'evaluation';

export interface LandingPageProps {
  onOpenWorkbench: (targetView?: WorkbenchTargetView, newRunId?: string) => void;
}

function parseIssueUrlOrRepo(input: string): {
  repo: string;
  issueNumber: number;
  title: string;
  body: string;
} {
  const trimmed = input.trim();
  const urlMatch = trimmed.match(
    /(?:https?:\/\/)?(?:www\.)?github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+?)(?:\.git)?(?:\/issues\/(\d+))?(?:\/.*)?$/i
  );
  if (urlMatch && urlMatch[1]) {
    const repo = urlMatch[1];
    const num = urlMatch[2] ? parseInt(urlMatch[2], 10) : 1;
    return {
      repo,
      issueNumber: !Number.isNaN(num) && num >= 1 ? num : 1,
      title: `Resolve GitHub Issue #${!Number.isNaN(num) && num >= 1 ? num : 1} in ${repo}`,
      body: `Autonomous resolution triggered from Mini-Devin Landing Command Bar for ${trimmed}`,
    };
  }
  return {
    repo: trimmed || 'sanjeev23oct/mini-devin',
    issueNumber: 1,
    title: trimmed ? `Resolve: ${trimmed}` : 'Autonomous Issue Resolution',
    body: `Autonomous resolution triggered for ${trimmed || 'sanjeev23oct/mini-devin'}`,
  };
}

const PIPELINE_NODES = [
  { step: '01', name: 'Triage', sub: 'DistilBERT', active: true },
  { step: '02', name: 'Retrieval', sub: 'FAISS + BM25', active: true },
  { step: '03', name: 'Planner', sub: 'LLM Synthesis', active: true },
  { step: '04', name: 'Human Gate', sub: 'SHA-256 Hash', active: true, highlight: true },
  { step: '05', name: 'Coder', sub: 'AST Patch', active: true },
  { step: '06', name: 'Sandbox', sub: 'Pytest Runner', active: true },
  { step: '07', name: 'Reviewer', sub: '6-Dim Rubric', active: true },
  { step: '08', name: 'PR Ready', sub: 'GitHub REST', active: true, emerald: true },
];

export const LandingPage: React.FC<LandingPageProps> = ({ onOpenWorkbench }) => {
  const [issueInput, setIssueInput] = useState('');
  const [isLaunching, setIsLaunching] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleQuickLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issueInput.trim()) {
      onOpenWorkbench('dashboard');
      return;
    }
    setIsLaunching(true);
    setErrorMsg(null);
    try {
      const parsed = parseIssueUrlOrRepo(issueInput);
      const run = await ingestIssue({
        repo: parsed.repo,
        issue_number: parsed.issueNumber,
        title: parsed.title,
        body: parsed.body,
      });
      onOpenWorkbench('live-console', run.id);
    } catch (err) {
      const msg =
        err && typeof err === 'object' && 'message' in err && typeof (err as { message: unknown }).message === 'string'
          ? (err as { message: string }).message
          : 'Could not reach backend — opening Workbench Dashboard.';
      setErrorMsg(msg);
      setTimeout(() => onOpenWorkbench('dashboard'), 900);
    } finally {
      setIsLaunching(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#050508] text-[#e5e1e7] relative overflow-x-hidden selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Ambient Aurora Radial Glows (Synthetic Monolith Palette) */}
      <div className="pointer-events-none fixed top-[-180px] left-1/2 -translate-x-1/2 w-[980px] h-[520px] rounded-full bg-gradient-to-tr from-[#6366f1]/20 via-[#a855f7]/15 to-[#22d3ee]/10 blur-[130px] z-0" />
      <div className="pointer-events-none fixed bottom-[-240px] left-1/3 w-[720px] h-[420px] rounded-full bg-[#6366f1]/10 blur-[140px] z-0" />

      {/* 1. Floating Glassmorphic Pill Navbar */}
      <header className="sticky top-5 z-50 px-4 flex justify-center">
        <nav className="w-full max-w-4xl flex items-center justify-between px-5 py-2.5 rounded-full border border-white/[0.08] bg-[#0b0b12]/80 backdrop-blur-2xl shadow-[0_16px_40px_-12px_rgba(0,0,0,0.85)]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-white font-mono text-xs font-bold shadow-[0_0_16px_rgba(99,102,241,0.5)]">
              M
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">Mini-Devin</span>
            <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-medium bg-white/[0.05] border border-white/[0.08] text-indigo-300">
              v0.9
            </span>
          </div>

          <div className="hidden md:flex items-center gap-6 text-xs text-slate-400">
            <a href="#workflow" className="hover:text-white transition-colors">
              Workflow
            </a>
            <button
              type="button"
              onClick={() => onOpenWorkbench('plan-approval')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              Plan Gate
            </button>
            <button
              type="button"
              onClick={() => onOpenWorkbench('diff-viewer')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              AST Guardrails
            </button>
            <button
              type="button"
              onClick={() => onOpenWorkbench('pull-request')}
              className="hover:text-white transition-colors cursor-pointer"
            >
              Verified PRs
            </button>
          </div>

          <button
            type="button"
            onClick={() => onOpenWorkbench('dashboard')}
            className="px-4 py-1.5 rounded-full bg-white text-[#050508] hover:bg-slate-200 font-medium text-xs transition-all shadow-[0_0_20px_rgba(255,255,255,0.2)] cursor-pointer"
          >
            Open Workbench →
          </button>
        </nav>
      </header>

      {/* 2. Hero Section */}
      <main className="relative z-10 max-w-6xl mx-auto px-6 pt-16 pb-24 flex flex-col items-center text-center">
        {/* Eyebrow Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.08] mb-6">
          <span className="w-2 h-2 rounded-full bg-[#22d3ee] animate-pulse" />
          <span className="font-mono text-[11px] uppercase tracking-wider text-slate-300">
            Mini-Devin 0.9 • AST-Verified Autonomous SWE Engine
          </span>
        </div>

        {/* Display Headline */}
        <h1 className="text-4xl sm:text-6xl font-semibold tracking-tight text-white max-w-4xl leading-[1.12] mb-5">
          Autonomous Software Engineering,{' '}
          <span className="bg-gradient-to-r from-[#c0c1ff] via-[#ddb7ff] to-[#2fd9f4] bg-clip-text text-transparent">
            Verified by AST &amp; Sandboxed Tests.
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed mb-9">
          Mini-Devin ingests GitHub issues, retrieves repository context via FAISS + BM25,
          synthesizes human-approved plans with SHA-256 hashes, writes AST-validated patches,
          and executes isolated pytest suites to ship ready-to-merge Pull Requests.
        </p>

        {/* Raycast-Style Issue Command Bar */}
        <form
          onSubmit={handleQuickLaunch}
          className="w-full max-w-2xl flex flex-col sm:flex-row items-stretch sm:items-center gap-2 p-2 rounded-2xl bg-[#0c0d14]/90 border border-white/[0.1] shadow-[0_0_50px_-10px_rgba(99,102,241,0.28)] mb-4"
        >
          <div className="flex items-center gap-2.5 flex-1 px-3 py-2">
            <TerminalIcon className="w-4 h-4 text-[#22d3ee] shrink-0" />
            <input
              type="text"
              value={issueInput}
              onChange={(e) => setIssueInput(e.target.value)}
              placeholder="Paste a GitHub Issue URL (e.g. https://github.com/owner/repo/issues/429)..."
              className="w-full bg-transparent text-xs sm:text-sm font-mono text-white placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={isLaunching}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#a855f7] hover:opacity-95 text-white font-medium text-xs sm:text-sm shadow-[0_0_20px_rgba(99,102,241,0.4)] transition-all cursor-pointer shrink-0 disabled:opacity-60"
          >
            {isLaunching ? 'Launching Run...' : 'Run Agent ↵'}
          </button>
        </form>

        {errorMsg && (
          <p className="text-xs font-mono text-amber-300 mb-3">{errorMsg}</p>
        )}

        {/* Quick Preset Chips & Direct Workbench Actions */}
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs font-mono text-slate-400 mb-14">
          <span className="text-[11px] text-slate-500">Quick launch:</span>
          <button
            type="button"
            onClick={() => setIssueInput('https://github.com/PUDUCAN-JIPMER/puducan-jipmer/issues/429')}
            className="px-2.5 py-1 rounded-full bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 transition-colors cursor-pointer"
          >
            #429 Audit Log Trail
          </button>
          <button
            type="button"
            onClick={() => setIssueInput('https://github.com/PUDUCAN-JIPMER/puducan-jipmer/issues/422')}
            className="px-2.5 py-1 rounded-full bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 transition-colors cursor-pointer"
          >
            #422 Navbar Responsiveness
          </button>
          <button
            type="button"
            onClick={() => onOpenWorkbench('live-console')}
            className="px-2.5 py-1 rounded-full bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 transition-colors cursor-pointer"
          >
            Explore Live Console →
          </button>
        </div>

        {/* 3. LangGraph 8-Agent Workflow Visual Board */}
        <section
          id="workflow"
          className="w-full rounded-3xl border border-white/[0.08] bg-[#0b0c14]/85 backdrop-blur-xl p-6 sm:p-8 shadow-2xl text-left mb-16"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 pb-5 mb-6 border-b border-white/[0.06]">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-mono text-xs uppercase tracking-wider text-slate-300 font-semibold">
                LangGraph 8-Stage Autonomous State Machine
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] text-slate-400">
              <span className="px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08]">
                AST Guard: ENABLED
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                53 / 53 Unit Tests Passing
              </span>
            </div>
          </div>

          {/* 8 Nodes Pipeline Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 mb-6">
            {PIPELINE_NODES.map((node) => (
              <div
                key={node.step}
                className={`p-3 rounded-xl border transition-all flex flex-col justify-between ${
                  node.emerald
                    ? 'bg-emerald-500/10 border-emerald-500/30'
                    : node.highlight
                    ? 'bg-indigo-500/15 border-indigo-400/40 shadow-[0_0_20px_rgba(99,102,241,0.2)]'
                    : 'bg-white/[0.02] border-white/[0.07]'
                }`}
              >
                <div className="flex items-center justify-between font-mono text-[10px] text-slate-400 mb-2">
                  <span>{node.step}</span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      node.emerald
                        ? 'bg-emerald-400'
                        : node.highlight
                        ? 'bg-indigo-400 animate-ping'
                        : 'bg-[#22d3ee]'
                    }`}
                  />
                </div>
                <div className="font-semibold text-xs text-white truncate">{node.name}</div>
                <div className="font-mono text-[10px] text-slate-400 truncate mt-0.5">
                  {node.sub}
                </div>
              </div>
            ))}
          </div>

          {/* Live Telemetry Readout Bar */}
          <div className="rounded-xl bg-[#06070c] border border-white/[0.06] p-4 font-mono text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-slate-300 truncate">
              <span className="text-[#22d3ee]">[langgraph:stream]</span>
              <span className="truncate">
                triage → retrieval → planner → approval_gate (SHA-256 frozen) → coder → sandbox → pr
              </span>
            </div>
            <button
              type="button"
              onClick={() => onOpenWorkbench('live-console')}
              className="text-indigo-300 hover:text-white underline shrink-0 cursor-pointer"
            >
              Inspect Live Telemetry →
            </button>
          </div>
        </section>

        {/* 4. Visual-First Feature Showcase Cards (3-Card Row) */}
        <section className="w-full grid grid-cols-1 md:grid-cols-3 gap-5 text-left mb-6">
          {/* Card 1: Plan Approval */}
          <div
            onClick={() => onOpenWorkbench('plan-approval')}
            className="group rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] hover:border-indigo-500/40 p-6 flex flex-col justify-between transition-all cursor-pointer"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-300">
                  <ChecklistIcon className="w-4 h-4" />
                </div>
                <span className="px-2.5 py-0.5 rounded-full font-mono text-[10px] bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
                  GATE 01 • SHA-256
                </span>
              </div>
              <h3 className="text-base font-semibold text-white mb-1.5">
                Human-in-the-Loop Plan Gate
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Every implementation plan is cryptographically hashed and paused for human inspection before any file is modified.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-[#07080e] border border-white/[0.06] font-mono text-[11px] text-slate-300 flex items-center justify-between">
              <span>plan_hash: 7cee92dd...</span>
              <span className="text-emerald-400 font-semibold">Approve →</span>
            </div>
          </div>

          {/* Card 2: Diff & Sandbox Pytest */}
          <div
            onClick={() => onOpenWorkbench('diff-viewer')}
            className="group rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] hover:border-cyan-500/40 p-6 flex flex-col justify-between transition-all cursor-pointer"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-300">
                  <DiffIcon className="w-4 h-4" />
                </div>
                <span className="px-2.5 py-0.5 rounded-full font-mono text-[10px] bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">
                  AST + DIFF VIEWER
                </span>
              </div>
              <h3 className="text-base font-semibold text-white mb-1.5">
                Side-by-Side Diff &amp; AST Check
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Inspect unified diffs with syntax-validated hunks, strict file-scope guardrails, and zero hallucinated edits.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-[#07080e] border border-white/[0.06] font-mono text-[11px] flex items-center justify-between">
              <span className="text-emerald-400">+76 additions</span>
              <span className="text-cyan-300">Inspect Diff →</span>
            </div>
          </div>

          {/* Card 3: One-Click Verified GitHub PR */}
          <div
            onClick={() => onOpenWorkbench('pull-request')}
            className="group rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] hover:border-emerald-500/40 p-6 flex flex-col justify-between transition-all cursor-pointer"
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300">
                  <BranchIcon className="w-4 h-4" />
                </div>
                <span className="px-2.5 py-0.5 rounded-full font-mono text-[10px] bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                  GH-PR-READY
                </span>
              </div>
              <h3 className="text-base font-semibold text-white mb-1.5">
                Verified GitHub Pull Requests
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Automatically pushes feature branches, attaches the 6-dimension review report, and opens a clean GitHub PR.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-[#07080e] border border-white/[0.06] font-mono text-[11px] flex items-center justify-between">
              <span className="text-slate-300">agent/issue-429 → main</span>
              <span className="text-emerald-400 font-semibold">Open PR →</span>
            </div>
          </div>
        </section>

        {/* 5. 2-Card Wide Split Row (Sandbox + Transparency) */}
        <section className="w-full grid grid-cols-1 md:grid-cols-2 gap-5 text-left mb-16">
          <div
            onClick={() => onOpenWorkbench('tests-and-preview')}
            className="rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] p-6 flex items-start justify-between gap-4 transition-all cursor-pointer"
          >
            <div>
              <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#22d3ee] uppercase mb-2">
                <ScienceIcon className="w-3.5 h-3.5" />
                <span>Isolated Sandbox Execution</span>
              </div>
              <h4 className="text-sm sm:text-base font-semibold text-white mb-1">
                Containerized Pytest &amp; Live App Preview
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Every generated patch is verified inside an isolated workspace snapshot with live stdout/stderr streaming.
              </p>
            </div>
            <span className="font-mono text-xs text-indigo-300 shrink-0 mt-1">View Tests →</span>
          </div>

          <div
            onClick={() => onOpenWorkbench('transparency')}
            className="rounded-2xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04] p-6 flex items-start justify-between gap-4 transition-all cursor-pointer"
          >
            <div>
              <div className="inline-flex items-center gap-2 font-mono text-[11px] text-purple-300 uppercase mb-2">
                <LockIcon className="w-3.5 h-3.5" />
                <span>Hybrid Model Routing</span>
              </div>
              <h4 className="text-sm sm:text-base font-semibold text-white mb-1">
                Ollama, Groq, Gemini &amp; DistilBERT Telemetry
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Full transparency over active tools, prompt/completion token budgets, and writer-blind review rubric scores.
              </p>
            </div>
            <span className="font-mono text-xs text-indigo-300 shrink-0 mt-1">Telemetry →</span>
          </div>
        </section>

        {/* 6. Call-to-Action Banner */}
        <section className="w-full rounded-3xl border border-indigo-500/30 bg-gradient-to-r from-[#111222] via-[#17132a] to-[#0e1726] p-8 sm:p-10 flex flex-col sm:flex-row items-center justify-between gap-6 text-left shadow-2xl">
          <div>
            <h2 className="text-xl sm:text-2xl font-semibold text-white mb-1.5">
              Ready to ship autonomous Pull Requests?
            </h2>
            <p className="text-xs sm:text-sm text-slate-300">
              Launch the full 9-tab Mini-Devin Workbench or stream live LangGraph agent events.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() => onOpenWorkbench('dashboard')}
              className="px-5 py-2.5 rounded-full bg-white text-[#050508] hover:bg-slate-200 font-semibold text-xs sm:text-sm transition-all cursor-pointer"
            >
              Start Autonomous Run →
            </button>
            <button
              type="button"
              onClick={() => onOpenWorkbench('live-console')}
              className="px-5 py-2.5 rounded-full bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.12] text-white font-medium text-xs sm:text-sm transition-all cursor-pointer"
            >
              Live Console
            </button>
          </div>
        </section>
      </main>

      {/* 7. Minimal Footer */}
      <footer className="relative z-10 border-t border-white/[0.06] py-6 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-slate-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Mini-Devin Autonomous SWE • All Agent Nodes Operational</span>
          </div>
          <div className="flex items-center gap-5">
            <button
              type="button"
              onClick={() => onOpenWorkbench('dashboard')}
              className="hover:text-slate-300 transition-colors cursor-pointer"
            >
              Workbench
            </button>
            <button
              type="button"
              onClick={() => onOpenWorkbench('artifacts')}
              className="hover:text-slate-300 transition-colors cursor-pointer"
            >
              Artifacts
            </button>
            <button
              type="button"
              onClick={() => onOpenWorkbench('evaluation')}
              className="hover:text-slate-300 transition-colors cursor-pointer"
            >
              Evaluation
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
};

