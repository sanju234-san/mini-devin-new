'use client';

import React, { useState } from 'react';
import { AppShell } from '../components/layout/AppShell';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { EmptyStatePanel } from '../components/dashboard/EmptyStatePanel';
import { RestClientStateSection } from '../components/rest/RestClientStateSection';
import { ConnectionMonitorSection } from '../components/websocket/ConnectionMonitorSection';
import { CapabilitiesGrid } from '../components/dashboard/CapabilitiesGrid';
import { FooterStrip } from '../components/dashboard/FooterStrip';
import { LiveConsole } from '../components/LiveConsole';
import { PlanApproval } from '../components/PlanApproval';
import { DiffViewer } from '../components/DiffViewer';
import { TestsAndPreview } from '../components/TestsAndPreview';
import { ArtifactTrailViewer } from '../components/Artifacts';
import { TransparencyDashboard } from '../components/Transparency';
import { EvalResults } from '../components/EvalResults';
import { TerminalIcon, GridIcon, ChecklistIcon, DiffIcon, ScienceIcon, FolderZipIcon, EyeIcon, MonitoringIcon } from '../components/icons/Icons';

type NavView = 'dashboard' | 'live-console' | 'plan-approval' | 'diff-viewer' | 'tests-and-preview' | 'artifacts' | 'transparency' | 'evaluation';

export default function DashboardPage() {
  const [activeNav, setActiveNav] = useState<NavView>('dashboard');

  return (
    <AppShell
      activeNav={activeNav}
      onSelectNav={(id) => {
        if (
          id === 'dashboard' ||
          id === 'live-console' ||
          id === 'plan-approval' ||
          id === 'diff-viewer' ||
          id === 'tests-and-preview' ||
          id === 'artifacts' ||
          id === 'transparency' ||
          id === 'evaluation'
        ) {
          setActiveNav(id as NavView);
        }
      }}
    >
      {/* Top View Toggle Banner for immediate visibility and testing */}
      <div className="bg-surface-container-low/70 border-b border-outline-variant/20 px-space-md py-2 flex items-center w-full min-w-0">
        <div className="flex items-center gap-2.5 w-full min-w-0">
          <span className="text-xs text-on-surface-variant font-mono shrink-0 select-none">View:</span>
          <div className="flex-1 min-w-0 overflow-x-auto py-0.5">
            <div className="inline-flex rounded-lg bg-surface-container-high p-0.5 border border-outline-variant/30 flex-nowrap shrink-0 gap-0.5">
              <button
                type="button"
                onClick={() => setActiveNav('dashboard')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'dashboard'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <GridIcon className="w-3.5 h-3.5" />
                <span>Dashboard (Tasks 1–3)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('live-console')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'live-console'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <TerminalIcon className="w-3.5 h-3.5" />
                <span>Live Console (Task 4)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('plan-approval')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'plan-approval'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <ChecklistIcon className="w-3.5 h-3.5" />
                <span>Plan Approval (Task 5)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('diff-viewer')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'diff-viewer'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <DiffIcon className="w-3.5 h-3.5" />
                <span>Diff Viewer (Task 6)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('tests-and-preview')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'tests-and-preview'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <ScienceIcon className="w-3.5 h-3.5" />
                <span>Tests & Preview (Task 7)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('artifacts')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'artifacts'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <FolderZipIcon className="w-3.5 h-3.5" />
                <span>Artifacts (Task 8)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('transparency')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'transparency'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <EyeIcon className="w-3.5 h-3.5" />
                <span>Transparency (Task 9)</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveNav('evaluation')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium shrink-0 whitespace-nowrap transition-colors ${
                  activeNav === 'evaluation'
                    ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <MonitoringIcon className="w-3.5 h-3.5" />
                <span>Evaluation (Task 10)</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {activeNav === 'evaluation' ? (
        <EvalResults onNavigateToDiff={() => setActiveNav('diff-viewer')} />
      ) : activeNav === 'transparency' ? (
        <TransparencyDashboard />
      ) : activeNav === 'artifacts' ? (
        <ArtifactTrailViewer
          onNavigateToDiff={() => setActiveNav('diff-viewer')}
          onNavigateToTests={() => setActiveNav('tests-and-preview')}
        />
      ) : activeNav === 'tests-and-preview' ? (
        <TestsAndPreview onNavigateToDiff={() => setActiveNav('diff-viewer')} />
      ) : activeNav === 'diff-viewer' ? (
        <DiffViewer />
      ) : activeNav === 'plan-approval' ? (
        <div className="p-space-md sm:p-space-lg max-w-[1600px] mx-auto w-full">
          <PlanApproval />
        </div>
      ) : activeNav === 'live-console' ? (
        <div className="p-space-md sm:p-space-lg max-w-[1600px] mx-auto w-full">
          <LiveConsole />
        </div>
      ) : (
        <div className="flex flex-col w-full">
          <div className="p-space-lg md:p-space-xl flex flex-col gap-space-xl max-w-7xl mx-auto w-full">
            {/* 1. Dashboard Header */}
            <DashboardHeader />

            {/* 2. Initial / Empty State Banner with Pipeline Visualization */}
            <EmptyStatePanel />

            {/* 3. REST Client State Orchestration (Task 2) */}
            <RestClientStateSection />

            {/* 4. WebSocket Client & Connection Monitor (Task 3) */}
            <ConnectionMonitorSection />

            {/* 5. Platform Capabilities & Subsystems Grid */}
            <CapabilitiesGrid />

            {/* 6. Architecture Footer Note */}
            <FooterStrip />
          </div>
        </div>
      )}
    </AppShell>
  );
}
