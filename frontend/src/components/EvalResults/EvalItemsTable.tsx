import React, { useState, useMemo } from 'react';
import type { EvalItem, EvalItemStatus } from './evalResultsUtils';

interface EvalItemsTableProps {
  items: EvalItem[];
  selectedItemId?: string;
  onSelectItem?: (item: EvalItem) => void;
}

export const EvalItemsTable: React.FC<EvalItemsTableProps> = ({
  items,
  selectedItemId,
  onSelectItem,
}) => {
  const [selectedStatusTab, setSelectedStatusTab] = useState<'ALL' | 'FAILED' | 'PASSED' | 'SKIPPED'>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const pageSize = 7;

  // Counts for tabs
  const failedCount = useMemo(() => items.filter((i) => i.status === 'FAILED').length, [items]);
  const passedCount = useMemo(() => items.filter((i) => i.status === 'PASSED').length, [items]);
  const skippedCount = useMemo(() => items.filter((i) => i.status === 'SKIPPED').length, [items]);

  // Filtered items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Status tab
      if (selectedStatusTab !== 'ALL' && item.status !== selectedStatusTab) {
        return false;
      }
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = item.name.toLowerCase().includes(q);
        const matchSymbol = item.symbol.toLowerCase().includes(q);
        const matchError = (item.errorMessage || '').toLowerCase().includes(q);
        const matchNote = (item.detailNote || '').toLowerCase().includes(q);
        return matchName || matchSymbol || matchError || matchNote;
      }
      return true;
    });
  }, [items, selectedStatusTab, searchQuery]);

  // Paginated items
  const totalPages = Math.ceil(filteredItems.length / pageSize) || 1;
  const paginatedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, page, pageSize]);

  return (
    <div className="flex flex-col bg-surface-container-lowest border border-outline-variant/30 rounded-lg overflow-hidden h-full">
      {/* 1. Filter Bar matching Stitch design */}
      <div className="p-3 border-b border-outline-variant/30 flex flex-col md:flex-row md:items-center justify-between gap-2.5 bg-surface-container-low/40">
        {/* Left: Filter Tabs */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <div className="flex items-center bg-surface-container-lowest border border-outline-variant/30 rounded p-0.5 text-xs font-mono">
            <button
              type="button"
              onClick={() => {
                setSelectedStatusTab('ALL');
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                selectedStatusTab === 'ALL'
                  ? 'bg-surface-container-high text-primary font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              All Items ({items.length})
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedStatusTab('FAILED');
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 ${
                selectedStatusTab === 'FAILED'
                  ? 'bg-surface-container-high text-red-400 font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              Failed ({failedCount})
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedStatusTab('PASSED');
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                selectedStatusTab === 'PASSED'
                  ? 'bg-surface-container-high text-emerald-400 font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Passed ({passedCount})
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedStatusTab('SKIPPED');
                setPage(1);
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                selectedStatusTab === 'SKIPPED'
                  ? 'bg-surface-container-high text-on-surface font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
            >
              Skipped ({skippedCount})
            </button>
          </div>
        </div>

        {/* Right: Search Input */}
        <div className="relative flex-1 max-w-sm">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search criteria, test symbols, assertions... (⌘K)"
            className="w-full px-2.5 py-1 text-xs bg-surface-container-lowest border border-outline-variant/40 rounded text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary font-mono"
          />
        </div>
      </div>

      {/* 2. Table Header Bar */}
      <div className="px-3 py-2 border-b border-outline-variant/30 flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-on-surface">Evaluation Details</span>
          <span className="text-outline text-[11px]">{filteredItems.length} items</span>
        </div>
        <div className="text-[11px] text-outline flex items-center gap-1 cursor-pointer hover:text-on-surface">
          <span>Sort by: Failure Severity ↓</span>
        </div>
      </div>

      {/* 3. Items Table List */}
      <div className="flex-1 overflow-y-auto min-h-[420px]">
        {paginatedItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-outline text-xs">
            <svg className="w-8 h-8 mb-2 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <line x1="8" y1="12" x2="16" y2="12" />
            </svg>
            <span>No criteria items matching filter.</span>
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/20 font-mono text-xs">
            {paginatedItems.map((item) => {
              const isSelected = selectedItemId === item.id;
              const isFailed = item.status === 'FAILED';
              const isPassed = item.status === 'PASSED';

              return (
                <div
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectItem?.(item)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectItem?.(item);
                    }
                  }}
                  className={`p-3 text-left transition-colors cursor-pointer flex items-center justify-between gap-3 ${
                    isSelected
                      ? 'bg-surface-container-high/90 border-l-2 border-primary'
                      : 'hover:bg-surface-container-low/60'
                  }`}
                >
                  {/* Left: Symbol & Error/Note */}
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <span className="mt-0.5">
                      {isFailed ? (
                        <span className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-red-400 font-bold text-xs">
                          ⨂
                        </span>
                      ) : isPassed ? (
                        <span className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-emerald-400 font-bold text-xs">
                          ✔
                        </span>
                      ) : (
                        <span className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-outline font-bold text-xs">
                          ○
                        </span>
                      )}
                    </span>

                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="text-on-surface font-semibold truncate">
                        {item.symbol}
                      </span>
                      {item.errorMessage ? (
                        <span className="text-[11px] text-red-400/90 truncate mt-0.5">
                          {item.errorMessage}
                        </span>
                      ) : item.detailNote ? (
                        <span className="text-[11px] text-outline truncate mt-0.5">
                          {item.detailNote}
                        </span>
                      ) : (
                        <span className="text-[10px] text-outline truncate mt-0.5">
                          {item.subcategory}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Right: Status Pill, Score, Duration */}
                  <div className="flex items-center gap-4 shrink-0 text-right">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase border ${
                        isFailed
                          ? 'bg-red-500/10 text-red-400 border-red-500/30'
                          : isPassed
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-surface-container-high text-outline border-outline-variant/30'
                      }`}
                    >
                      {item.status}
                    </span>

                    <span className="w-16 font-semibold text-on-surface text-right">
                      {item.status === 'SKIPPED'
                        ? '--'
                        : `${item.score.toFixed(2)} / ${item.maxScore.toFixed(1)}`}
                    </span>

                    <span className="w-12 text-[11px] text-outline text-right">
                      {item.durationMs}ms
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Table Pagination Footer */}
      <div className="p-3 border-t border-outline-variant/30 bg-surface-container-low/40 flex items-center justify-between text-xs font-mono text-outline">
        <span>
          Showing {paginatedItems.length} of {filteredItems.length} criteria in active view
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(p - 1, 1))}
            className="px-2 py-0.5 rounded border border-outline-variant/30 text-on-surface disabled:opacity-30 disabled:cursor-not-allowed hover:bg-surface-container-high"
          >
            Prev
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            className="px-2 py-0.5 rounded border border-outline-variant/30 text-on-surface disabled:opacity-30 disabled:cursor-not-allowed hover:bg-surface-container-high"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
