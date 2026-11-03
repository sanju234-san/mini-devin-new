import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { getHealth, getRuns } from '../../services/api';
import {
  DeployedCodeIcon,
  SourceIcon,
  ChevronDownIcon,
  SettingsIcon,
  MenuIcon,
} from '../icons/Icons';

interface HeaderProps {
  onToggleMobileSidebar: () => void;
  activeNav?: string;
}

const NAV_TITLES: Record<string, string> = {
  dashboard: 'Dashboard',
  'live-console': 'Live Console',
  'plan-approval': 'Plan Approval',
  'diff-viewer': 'Diff Viewer',
  'tests-and-preview': 'Tests & Preview',
  artifacts: 'Artifact Trail',
  transparency: 'Transparency',
  evaluation: 'Evaluation',
};

export const Header: React.FC<HeaderProps> = ({ onToggleMobileSidebar, activeNav = 'dashboard' }) => {
  const currentTitle = NAV_TITLES[activeNav] || 'Workbench';
  const [backendConnected, setBackendConnected] = useState(false);
  const [latestRun, setLatestRun] = useState<{ id: string; repo?: string; status?: string } | null>(null);

  useEffect(() => {
    getHealth()
      .then((res) => setBackendConnected(res.status === 'ok'))
      .catch(() => setBackendConnected(false));
    getRuns(1, 0)
      .then((res) => {
        const r = res.runs?.[0];
        if (r) {
          setLatestRun({ id: r.id, repo: r.repository, status: r.status });
        } else {
          setLatestRun(null);
        }
      })
      .catch(() => setLatestRun(null));
  }, [activeNav]);

  return (
    <header className="fixed top-0 left-0 lg:left-64 right-0 h-14 bg-surface-container-lowest/90 backdrop-blur-md border-b border-outline-variant/30 z-40 px-space-md">
      <div className="w-full h-full flex items-center justify-between gap-space-md">
        {/* Left: Mobile hamburger & Workspace Breadcrumb & Repo Selector */}
        <div className="flex items-center gap-space-sm min-w-0">
          {/* Mobile hamburger button */}
          <button
            onClick={onToggleMobileSidebar}
            className="lg:hidden p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
            aria-label="Toggle navigation menu"
          >
            <MenuIcon className="w-5 h-5" />
          </button>

          {/* Mobile logo when sidebar is hidden */}
          <div className="flex lg:hidden items-center gap-1.5 mr-1 flex-shrink-0">
            <Image
              src="/logo.svg"
              alt="Mini-Devin Mark"
              width={22}
              height={22}
              className="w-[22px] h-[22px]"
            />
            <span className="font-semibold text-xs tracking-tight text-on-surface">
              Mini-Devin
            </span>
          </div>

          {/* Workspace / View Breadcrumb */}
          <div className="hidden sm:flex items-center gap-space-xs text-xs min-w-0">
            <DeployedCodeIcon className="w-4 h-4 text-primary flex-shrink-0" />
            <div className="flex items-center gap-1.5 font-mono truncate text-[11px]">
              <span className="text-outline">Mini-Devin</span>
              <span className="text-outline-variant font-bold">&gt;</span>
              <span className="text-on-surface font-semibold truncate">
                {currentTitle}
              </span>
            </div>
          </div>

          {/* Context Badges (Repo & Run Context) */}
          {latestRun && (
            <div className="hidden xl:flex items-center gap-1.5 font-mono text-[11px] select-none">
              {latestRun.repo && (
                <span className="px-2 py-0.5 rounded bg-surface-container-high/60 border border-outline-variant/30 text-outline">
                  {latestRun.repo}
                </span>
              )}
              <span className="px-2 py-0.5 rounded bg-surface-container-high/60 border border-outline-variant/30 text-primary font-semibold">
                #{latestRun.id.slice(0, 8)}
              </span>
            </div>
          )}

          {/* Right: Status Pills & User Area */}
        </div>

        <div className="flex items-center gap-space-sm sm:gap-space-md flex-shrink-0">
          {/* Backend Status Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-low border border-outline-variant/30 text-xs select-none">
            <span className="relative flex h-2 w-2">
              <span
                className={`inline-flex rounded-full h-2 w-2 ${
                  backendConnected ? 'bg-emerald-400' : 'bg-outline'
                }`}
              />
            </span>
            <span className="font-mono text-[11px] text-on-surface-variant">
              <span className="text-on-surface font-medium hidden sm:inline">Backend:</span>{' '}
              <span className={backendConnected ? 'text-emerald-400 hidden sm:inline font-semibold' : 'text-outline hidden sm:inline'}>
                {backendConnected ? 'Connected' : 'Not connected'}
              </span>
              <span className={backendConnected ? 'text-emerald-400 sm:hidden' : 'text-outline sm:hidden'}>
                {backendConnected ? 'Online' : 'Offline'}
              </span>
            </span>
          </div>

          {/* System Run Status Pill */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high/50 border border-outline-variant/30 select-none">
            <span className={`w-1.5 h-1.5 rounded-full ${latestRun ? 'bg-primary animate-pulse' : 'bg-outline/60'}`} />
            <span className="font-mono text-[11px] uppercase tracking-wide text-outline">
              {latestRun ? `Run Active · ${latestRun.status || 'queued'}` : 'System Idle · Awaiting Task'}
            </span>
          </div>

          {/* User Profile Area (Honest: Guest) */}
          <div className="flex items-center gap-space-sm pl-space-xs sm:pl-space-sm border-l border-outline-variant/30">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-surface-container-high border border-outline-variant/50 flex items-center justify-center text-xs font-mono text-outline">
                G
              </div>
              <div className="hidden xl:flex flex-col text-left">
                <span className="text-xs font-medium text-on-surface leading-none">
                  Guest
                </span>
                <span className="font-mono text-[10px] text-outline leading-tight">
                  Observer
                </span>
              </div>
            </div>

            <button
              type="button"
              className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded transition-colors"
              aria-label="Settings (Static placeholder)"
              title="Settings (Placeholder)"
            >
              <SettingsIcon className="w-4 h-4 text-outline hover:text-on-surface" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
