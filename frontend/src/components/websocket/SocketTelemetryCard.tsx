import React from 'react';
import type { SocketTelemetry } from '../../hooks/types';

interface SocketTelemetryCardProps {
  telemetry: SocketTelemetry;
}

function formatUptime(seconds: number): string {
  if (seconds <= 0) return 'n/a';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hrs.toString().padStart(2, '0')}:${mins
    .toString()
    .padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

const readyStateLabels: Record<number, string> = {
  0: '0 (CONNECTING)',
  1: '1 (OPEN)',
  2: '2 (CLOSING)',
  3: '3 (CLOSED)',
};

const stateColors: Record<string, { text: string; bg: string; border: string }> = {
  CONNECTED: {
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
  },
  CONNECTING: {
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
  RECONNECTING: {
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
  DISCONNECTED: {
    text: 'text-outline',
    bg: 'bg-surface-container-high',
    border: 'border-outline-variant/30',
  },
};

export const SocketTelemetryCard: React.FC<SocketTelemetryCardProps> = ({
  telemetry,
}) => {
  const currentColors =
    stateColors[telemetry.connectionState] || stateColors.DISCONNECTED;

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-lg flex flex-col justify-between shadow-sm">
      <div className="flex flex-col gap-space-md">
        {/* Card Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center text-primary">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                <path d="M1.42 9a16 16 0 0 1 21.16 0" />
                <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                <line x1="12" y1="20" x2="12.01" y2="20" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-on-surface">
              Client Telemetry &amp; Socket Metrics
            </h3>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container-high text-outline border border-outline-variant/30">
            FastAPI Stream Endpoint
          </span>
        </div>

        {/* 4 Metrics Quad Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-space-sm pt-1">
          {/* State */}
          <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col justify-between">
            <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
              State
            </span>
            <div className="my-1">
              <span className={`font-mono text-base font-bold ${currentColors.text}`}>
                {telemetry.connectionState}
              </span>
            </div>
            <span className="font-mono text-[10px] text-outline">
              readyState: {readyStateLabels[telemetry.readyState] || telemetry.readyState}
            </span>
          </div>

          {/* Socket Uptime */}
          <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col justify-between">
            <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
              Socket Uptime
            </span>
            <div className="my-1">
              <span className="font-mono text-base font-bold text-on-surface">
                {formatUptime(telemetry.uptimeSeconds)}
              </span>
            </div>
            <span className="font-mono text-[10px] text-outline">
              {telemetry.connectionState === 'CONNECTED' ? 'Uptime Active' : 'Offline'}
            </span>
          </div>

          {/* Ingested Events */}
          <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col justify-between">
            <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
              Ingested Events
            </span>
            <div className="my-1">
              <span className="font-mono text-base font-bold text-primary">
                {telemetry.ingestedEventCount} msgs
              </span>
            </div>
            <span className="font-mono text-[10px] text-outline truncate">
              {telemetry.lastMessageTimestamp
                ? new Date(telemetry.lastMessageTimestamp).toLocaleTimeString()
                : 'Awaiting events'}
            </span>
          </div>

          {/* Frame Drops / Parse Errors */}
          <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col justify-between">
            <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
              Frame Drops
            </span>
            <div className="my-1">
              <span
                className={`font-mono text-base font-bold ${
                  telemetry.parseErrorCount > 0 ? 'text-amber-400' : 'text-on-surface'
                }`}
              >
                {telemetry.parseErrorCount}
              </span>
            </div>
            <span className="font-mono text-[10px] text-outline">
              {telemetry.parseErrorCount === 0 ? '0 parse errors' : 'Malformed frames'}
            </span>
          </div>
        </div>

        {/* Target Connection URI */}
        <div className="p-space-md rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex flex-col min-w-0">
            <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
              Target Connection URI
            </span>
            <span className="font-mono text-xs text-primary truncate mt-0.5">
              {telemetry.targetUri}
            </span>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0 font-mono text-[10px]">
            <span className="px-2 py-0.5 rounded bg-surface-container-high border border-outline-variant/30 text-outline">
              Unidirectional Frontend Consumer
            </span>
            <span className="px-2 py-0.5 rounded bg-surface-container-high border border-outline-variant/30 text-outline hidden sm:inline">
              UTF-8 JSON
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
