import React from 'react';
import { TerminalIcon } from '../icons/Icons';

export const FooterStrip: React.FC = () => {
  return (
    <footer className="mt-space-md p-space-md rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-2">
      <div className="flex items-center gap-2 font-mono text-xs text-outline">
        <TerminalIcon className="w-3.5 h-3.5 text-primary flex-shrink-0" />
        <span className="text-center sm:text-left">
          Architecture: Next.js 14 · Tailwind CSS · TypeScript · Ready for REST &amp; WebSocket Integration
        </span>
      </div>
      <div className="font-mono text-[10px] text-outline-variant">
        Foundation Preview v0.1
      </div>
    </footer>
  );
};
