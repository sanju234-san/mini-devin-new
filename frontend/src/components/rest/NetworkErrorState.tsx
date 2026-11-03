import React from 'react';
import { API_BASE_URL } from '../../config/env';
import type { ApiError } from '../../services/types';

interface NetworkErrorStateProps {
  error?: ApiError;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export const NetworkErrorState: React.FC<NetworkErrorStateProps> = ({
  error,
  onRetry,
  isRetrying = false,
}) => {
  const endpoint = error?.endpoint || `${API_BASE_URL}/api/v1/runs`;
  const errorKind = error?.kind || 'NETWORK_ERROR';
  const errorMessage =
    error?.message ||
    `Failed to fetch run telemetry from ${endpoint}. The FastAPI agent runner service may be booting, crashed, or blocked by firewalls.`;

  return (
    <div
      className="rounded-xl bg-surface-container-low border border-red-500/30 overflow-hidden shadow-sm"
      role="alert"
      aria-live="assertive"
      aria-label="REST API error state"
    >
      {/* State Header Bar */}
      <div className="px-space-md py-2.5 bg-red-950/20 border-b border-red-500/20 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-red-500/10 text-red-400 border border-red-500/30 font-semibold">
            STATE 03
          </span>
          <span className="font-semibold text-on-surface">
            Network Fault / Backend Crash Boundary
          </span>
          <span className="font-mono text-[11px] text-red-300/80 hidden sm:inline">
            {errorKind === 'NETWORK_ERROR' ? 'ERR_CONNECTION_REFUSED' : `HTTP ${error?.status || 503}`}
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-red-400">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
          <span>HTTP 503 SERVICE UNAVAILABLE</span>
        </div>
      </div>

      {/* Main Error Content */}
      <div className="p-space-lg md:p-space-xl flex flex-col gap-space-lg">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-space-md">
          <div className="flex items-start gap-space-md">
            {/* Red Alert Icon */}
            <div className="w-11 h-11 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 flex-shrink-0 mt-0.5">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base sm:text-lg font-semibold text-on-surface">
                  Unable to Connect to REST API Backend
                </h3>
                <span className="px-1.5 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-red-500/20 text-red-300 border border-red-500/40">
                  {errorKind === 'NETWORK_ERROR' ? 'ECONNREFUSED' : `STATUS ${error?.status || 503}`}
                </span>
              </div>
              <p className="text-sm text-on-surface-variant leading-relaxed max-w-2xl">
                {errorMessage}
              </p>
            </div>
          </div>
        </div>

        {/* REST Client Exception Trace Box */}
        <div className="rounded-lg bg-surface-container-lowest border border-outline-variant/30 p-space-md font-mono text-xs flex flex-col gap-1.5 overflow-x-auto">
          <div className="flex items-center justify-between text-outline text-[11px] pb-1 border-b border-outline-variant/20 mb-1">
            <span className="flex items-center gap-1.5 text-red-400">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 17 10 11 4 5" />
                <line x1="12" y1="19" x2="20" y2="19" />
              </svg>
              <span>REST Client Exception Trace</span>
            </span>
            <span className="text-outline-variant text-[10px]">
              Target: {API_BASE_URL}
            </span>
          </div>

          <div className="text-red-400 font-medium">
            [REST Client] {endpoint}: {errorKind} (configured via src/config/env.ts)
          </div>
          <div className="text-outline text-[11px]">
            at request (src/services/api.ts)
          </div>
          <div className="text-outline text-[11px]">
            at getRuns (src/services/api.ts)
          </div>
          <div className="text-outline-variant text-[11px] pt-1 border-t border-outline-variant/10">
            [Client Policy] Single user-triggered retry strategy active. No auto-polling loop.
          </div>
        </div>

        {/* Actions Row */}
        <div className="flex items-center gap-space-sm pt-1">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
              className="flex items-center gap-2 px-space-md py-2 rounded-lg bg-primary-container text-on-primary-container font-semibold text-xs hover:bg-primary-container/90 active:scale-[0.99] transition-all shadow-sm disabled:opacity-50"
            >
              <svg
                className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              <span>{isRetrying ? 'Retrying...' : 'Retry Connection Now'}</span>
            </button>
          )}

          <div className="font-mono text-[11px] text-outline ml-auto hidden sm:block">
            Base URL: <span className="text-on-surface">{API_BASE_URL}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
