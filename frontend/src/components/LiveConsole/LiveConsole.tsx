'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { useAgentRunSocket, getWebSocketUri } from '../../hooks/useAgentRunSocket';
import type { AgentEventEnvelope } from '../../hooks/types';
import {
  type FilterCategory,
  filterEvents,
  derivePipelineStages,
  categorizeEvent,
  STATIC_PREVIEW_EVENTS,
} from './liveConsoleUtils';
import { WorkflowTimeline } from './WorkflowTimeline';
import { ConsoleControls } from './ConsoleControls';
import { EventStream } from './EventStream';
import { ActiveAgentPanel } from './ActiveAgentPanel';
import { ToolActivityPanel } from './ToolActivityPanel';
import { EventEnvelopeInspector } from './EventEnvelopeInspector';

interface LiveConsoleProps {
  runId?: string | null;
}

export const LiveConsole: React.FC<LiveConsoleProps> = ({ runId = 'sample-run' }) => {
  const [useStaticPreview, setUseStaticPreview] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FilterCategory>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [frozenSnapshot, setFrozenSnapshot] = useState<AgentEventEnvelope[] | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Consume Task 3 WebSocket Client hook
  const {
    connectionState,
    events: liveEvents,
    latestEvent: liveLatestEvent,
    telemetry,
    clearBuffer: clearSocketBuffer,
    error,
  } = useAgentRunSocket(runId, {
    autoConnect: true,
    bufferCap: 500,
  });

  // Events source: either live hook events or quarantined static preview events
  const rawEvents = useStaticPreview ? STATIC_PREVIEW_EVENTS : liveEvents;

  // Handle Pause / Snapshot Freeze
  const handleTogglePause = useCallback(() => {
    setIsPaused((prev) => {
      if (!prev) {
        // Pausing: freeze current list
        setFrozenSnapshot([...rawEvents]);
        return true;
      } else {
        // Resuming: unfreeze
        setFrozenSnapshot(null);
        return false;
      }
    });
  }, [rawEvents]);

  // Displayed events
  const displayedEvents = isPaused && frozenSnapshot ? frozenSnapshot : rawEvents;
  const pausedNewCount = isPaused && frozenSnapshot ? Math.max(0, rawEvents.length - frozenSnapshot.length) : 0;

  // Filtered events
  const filteredEvents = useMemo(
    () => filterEvents(displayedEvents, activeFilter),
    [displayedEvents, activeFilter]
  );

  // Filter counts computed honestly from current stream
  const counts = useMemo(() => {
    let tools = 0;
    let thoughts = 0;
    let errors = 0;

    for (const evt of displayedEvents) {
      const cat = categorizeEvent(evt);
      if (cat === 'tools') tools++;
      if (cat === 'thoughts') thoughts++;
      if (cat === 'errors') errors++;
    }

    return {
      all: displayedEvents.length,
      tools,
      thoughts,
      errors,
    };
  }, [displayedEvents]);

  // Derived 8-stage pipeline statuses
  const pipelineStages = useMemo(
    () => derivePipelineStages(rawEvents),
    [rawEvents]
  );

  // Active / Latest event
  const effectiveLatestEvent = useStaticPreview
    ? STATIC_PREVIEW_EVENTS[STATIC_PREVIEW_EVENTS.length - 1]
    : liveLatestEvent;

  // Selected event for inspector
  const selectedEvent = useMemo(() => {
    if (!selectedEventId) return effectiveLatestEvent;
    return (
      rawEvents.find((e, idx) => (e.id || String(idx)) === selectedEventId) ||
      effectiveLatestEvent
    );
  }, [selectedEventId, rawEvents, effectiveLatestEvent]);

  const handleSelectEvent = useCallback((event: AgentEventEnvelope) => {
    setSelectedEventId(event.id || null);
  }, []);

  const handleClear = useCallback(() => {
    if (useStaticPreview) {
      setFrozenSnapshot([]);
    } else {
      clearSocketBuffer();
    }
    setSelectedEventId(null);
  }, [useStaticPreview, clearSocketBuffer]);

  const targetUri = getWebSocketUri(runId);

  return (
    <div className="flex flex-col gap-space-md w-full">
      {/* Top Meta Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-space-sm p-space-sm rounded-xl bg-surface-container-low border border-outline-variant/30 text-xs font-mono">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="relative flex h-2 w-2">
            <span
              className={`inline-flex rounded-full h-2 w-2 ${
                useStaticPreview
                  ? 'bg-primary'
                  : connectionState === 'CONNECTED'
                  ? 'bg-emerald-400'
                  : 'bg-outline'
              }`}
            />
          </span>
          <span className="font-semibold text-on-surface">
            {useStaticPreview ? 'STATIC PREVIEW MODE' : connectionState}
          </span>
          <span className="text-outline-variant">|</span>
          <span className="text-outline text-[11px] truncate max-w-xs">
            {targetUri}
          </span>
        </div>

        {/* View Switcher: Live Stream vs Static Preview */}
        <div className="inline-flex p-0.5 rounded-lg bg-surface-container border border-outline-variant/30 text-xs">
          <button
            type="button"
            onClick={() => setUseStaticPreview(false)}
            className={`px-2.5 py-1 rounded font-medium transition-all ${
              !useStaticPreview
                ? 'bg-primary-container text-on-primary-container font-semibold shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            Live Hook Stream
          </button>
          <button
            type="button"
            onClick={() => setUseStaticPreview(true)}
            className={`px-2.5 py-1 rounded font-medium transition-all ${
              useStaticPreview
                ? 'bg-teal-500 text-surface-container-lowest font-bold shadow-sm'
                : 'text-teal-400 hover:text-teal-300'
            }`}
          >
            Static Preview
          </button>
        </div>
      </div>

      {/* 1. Autonomous Pipeline Execution (8 Stages) */}
      <WorkflowTimeline stages={pipelineStages} />

      {/* 2. Stream Controls Bar */}
      <ConsoleControls
        connectionState={useStaticPreview ? 'CONNECTED' : connectionState}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        counts={counts}
        autoScroll={autoScroll}
        onToggleAutoScroll={() => setAutoScroll((prev) => !prev)}
        isPaused={isPaused}
        onTogglePause={handleTogglePause}
        pausedNewCount={pausedNewCount}
        onClear={handleClear}
        totalEvents={displayedEvents.length}
      />

      {/* 3. Main Split View: Event Stream (Left) + Inspection Panels (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
        {/* Left Column: Event Stream (7 of 12 cols on desktop) */}
        <div className="lg:col-span-7 flex flex-col">
          <EventStream
            events={filteredEvents}
            connectionState={useStaticPreview ? 'CONNECTED' : connectionState}
            selectedEventId={selectedEventId}
            onSelectEvent={handleSelectEvent}
            autoScroll={autoScroll}
            parseErrorCount={telemetry.parseErrorCount}
            bufferCap={500}
            runId={runId}
            error={error}
            targetUri={targetUri}
          />
        </div>

        {/* Right Column: Three Stacked Inspection Panels (5 of 12 cols on desktop) */}
        <div className="lg:col-span-5 flex flex-col gap-space-md">
          {/* Active Agent Card */}
          <ActiveAgentPanel latestEvent={effectiveLatestEvent} />

          {/* Live Tool Activity Card */}
          <ToolActivityPanel events={rawEvents} />

          {/* Event Envelope Inspector */}
          <EventEnvelopeInspector selectedEvent={selectedEvent} />
        </div>
      </div>
    </div>
  );
};
