import React from 'react';
import type { SocketConnectionState } from '../../hooks/types';

interface LifecycleStatesCardProps {
  activeState: SocketConnectionState;
  reconnectAttempt?: number;
  onManualConnect?: () => void;
  onManualDisconnect?: () => void;
}

export const LifecycleStatesCard: React.FC<LifecycleStatesCardProps> = ({
  activeState,
  reconnectAttempt = 0,
  onManualConnect,
  onManualDisconnect,
}) => {
  const states = [
    {
      id: 'CONNECTED',
      code: '01',
      title: 'CONNECTED',
      badge: 'Active',
      readyState: 'readyState: 1',
      description:
        'Duplex socket open. Native WebSocket transport active. Client buffer accepting real-time agent envelopes.',
      accent: 'border-emerald-500/40 text-emerald-400',
      activeBg: 'bg-emerald-950/20 border-emerald-500/50',
    },
    {
      id: 'CONNECTING',
      code: '02',
      title: 'CONNECTING',
      badge: 'Transitional',
      readyState: 'readyState: 0',
      description:
        'Issuing initial HTTP Upgrade header to ws://... Awaiting 101 Switching Protocols response.',
      accent: 'border-amber-500/40 text-amber-400',
      activeBg: 'bg-amber-950/20 border-amber-500/50',
    },
    {
      id: 'RECONNECTING',
      code: '03',
      title: 'RECONNECTING',
      badge: reconnectAttempt > 0 ? `Attempt ${reconnectAttempt} of 5` : 'Backoff Active',
      readyState: 'Exponential Backoff',
      description:
        'Network dropped or TCP reset detected. Bounded backoff: min(1000 * 2^attempt, 15000) capped at 5 attempts.',
      accent: 'border-amber-500/40 text-amber-400',
      activeBg: 'bg-amber-950/20 border-amber-500/50',
    },
    {
      id: 'DISCONNECTED',
      code: '04',
      title: 'DISCONNECTED',
      badge: 'Terminal State',
      readyState: 'readyState: 3',
      description:
        'Connection closed cleanly (1000), abnormally (1006), or manually unmounted. Retries exhausted or unmounted.',
      accent: 'border-outline-variant/40 text-outline',
      activeBg: 'bg-surface-container-high/40 border-outline/40',
    },
  ];

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-md">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-on-surface">
              Client Lifecycle States (useAgentRunSocket)
            </h3>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-outline border border-outline-variant/30">
            Finite State Machine
          </span>
        </div>

        {/* 2x2 Grid of States */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm pt-1">
          {states.map((st) => {
            const isActive = activeState === st.id;
            return (
              <div
                key={st.id}
                className={`p-space-md rounded-lg border transition-all ${
                  isActive
                    ? st.activeBg
                    : 'bg-surface-container border-outline-variant/20 opacity-70'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        isActive ? 'bg-primary animate-pulse' : 'bg-outline/50'
                      }`}
                    />
                    <span className="font-mono text-xs font-semibold text-on-surface">
                      {st.code} · {st.title}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] uppercase px-1.5 py-0.2 rounded bg-surface-container-high text-outline">
                    {st.badge}
                  </span>
                </div>

                <p className="text-xs text-on-surface-variant leading-relaxed mb-2">
                  {st.description}
                </p>

                <div className="flex items-center justify-between font-mono text-[10px] text-outline pt-1 border-t border-outline-variant/10">
                  <span>{st.readyState}</span>
                  {isActive && <span className="text-primary font-bold">CURRENT</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* Manual Connect / Disconnect Controls */}
        {(onManualConnect || onManualDisconnect) && (
          <div className="flex items-center gap-2 pt-2 border-t border-outline-variant/20 font-mono text-xs">
            <span className="text-outline text-[11px]">Manual Controls:</span>
            {onManualConnect && (
              <button
                type="button"
                onClick={onManualConnect}
                disabled={activeState === 'CONNECTED' || activeState === 'CONNECTING'}
                className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-primary disabled:opacity-40 transition-colors"
              >
                Connect Socket
              </button>
            )}
            {onManualDisconnect && (
              <button
                type="button"
                onClick={onManualDisconnect}
                disabled={activeState === 'DISCONNECTED'}
                className="px-2.5 py-1 rounded bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/30 text-outline hover:text-red-400 disabled:opacity-40 transition-colors"
              >
                Disconnect
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
