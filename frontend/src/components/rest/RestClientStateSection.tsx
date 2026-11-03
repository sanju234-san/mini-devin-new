'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSkeletonState } from './LoadingSkeletonState';
import { EmptyDatasetState } from './EmptyDatasetState';
import { NetworkErrorState } from './NetworkErrorState';
import { getRuns } from '../../services/api';
import type { RequestState, RunsListResponse } from '../../services/types';
import { API_BASE_URL } from '../../config/env';

type PreviewMode = 'overview' | 'loading' | 'empty' | 'error' | 'live';

export const RestClientStateSection: React.FC = () => {
  const [previewMode, setPreviewMode] = useState<PreviewMode>('overview');

  // Live request state driven by real api.ts call
  const [liveState, setLiveState] = useState<RequestState<RunsListResponse>>({
    status: 'idle',
  });
  const [isRetrying, setIsRetrying] = useState(false);

  const executeLiveRequest = useCallback(async () => {
    setLiveState({ status: 'loading' });
    setIsRetrying(true);

    try {
      const response = await getRuns();
      if (!response.runs || response.runs.length === 0) {
        setLiveState({ status: 'empty', data: response });
      } else {
        setLiveState({ status: 'success', data: response });
      }
    } catch (err) {
      setLiveState({
        status: 'error',
        error: err as RequestState<RunsListResponse>['error'],
      });
    } finally {
      setIsRetrying(false);
    }
  }, []);

  // Run live request on mount
  useEffect(() => {
    executeLiveRequest();
  }, [executeLiveRequest]);

  return (
    <section className="flex flex-col gap-space-lg pt-space-xs" aria-label="REST Client States">
      {/* Section Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-md pb-space-md border-b border-outline-variant/20">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-space-sm flex-wrap">
            <div className="w-7 h-7 rounded-lg bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-primary">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                <line x1="6" y1="6" x2="6.01" y2="6" />
                <line x1="6" y1="18" x2="6.01" y2="18" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-on-surface">
              REST Client State Orchestration
            </h2>
            <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-surface-container-high text-outline border border-outline-variant/30">
              Client Spec: RFC-7807
            </span>
          </div>
          <p className="text-sm text-on-surface-variant max-w-3xl">
            Demonstrating UI response states for <span className="text-primary font-mono text-xs">src/services/api.ts</span> error boundaries, suspense skeletons, and zero-run states across autonomous pipelines.
          </p>
        </div>

        {/* State Preview Switcher */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wider text-outline px-1">
            UI State Preview:
          </span>
          <div className="inline-flex p-1 rounded-lg bg-surface-container-low border border-outline-variant/30 text-xs">
            <button
              type="button"
              onClick={() => setPreviewMode('overview')}
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                previewMode === 'overview'
                  ? 'bg-primary-container text-on-primary-container shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Overview (All 3)
            </button>
            <button
              type="button"
              onClick={() => setPreviewMode('loading')}
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                previewMode === 'loading'
                  ? 'bg-primary-container text-on-primary-container shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              1. Loading
            </button>
            <button
              type="button"
              onClick={() => setPreviewMode('empty')}
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                previewMode === 'empty'
                  ? 'bg-primary-container text-on-primary-container shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              2. Empty
            </button>
            <button
              type="button"
              onClick={() => setPreviewMode('error')}
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                previewMode === 'error'
                  ? 'bg-primary-container text-on-primary-container shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              3. Error &amp; Retry
            </button>
            <button
              type="button"
              onClick={() => setPreviewMode('live')}
              className={`px-2.5 py-1 rounded font-medium transition-all ${
                previewMode === 'live'
                  ? 'bg-teal-500 text-surface-container-lowest font-semibold shadow-sm'
                  : 'text-teal-400 hover:text-teal-300'
              }`}
            >
              Live Request
            </button>
          </div>
        </div>
      </div>

      {/* Meta Telemetry Row */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-space-md py-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20 font-mono text-xs text-outline">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 text-[10px] font-semibold">
            ENDPOINT
          </span>
          <span className="text-on-surface">GET /api/v1/runs</span>
          <span className="text-outline-variant">|</span>
          <span className="text-outline-variant text-[11px]">
            Target Base: {API_BASE_URL}
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px]">
          <span>Single-Retry Policy</span>
          <span className="text-outline-variant">•</span>
          <span>Zero Auto-Polling</span>
        </div>
      </div>

      {/* Rendered Preview States */}
      {previewMode === 'overview' && (
        <div className="flex flex-col gap-space-lg">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-outline uppercase tracking-wider">
              Static Preview — State 01
            </span>
          </div>
          <LoadingSkeletonState />

          <div className="flex items-center justify-between pt-2">
            <span className="font-mono text-xs text-outline uppercase tracking-wider">
              Static Preview — State 02
            </span>
          </div>
          <EmptyDatasetState />

          <div className="flex items-center justify-between pt-2">
            <span className="font-mono text-xs text-outline uppercase tracking-wider">
              Static Preview — State 03
            </span>
          </div>
          <NetworkErrorState
            onRetry={executeLiveRequest}
            isRetrying={isRetrying}
          />
        </div>
      )}

      {previewMode === 'loading' && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-outline font-mono text-xs">
            <span>STATIC PREVIEW — LOADING SKELETON</span>
          </div>
          <LoadingSkeletonState />
        </div>
      )}

      {previewMode === 'empty' && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-outline font-mono text-xs">
            <span>STATIC PREVIEW — EMPTY DATASET</span>
          </div>
          <EmptyDatasetState />
        </div>
      )}

      {previewMode === 'error' && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-outline font-mono text-xs">
            <span>STATIC PREVIEW — NETWORK FAULT &amp; RETRY</span>
          </div>
          <NetworkErrorState
            onRetry={executeLiveRequest}
            isRetrying={isRetrying}
          />
        </div>
      )}

      {/* Live Request Driven Mode */}
      {previewMode === 'live' && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-space-md py-2 rounded-lg bg-surface-container-high/40 border border-outline-variant/30 text-xs font-mono">
            <span className="text-on-surface font-semibold flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  liveState.status === 'loading'
                    ? 'bg-amber-400 animate-ping'
                    : liveState.status === 'error'
                    ? 'bg-red-400'
                    : 'bg-emerald-400'
                }`}
              />
              Live Request Status: {liveState.status.toUpperCase()}
            </span>
            <button
              type="button"
              onClick={executeLiveRequest}
              disabled={isRetrying}
              className="text-primary hover:underline disabled:opacity-50"
            >
              Re-execute Request
            </button>
          </div>

          {liveState.status === 'loading' && <LoadingSkeletonState />}
          {liveState.status === 'empty' && <EmptyDatasetState />}
          {liveState.status === 'error' && (
            <NetworkErrorState
              error={liveState.error}
              onRetry={executeLiveRequest}
              isRetrying={isRetrying}
            />
          )}
          {liveState.status === 'success' && (
            <div className="p-space-lg rounded-xl bg-surface-container-low border border-emerald-500/30">
              <div className="font-semibold text-emerald-400 text-sm mb-2">
                Live Data Received ({liveState.data?.runs?.length || 0} runs)
              </div>
              <pre className="p-3 bg-surface-container-lowest rounded text-xs font-mono text-on-surface overflow-x-auto">
                {JSON.stringify(liveState.data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
