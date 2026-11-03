'use client';

import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { CloseIcon } from '../icons/Icons';

interface AppShellProps {
  children: React.ReactNode;
  activeNav?: string;
  onSelectNav?: (id: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  activeNav = 'dashboard',
  onSelectNav,
}) => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface-container-lowest text-on-surface flex">
      {/* Desktop Persistent Sidebar */}
      <div className="hidden lg:block fixed left-0 top-0 h-full w-64 z-50">
        <Sidebar activeNav={activeNav} onSelectNav={onSelectNav} />
      </div>

      {/* Mobile Sidebar Overlay / Drawer */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer Content */}
          <div className="relative flex flex-col w-72 max-w-[85vw] h-full bg-surface-container-lowest z-10 shadow-2xl">
            <div className="absolute top-3 right-3 z-10">
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(false)}
                className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container-high transition-colors"
                aria-label="Close navigation"
              >
                <CloseIcon className="w-5 h-5" />
              </button>
            </div>
            <Sidebar
              activeNav={activeNav}
              onSelectNav={onSelectNav}
              onCloseMobile={() => setMobileSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* Top Header */}
        <Header
          activeNav={activeNav}
          onToggleMobileSidebar={() => setMobileSidebarOpen((prev) => !prev)}
        />

        {/* Content Area */}
        <main className="w-full pt-14 flex-1 bg-surface-container-lowest overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
};
