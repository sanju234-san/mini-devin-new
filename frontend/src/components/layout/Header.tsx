import React from 'react';
import Image from 'next/image';
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
          <div className="hidden xl:flex items-center gap-1.5 font-mono text-[11px] select-none">
            <span className="px-2 py-0.5 rounded bg-surface-container-high/60 border border-outline-variant/30 text-outline">
              octocat/linguist
            </span>
            <span className="px-2 py-0.5 rounded bg-surface-container-high/60 border border-outline-variant/30 text-primary font-semibold">
              #run-8924a
            </span>
          </div>

          {/* Visual Repo Selector (Disabled Placeholder) */}
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="hidden md:flex items-center gap-1 px-2 py-1 rounded bg-surface-container-high/60 border border-outline-variant/30 text-on-surface-variant/80 text-xs font-mono cursor-not-allowed opacity-85"
            title="Repository selection (Placeholder - Config required)"
          >
            <SourceIcon className="w-3.5 h-3.5 text-outline" />
            <span className="truncate max-w-[130px]">octocat/linguist</span>
            <ChevronDownIcon className="w-3.5 h-3.5 text-outline" />
          </button>
        </div>

        {/* Right: Status Pills & User Area */}
        <div className="flex items-center gap-space-sm sm:gap-space-md flex-shrink-0">
          {/* Backend Status Pill (Honest: Not Connected) */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-low border border-outline-variant/30 text-xs select-none">
            <span className="relative flex h-2 w-2">
              <span className="inline-flex rounded-full h-2 w-2 bg-outline" />
            </span>
            <span className="font-mono text-[11px] text-on-surface-variant">
              <span className="text-on-surface font-medium hidden sm:inline">Backend:</span>{' '}
              <span className="text-outline hidden sm:inline">Not connected (foundation preview)</span>
              <span className="text-outline sm:hidden">Offline</span>
            </span>
          </div>

          {/* System Run Status Pill (Honest: System Idle) */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high/50 border border-outline-variant/30 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-outline/60" />
            <span className="font-mono text-[11px] uppercase tracking-wide text-outline">
              System Idle · Awaiting Task
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
