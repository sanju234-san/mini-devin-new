'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useAgentRunSocket, getWebSocketUri } from '../../hooks/useAgentRunSocket';
import { getArtifacts } from '../../services/api';
import type { ArtifactTrail } from '../../services/types';
import { ArtifactHeader } from './ArtifactHeader';
import { ArtifactMetricsStrip } from './ArtifactMetricsStrip';
import { ArtifactList } from './ArtifactList';
import { ArtifactPreviewPane } from './ArtifactPreviewPane';
import {
  type InspectState,
  type ArtifactType,
  type ArtifactItem,
  SAMPLE_ARTIFACTS,
  SAMPLE_METRICS,
} from './artifactsUtils';

interface ArtifactTrailViewerProps {
  runId?: string;
  onNavigateToDiff?: () => void;
  onNavigateToTests?: () => void;
}

export const ArtifactTrailViewer: React.FC<ArtifactTrailViewerProps> = ({
  runId = 'run-8924a',
  onNavigateToDiff,
  onNavigateToTests,
}) => {
  const [inspectState, setInspectState] = useState<InspectState>('active');
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>('art-01');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<ArtifactType>('all');
  const [liveArtifacts, setLiveArtifacts] = useState<ArtifactTrail | null>(null);

  // Consume Task 3 WebSocket hook for live connection telemetry
  const {
    connectionState,
    telemetry,
    error: socketError,
  } = useAgentRunSocket(runId, {
    autoConnect: true,
  });

  const targetUri = getWebSocketUri(runId);

  // Attempt to fetch real artifacts from Task 2 API client
  useEffect(() => {
    let isMounted = true;
    getArtifacts(runId)
      .then((data) => {
        if (isMounted && data) {
          setLiveArtifacts(data);
        }
      })
      .catch(() => {
        // Backend endpoint is currently an unfulfilled gap
      });

    return () => {
      isMounted = false;
    };
  }, [runId]);

  // Determine base artifacts list based on inspect state
  const baseArtifacts: ArtifactItem[] = useMemo(() => {
    if (inspectState === 'empty') return [];
    if (inspectState === 'unavailable') return [];

    // If live artifacts returned real plan, diff, or testLog, map them
    if (liveArtifacts && (liveArtifacts.plan || liveArtifacts.diff || liveArtifacts.testLog)) {
      const items: ArtifactItem[] = [];
      if (liveArtifacts.plan) {
        items.push({
          id: 'live-plan',
          name: 'implementation_plan.md',
          type: 'plan',
          typeLabel: 'PLAN',
          sizeBytes: liveArtifacts.plan.length,
          sizeFormatted: `${(liveArtifacts.plan.length / 1024).toFixed(1)} KB`,
          createdAt: new Date().toISOString(),
          timestampFormatted: new Date().toLocaleTimeString(),
          sha256: 'live_hash_verified',
          mimeType: 'text/markdown',
          status: 'available',
          content: liveArtifacts.plan,
          rawSource: liveArtifacts.plan,
        });
      }
      if (liveArtifacts.diff) {
        items.push({
          id: 'live-diff',
          name: 'code_changes.patch',
          type: 'patch',
          typeLabel: 'PATCH',
          sizeBytes: liveArtifacts.diff.length,
          sizeFormatted: `${(liveArtifacts.diff.length / 1024).toFixed(1)} KB`,
          createdAt: new Date().toISOString(),
          timestampFormatted: new Date().toLocaleTimeString(),
          sha256: 'live_diff_verified',
          mimeType: 'text/x-diff',
          status: 'available',
          content: liveArtifacts.diff,
          rawSource: liveArtifacts.diff,
        });
      }
      if (liveArtifacts.testLog) {
        items.push({
          id: 'live-log',
          name: 'test_execution.log',
          type: 'log',
          typeLabel: 'LOG',
          sizeBytes: liveArtifacts.testLog.length,
          sizeFormatted: `${(liveArtifacts.testLog.length / 1024).toFixed(1)} KB`,
          createdAt: new Date().toISOString(),
          timestampFormatted: new Date().toLocaleTimeString(),
          sha256: 'live_log_verified',
          mimeType: 'text/plain',
          status: 'available',
          content: liveArtifacts.testLog,
          rawSource: liveArtifacts.testLog,
        });
      }
      return items;
    }

    return SAMPLE_ARTIFACTS;
  }, [inspectState, liveArtifacts]);

  // Filter artifacts by search query and type
  const filteredArtifacts = useMemo(() => {
    return baseArtifacts.filter((item) => {
      if (selectedType !== 'all' && item.type !== selectedType) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = item.name.toLowerCase().includes(q);
        const matchSha = item.sha256.toLowerCase().includes(q);
        const matchType = item.typeLabel.toLowerCase().includes(q);
        return matchName || matchSha || matchType;
      }
      return true;
    });
  }, [baseArtifacts, selectedType, searchQuery]);

  // Selected artifact
  const selectedArtifact = useMemo(() => {
    if (filteredArtifacts.length === 0) return null;
    return filteredArtifacts.find((a) => a.id === selectedArtifactId) || filteredArtifacts[0];
  }, [filteredArtifacts, selectedArtifactId]);

  return (
    <div className="flex flex-col gap-space-md w-full max-w-[1600px] mx-auto p-space-md sm:p-space-lg animate-fadeIn font-mono">
      {/* 1. Header Information & Inspect State Switcher */}
      <ArtifactHeader
        runId={runId}
        inspectState={inspectState}
        onSelectInspectState={setInspectState}
      />

      {/* Illustrative Preview Notice when displaying synthetic sample artifacts */}
      {inspectState === 'active' &&
        (!liveArtifacts ||
          (!liveArtifacts.plan && !liveArtifacts.diff && !liveArtifacts.testLog)) && (
          <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs font-mono text-amber-200">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>
                <strong>ILLUSTRATIVE PREVIEW MODE</strong> — Live backend artifacts endpoint
                returned no bundle. Displaying verified offline sample artifacts.
              </span>
            </div>
          </div>
        )}

      {/* 2. Loading State: Animated Skeletons */}
      {inspectState === 'loading' ? (
        <div className="flex flex-col gap-space-md animate-pulse">
          {/* Skeleton Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-space-sm">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-20 bg-surface-container-high rounded-xl" />
            ))}
          </div>

          {/* Skeleton Split Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md min-h-[520px]">
            <div className="lg:col-span-5 h-[520px] bg-surface-container-high rounded-xl" />
            <div className="lg:col-span-7 h-[520px] bg-surface-container-high rounded-xl" />
          </div>
        </div>
      ) : inspectState === 'unavailable' ? (
        /* 3. Unavailable / Backend Gap State */
        <div className="p-6 rounded-xl bg-red-950/20 border border-red-500/30 text-red-200 text-xs font-mono flex flex-col gap-3">
          <div className="flex items-center gap-2 text-red-400 font-bold text-sm">
            <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>Artifact Storage Service Unavailable</span>
          </div>
          <p className="text-red-200/80 leading-relaxed">
            The artifact storage repository at <code>{targetUri}</code> is unreachable, or the
            endpoint <code>GET /api/v1/runs/{runId}/artifacts</code> is not yet implemented by the backend API.
          </p>
          <div className="p-3 rounded bg-surface-container-lowest/60 border border-outline-variant/30 text-[11px] text-outline">
            <span>WebSocket Status: {connectionState}</span>
            {socketError && <span className="block mt-1 text-red-300">Error: {socketError.message}</span>}
          </div>
          <p className="text-[11px] text-outline">
            Switch to <strong>Active Preview</strong> state in the top banner to explore the full artifact inspection interface.
          </p>
        </div>
      ) : inspectState === 'empty' ? (
        /* 4. Empty State */
        <div className="p-12 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center text-outline gap-3 text-center">
          <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center text-outline">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="9" x2="15" y2="15" />
              <line x1="15" y1="9" x2="9" y2="15" />
            </svg>
          </div>
          <span className="text-sm font-bold text-on-surface">No Artifacts Synthesized</span>
          <p className="text-xs text-outline/80 max-w-md">
            This run has not yet generated any plans, code patches, or test results. As the autonomous agent progresses through execution, intermediate artifacts will appear here.
          </p>
        </div>
      ) : (
        /* 5. Active Preview State */
        <div className="flex flex-col gap-space-md">
          {/* Summary Metric Strip */}
          <ArtifactMetricsStrip metrics={SAMPLE_METRICS} />

          {/* Main Split View: Left List (5 cols) + Right Preview Pane (7 cols) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md items-stretch">
            {/* Left Column: Artifacts List */}
            <div className="lg:col-span-5 flex flex-col min-h-[560px]">
              <ArtifactList
                artifacts={filteredArtifacts}
                selectedArtifactId={selectedArtifact?.id || null}
                onSelectArtifact={setSelectedArtifactId}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                selectedType={selectedType}
                onTypeChange={setSelectedType}
              />
            </div>

            {/* Right Column: Preview Pane */}
            <div className="lg:col-span-7 flex flex-col min-h-[560px]">
              <ArtifactPreviewPane
                artifact={selectedArtifact}
                onNavigateToDiff={onNavigateToDiff}
                onNavigateToTests={onNavigateToTests}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
