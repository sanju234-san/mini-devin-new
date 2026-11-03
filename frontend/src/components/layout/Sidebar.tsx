import React from 'react';
import Image from 'next/image';
import {
  GridIcon,
  TerminalIcon,
  ChecklistIcon,
  DiffIcon,
  ScienceIcon,
  FolderZipIcon,
  MonitoringIcon,
  EyeIcon,
} from '../icons/Icons';

interface SidebarProps {
  onCloseMobile?: () => void;
  activeNav?: string;
  onSelectNav?: (id: string) => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  isSupported?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  onCloseMobile,
  activeNav = 'dashboard',
  onSelectNav,
}) => {
  const navItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <GridIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'live-console',
      label: 'Live Console',
      icon: <TerminalIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'plan-approval',
      label: 'Plan Approval',
      icon: <ChecklistIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'diff-viewer',
      label: 'Diff Viewer',
      icon: <DiffIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'tests-and-preview',
      label: 'Tests & Preview',
      icon: <ScienceIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'artifacts',
      label: 'Artifacts',
      icon: <FolderZipIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'transparency',
      label: 'Transparency',
      icon: <EyeIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
    {
      id: 'evaluation',
      label: 'Evaluation',
      icon: <MonitoringIcon className="w-[18px] h-[18px]" />,
      isSupported: true,
    },
  ];

  return (
    <aside className="h-full w-64 bg-surface-container-lowest flex flex-col justify-between border-r border-outline-variant/30 select-none">
      <div className="flex flex-col">
        {/* Sidebar Brand Header */}
        <div className="h-14 px-space-md flex items-center justify-between border-b border-outline-variant/30">
          <div className="flex items-center gap-space-sm">
            <div className="w-7 h-7 rounded-lg bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-primary overflow-hidden">
              <Image
                src="/logo.svg"
                alt="Mini-Devin Mark"
                width={20}
                height={20}
                className="w-5 h-5"
              />
            </div>
            <div className="flex items-center gap-space-xs">
              <span className="font-semibold text-sm tracking-tight text-on-surface">
                Mini-Devin
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-surface-container-high text-primary border border-primary/20">
                v0.1-preview
              </span>
            </div>
          </div>
        </div>

        {/* Section Label */}
        <div className="px-space-md py-space-sm mt-1">
          <span className="font-mono text-[11px] uppercase tracking-wider text-outline px-space-xs">
            Orchestration
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="flex flex-col gap-0.5 px-space-sm" aria-label="Main Navigation">
          {navItems.map((item) => {
            const isActive = item.id === activeNav;

            if (item.isSupported) {
              if (isActive) {
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      onSelectNav?.(item.id);
                      onCloseMobile?.();
                    }}
                    aria-current="page"
                    className="w-full flex items-center justify-between px-space-md py-2 rounded text-xs font-medium bg-primary-container/20 text-primary border border-primary/30 transition-colors text-left"
                  >
                    <div className="flex items-center gap-space-md">
                      {item.icon}
                      <span>{item.label}</span>
                    </div>
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  </button>
                );
              }

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    onSelectNav?.(item.id);
                    onCloseMobile?.();
                  }}
                  className="w-full flex items-center justify-between px-space-md py-2 rounded text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/60 transition-colors text-left"
                >
                  <div className="flex items-center gap-space-md">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                </button>
              );
            }

            return (
              <div
                key={item.id}
                aria-disabled="true"
                role="link"
                tabIndex={-1}
                className="flex items-center justify-between px-space-md py-2 rounded text-xs text-on-surface-variant/70 border border-transparent cursor-not-allowed opacity-60 hover:bg-surface-container-high/40 transition-colors"
                title={`${item.label} (Placeholder - Not yet connected)`}
              >
                <div className="flex items-center gap-space-md">
                  {item.icon}
                  <span>{item.label}</span>
                </div>
              </div>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Footer Panel */}
      <div className="border-t border-outline-variant/30 p-space-sm bg-surface-container-lowest/80">
        <div className="p-space-sm rounded-lg bg-surface-container-low border border-outline-variant/20 mb-space-xs">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="inline-flex rounded-full h-2 w-2 bg-tertiary/70" />
              </span>
              <span className="font-mono text-[11px] uppercase tracking-wide text-on-surface-variant">
                Agent Core
              </span>
            </div>
            <span className="font-mono text-[11px] text-tertiary">Idle</span>
          </div>
          <div className="flex items-center justify-between text-xs text-outline">
            <span className="font-mono text-[11px] text-outline">Runtime: Standby</span>
            <span className="font-mono text-[10px] text-outline-variant">v0.1</span>
          </div>
        </div>

        <div className="flex items-center justify-between px-space-xs pt-1">
          <span className="font-mono text-[10px] text-outline uppercase tracking-wider">
            Foundation Preview
          </span>
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="lg:hidden text-outline hover:text-on-surface text-xs underline"
            >
              Close
            </button>
          )}
        </div>
        <div className="px-space-xs pt-1.5 border-t border-outline-variant/20 mt-1.5 flex items-center justify-between">
          <span className="font-mono text-[10px] text-outline whitespace-nowrap truncate" title="Nikunj Nanda · Frontend Lead">
            Nikunj Nanda · Frontend Lead
          </span>
        </div>
      </div>
    </aside>
  );
};
