'use client';

import React from 'react';
import type { ArtifactItem, ArtifactType } from './artifactsUtils';

interface ArtifactListProps {
  artifacts: ArtifactItem[];
  selectedArtifactId: string | null;
  onSelectArtifact: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedType: ArtifactType;
  onTypeChange: (type: ArtifactType) => void;
  quotaUsedMb?: number;
  quotaTotalMb?: number;
}

export const ArtifactList: React.FC<ArtifactListProps> = ({
  artifacts,
  selectedArtifactId,
  onSelectArtifact,
  searchQuery,
  onSearchChange,
  selectedType,
  onTypeChange,
  quotaUsedMb = 2.4,
  quotaTotalMb = 50,
}) => {
  const quotaPercentage = ((quotaUsedMb / quotaTotalMb) * 100).toFixed(1);

  return (
    <div className="flex flex-col h-full rounded-xl bg-surface-container-low border border-outline-variant/30 overflow-hidden shadow-xs font-mono text-xs">
      {/* 1. Search Bar */}
      <div className="p-space-sm border-b border-outline-variant/20 bg-surface-container-high/40">
        <div className="relative w-full">
          <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-outline">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter by name, hash, ext..."
            className="w-full pl-8 pr-8 py-1.5 bg-surface-container-lowest border border-outline-variant/30 rounded text-xs font-mono text-on-surface placeholder:text-outline/60 focus:outline-hidden focus:border-primary transition-colors"
          />
          <div className="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none">
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-surface-container text-outline border border-outline-variant/20">
              ⌘K
            </span>
          </div>
        </div>
      </div>

      {/* 2. Type Filter Controls Bar */}
      <div className="px-space-md py-2 border-b border-outline-variant/20 flex items-center justify-between gap-2 bg-surface-container-low">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-[11px] text-outline uppercase tracking-wider">TYPE:</span>
          <select
            value={selectedType}
            onChange={(e) => onTypeChange(e.target.value as ArtifactType)}
            className="bg-surface-container border border-outline-variant/30 text-on-surface text-xs rounded px-2 py-0.5 focus:outline-hidden focus:border-primary cursor-pointer truncate"
          >
            <option value="all">All Types ({artifacts.length})</option>
            <option value="plan">Plans &amp; Docs</option>
            <option value="patch">Code Patches</option>
            <option value="test_suite">Test Suites</option>
            <option value="log">Logs &amp; Streams</option>
            <option value="image">Screenshots</option>
            <option value="manifest">AST &amp; Manifests</option>
            <option value="expired">Expired / Purged</option>
          </select>
        </div>

        <div className="flex items-center gap-1 text-outline">
          <button
            type="button"
            className="p-1 hover:text-on-surface rounded hover:bg-surface-container transition-colors"
            title="Sort artifacts"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m3 16 4 4 4-4" />
              <path d="M7 20V4" />
              <path d="m21 8-4-4-4 4" />
              <path d="M17 4v16" />
            </svg>
          </button>
        </div>
      </div>

      {/* 3. Artifact Items List */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1 max-h-[580px]">
        {artifacts.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-outline gap-2 text-center px-4">
            <svg className="w-8 h-8 text-outline/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span className="text-xs">No artifacts match your filter.</span>
            <span className="text-[11px] text-outline/60">Try clearing the search query or selecting &quot;All Types&quot;.</span>
          </div>
        ) : (
          artifacts.map((art) => {
            const isSelected = art.id === selectedArtifactId;
            const isPurged = art.status === 'purged';

            return (
              <button
                key={art.id}
                type="button"
                onClick={() => onSelectArtifact(art.id)}
                className={`w-full text-left p-2.5 rounded-lg border transition-all flex flex-col gap-1.5 ${
                  isSelected
                    ? 'bg-primary-container/15 border-primary/40 shadow-xs'
                    : isPurged
                    ? 'bg-surface-container-lowest/40 border-outline-variant/15 opacity-60 hover:opacity-80'
                    : 'bg-surface-container-lowest/70 border-outline-variant/20 hover:border-outline-variant/40 hover:bg-surface-container'
                }`}
              >
                {/* Header: Name + Type Badge */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-outline shrink-0">
                      {art.type === 'plan' ? (
                        <svg className="w-3.5 h-3.5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                      ) : art.type === 'patch' ? (
                        <svg className="w-3.5 h-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <line x1="12" y1="18" x2="12" y2="12" />
                          <line x1="9" y1="15" x2="15" y2="15" />
                        </svg>
                      ) : art.type === 'test_suite' ? (
                        <svg className="w-3.5 h-3.5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="9 11 12 14 22 4" />
                          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                        </svg>
                      ) : art.type === 'log' ? (
                        <svg className="w-3.5 h-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="4 17 10 11 4 5" />
                          <line x1="12" y1="19" x2="20" y2="19" />
                        </svg>
                      ) : art.type === 'image' ? (
                        <svg className="w-3.5 h-3.5 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                          <circle cx="8.5" cy="8.5" r="1.5" />
                          <polyline points="21 15 16 10 5 21" />
                        </svg>
                      ) : art.type === 'manifest' ? (
                        <svg className="w-3.5 h-3.5 text-teal-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="16 18 22 12 16 6" />
                          <polyline points="8 6 2 12 8 18" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                          <line x1="12" y1="9" x2="12" y2="13" />
                          <line x1="12" y1="17" x2="12.01" y2="17" />
                        </svg>
                      )}
                    </span>
                    <span
                      className={`font-mono text-xs font-semibold truncate ${
                        isSelected
                          ? 'text-primary'
                          : isPurged
                          ? 'text-outline/70 line-through'
                          : 'text-on-surface'
                      }`}
                    >
                      {art.name}
                    </span>
                  </div>

                  {/* Type Label Badge */}
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-bold tracking-wider shrink-0 uppercase ${
                      art.type === 'plan'
                        ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                        : art.type === 'patch'
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : art.type === 'test_suite'
                        ? 'bg-blue-500/15 text-blue-300 border border-blue-500/30'
                        : art.type === 'log'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                        : art.type === 'image'
                        ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30'
                        : art.type === 'manifest'
                        ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30'
                        : 'bg-red-500/15 text-red-400 border border-red-500/30'
                    }`}
                  >
                    {art.typeLabel}
                  </span>
                </div>

                {/* Subtitle: Size • Timestamp • Metadata */}
                <div className="flex items-center justify-between gap-2 text-[11px] text-outline">
                  <div className="flex items-center gap-1.5 truncate">
                    <span>{art.sizeFormatted}</span>
                    <span className="text-outline-variant">•</span>
                    {art.diffSummary ? (
                      <span className="text-emerald-400">
                        +{art.diffSummary.added} / -{art.diffSummary.deleted}
                      </span>
                    ) : art.testSummary ? (
                      <span>
                        <span className="text-emerald-400">{art.testSummary.passed} pass</span>{' '}
                        <span className="text-red-400">{art.testSummary.failed} fail</span>
                      </span>
                    ) : art.imageResolution ? (
                      <span>{art.imageResolution}</span>
                    ) : isPurged ? (
                      <span className="text-red-400/80">Purged • Policy TTL</span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span>sha:{art.sha256.substring(0, 7)}</span>
                      </span>
                    )}
                  </div>

                  <span className="text-outline/70 shrink-0">{art.timestampFormatted}</span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* 4. List Footer: Item count & Storage Quota */}
      <div className="p-space-sm bg-surface-container-high/60 border-t border-outline-variant/20 flex items-center justify-between text-[11px] text-outline">
        <span>Showing {artifacts.length} of {artifacts.length}</span>
        <div className="flex items-center gap-1">
          <span>Quota: {quotaUsedMb} / {quotaTotalMb} MB</span>
          <span className="text-primary font-semibold">({quotaPercentage}%)</span>
        </div>
      </div>
    </div>
  );
};
