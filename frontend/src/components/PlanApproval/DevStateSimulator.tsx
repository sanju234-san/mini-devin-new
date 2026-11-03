'use client';

import React from 'react';
import type { SimulatorState } from './types';

interface DevStateSimulatorProps {
  currentState: SimulatorState;
  onSelectState: (state: SimulatorState) => void;
}

export const DevStateSimulator: React.FC<DevStateSimulatorProps> = ({
  currentState,
  onSelectState,
}) => {
  // Only render in non-production environments
  if (process.env.NODE_ENV === 'production') {
    return null;
  }

  const states: { id: SimulatorState; label: string }[] = [
    { id: 'real', label: 'Live API (Real)' },
    { id: 'awaiting_approval', label: '1. Awaiting Approval (Active Preview)' },
    { id: 'loading', label: '2. Loading Skeleton' },
    { id: 'submitting', label: '3. Submitting...' },
    { id: 'approved', label: '4. Approved (Advancing)' },
    { id: 'changes_requested', label: '5. Changes Requested' },
    { id: 'empty', label: '6. Empty Plan' },
    { id: 'error', label: '7. Error / Aborted' },
  ];

  return (
    <div className="w-full bg-surface-container-lowest border-t border-outline-variant/30 px-space-md py-3 mt-space-xl flex flex-col gap-2">
      <div className="flex items-center justify-between flex-wrap gap-2 text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-tertiary" />
          <span className="font-semibold text-on-surface uppercase tracking-wider text-[11px]">
            DEV PREVIEW SIMULATOR (Static demonstration, no real API mutations)
          </span>
        </div>
        <span className="text-[10px] text-outline">
          Isolated Development Testing Bar
        </span>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap overflow-x-auto pt-1">
        {states.map((st) => {
          const isActive = currentState === st.id;
          return (
            <button
              key={st.id}
              type="button"
              onClick={() => onSelectState(st.id)}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                  : 'bg-surface-container hover:bg-surface-container-high text-on-surface-variant'
              }`}
            >
              {st.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
