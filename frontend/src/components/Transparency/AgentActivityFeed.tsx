import React, { useState, useMemo } from 'react';
import type { TransparencyEvent } from './transparencyUtils';

interface AgentActivityFeedProps {
  events: TransparencyEvent[];
  selectedEventId?: string;
  onSelectEvent?: (event: TransparencyEvent) => void;
  onExportAuditJson?: () => void;
  onCopyTrace?: () => void;
}

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  onExportAuditJson,
  onCopyTrace,
}) => {
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'tools' | 'thoughts' | 'decisions'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Extract distinct agents for dropdown
  const distinctAgents = useMemo(() => {
    const set = new Set<string>();
    events.forEach((evt) => set.add(evt.agent));
    return Array.from(set);
  }, [events]);

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter((evt) => {
      // Agent filter
      if (selectedAgentFilter !== 'all' && evt.agent !== selectedAgentFilter) {
        return false;
      }
      // Category filter
      if (selectedCategory !== 'all' && evt.category !== selectedCategory) {
        return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = evt.title.toLowerCase().includes(q);
        const matchContent = evt.content.toLowerCase().includes(q);
        const matchAgent = evt.agent.toLowerCase().includes(q);
        const matchModel = (evt.model || '').toLowerCase().includes(q);
        return matchTitle || matchContent || matchAgent || matchModel;
      }
      return true;
    });
  }, [events, selectedAgentFilter, selectedCategory, searchQuery]);

  return (
    <div className="flex flex-col h-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg overflow-hidden">
      {/* Controls Bar: Agent Dropdown & Category Tabs */}
      <div className="p-3 border-b border-outline-variant/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-surface-container-low/40">
        <div className="flex items-center gap-2">
          {/* Agent Dropdown */}
          <select
            value={selectedAgentFilter}
            onChange={(e) => setSelectedAgentFilter(e.target.value)}
            className="px-2.5 py-1 text-xs font-mono bg-surface-container-high border border-outline-variant/40 rounded text-on-surface focus:outline-none focus:border-primary"
          >
            <option value="all">All Agents ({distinctAgents.length || 8})</option>
            {distinctAgents.map((ag) => (
              <option key={ag} value={ag}>
                {ag}
              </option>
            ))}
          </select>

          {/* Category Tabs */}
          <div className="flex items-center bg-surface-container-lowest border border-outline-variant/30 rounded p-0.5 text-xs font-mono">
            {(['all', 'tools', 'thoughts', 'decisions'] as const).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`px-2 py-0.5 rounded capitalize transition-colors ${
                  selectedCategory === cat
                    ? 'bg-surface-container-high text-primary font-semibold'
                    : 'text-outline hover:text-on-surface'
                }`}
              >
                {cat === 'all' ? 'All Events' : cat}
              </button>
            ))}
          </div>
        </div>

        {/* Filter Input */}
        <div className="relative flex-1 max-w-xs">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter logs, tool calls... ⌘K"
            className="w-full px-2.5 py-1 text-xs bg-surface-container-lowest border border-outline-variant/40 rounded text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary font-mono"
          />
        </div>
      </div>

      {/* Events List Scrollable Area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[420px] max-h-[620px]">
        {filteredEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-outline text-xs">
            <svg className="w-8 h-8 mb-2 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <line x1="8" y1="12" x2="16" y2="12" />
            </svg>
            <span>No activity events matching current filters.</span>
          </div>
        ) : (
          filteredEvents.map((evt) => {
            const isSelected = selectedEventId === evt.id;

            // Agent color tag
            const agentLower = evt.agent.toLowerCase();
            let agentBadge = 'text-primary bg-primary/10 border-primary/30';
            if (agentLower.includes('test')) {
              agentBadge = 'text-amber-400 bg-amber-500/10 border-amber-500/30';
            } else if (agentLower.includes('code')) {
              agentBadge = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
            } else if (agentLower.includes('plan')) {
              agentBadge = 'text-purple-400 bg-purple-500/10 border-purple-500/30';
            } else if (agentLower.includes('retriev')) {
              agentBadge = 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30';
            }

            return (
              <div
                key={evt.id}
                role="button"
                tabIndex={0}
                onClick={() => onSelectEvent?.(evt)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectEvent?.(evt);
                  }
                }}
                className={`p-3 rounded-lg border text-left transition-all cursor-pointer flex flex-col gap-2 ${
                  isSelected
                    ? 'bg-surface-container-high border-primary ring-1 ring-primary/40'
                    : 'bg-surface-container-lowest/90 border-outline-variant/30 hover:bg-surface-container-low hover:border-outline-variant/50'
                }`}
              >
                {/* Event Header Row: Agent name, timestamp, badge label, meta chips */}
                <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase font-bold border ${agentBadge}`}
                    >
                      {evt.agent}
                    </span>
                    <span className="font-mono text-[11px] text-outline">
                      {evt.timeFormatted}
                    </span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-surface-container-high text-on-surface-variant border border-outline-variant/30">
                      {evt.badgeLabel}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap font-mono text-[10px]">
                    {evt.exitCode !== undefined && (
                      <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/30 font-semibold">
                        Exit Code {evt.exitCode}
                      </span>
                    )}
                    {evt.sandboxId && (
                      <span className="text-outline">
                        {evt.sandboxId}
                      </span>
                    )}
                    {evt.tokensInfo && (
                      <span className="text-primary font-medium">
                        {evt.tokensInfo} {evt.durationInfo && `• ${evt.durationInfo}`}
                      </span>
                    )}
                    {evt.depth !== undefined && (
                      <span className="text-outline">
                        Depth {evt.depth}
                      </span>
                    )}
                    {evt.model && (
                      <span
                        className={`px-1.5 py-0.5 rounded border ${
                          evt.isClassifier
                            ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                            : 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                        }`}
                      >
                        {evt.model}
                      </span>
                    )}
                    {evt.contextRef && (
                      <span className="text-tertiary">
                        {evt.contextRef}
                      </span>
                    )}
                  </div>
                </div>

                {/* Event Title */}
                <div className="text-xs font-semibold text-on-surface">
                  {evt.title}
                </div>

                {/* Event Code / Log Content Box */}
                <div className="p-2 rounded bg-surface-container-lowest border border-outline-variant/20 font-mono text-[11px] text-on-surface-variant whitespace-pre-wrap overflow-x-auto leading-relaxed">
                  {evt.content}
                </div>

                {/* Event Footer / Subcontent or Telemetry Details */}
                {(evt.subContent || evt.confidence !== undefined || evt.diffSummary) && (
                  <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-outline pt-1 border-t border-outline-variant/15 flex-wrap">
                    {evt.confidence !== undefined && (
                      <div className="flex items-center gap-3">
                        <span className="text-emerald-400 font-medium">
                          Confidence: {evt.confidence}%
                        </span>
                        {evt.hallucinationScore && (
                          <span>
                            Hallucination check: <span className="text-on-surface">{evt.hallucinationScore}</span>
                          </span>
                        )}
                      </div>
                    )}
                    {evt.diffSummary && (
                      <span className="text-primary font-semibold">
                        {evt.diffSummary}
                      </span>
                    )}
                    {evt.subContent && (
                      <span className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                        {evt.subContent}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Feed Bottom Status & Actions Bar */}
      <div className="p-3 border-t border-outline-variant/30 bg-surface-container-low/40 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
        {/* Left Status Indicators */}
        <div className="flex items-center gap-3 flex-wrap text-[11px] font-mono text-outline">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-on-surface">Telemetry Stream Active (10 Hz)</span>
          </div>
          <span>|</span>
          <span>Session Storage: 4.8 MB / 50 MB</span>
          <span>|</span>
          <span className="text-emerald-400">Agent Latency: 24ms</span>
        </div>

        {/* Right Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={onExportAuditJson}
            className="px-2.5 py-1 rounded bg-surface-container-high border border-outline-variant/40 text-on-surface hover:bg-surface-container-highest transition-colors font-mono text-[11px] flex items-center gap-1.5"
          >
            <span>↓</span>
            <span>Export Audit JSON</span>
          </button>
          <button
            type="button"
            onClick={onCopyTrace}
            className="px-2.5 py-1 rounded bg-primary text-on-primary hover:bg-primary/90 transition-colors font-medium text-[11px] flex items-center gap-1.5"
          >
            <span>Copy Run Trace</span>
          </button>
        </div>
      </div>
    </div>
  );
};
