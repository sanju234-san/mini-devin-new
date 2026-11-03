/**
 * Helper utilities for Task 4: Live Agent Console
 *
 * Implements pure frontend event derivation, filtering, and stage classification
 * without modifying any backend or contract files.
 */

import type { AgentEventEnvelope } from '../../hooks/types';

export type FilterCategory = 'all' | 'tools' | 'thoughts' | 'errors';

export interface PipelineStageInfo {
  id: string;
  name: string;
  stageNumber: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'no_data';
  lastActiveTime?: string;
  agentKey: string;
}

export const PIPELINE_STAGES: { id: string; name: string; agentKey: string }[] = [
  { id: 'triage', name: 'Triage', agentKey: 'triage' },
  { id: 'retrieval', name: 'Retrieval', agentKey: 'retrieval' },
  { id: 'planner', name: 'Planner', agentKey: 'planner' },
  { id: 'coder', name: 'Coder', agentKey: 'coder' },
  { id: 'test_runner', name: 'Test Runner', agentKey: 'test_runner' },
  { id: 'debugger', name: 'Debugger', agentKey: 'debugger' },
  { id: 'reviewer', name: 'Reviewer', agentKey: 'reviewer' },
  { id: 'pr_agent', name: 'PR Agent', agentKey: 'pr_agent' },
];

/**
 * Categorizes an envelope into tools / thoughts / errors / general.
 */
export function categorizeEvent(evt: AgentEventEnvelope): 'tools' | 'thoughts' | 'errors' | 'other' {
  const type = (evt.eventType || '').toLowerCase();
  const payloadStr = typeof evt.payload === 'object' ? JSON.stringify(evt.payload).toLowerCase() : '';

  if (type.includes('error') || type.includes('fail') || payloadStr.includes('error')) {
    return 'errors';
  }
  if (evt.tool || type.includes('tool')) {
    return 'tools';
  }
  if (type.includes('thought') || type.includes('plan') || type.includes('reason') || type.includes('step')) {
    return 'thoughts';
  }
  return 'other';
}

/**
 * Filters an event stream by selected category.
 */
export function filterEvents(
  events: AgentEventEnvelope[],
  category: FilterCategory
): AgentEventEnvelope[] {
  if (category === 'all') return events;

  return events.filter((evt) => {
    const cat = categorizeEvent(evt);
    if (category === 'tools') return cat === 'tools';
    if (category === 'thoughts') return cat === 'thoughts';
    if (category === 'errors') return cat === 'errors';
    return true;
  });
}

/**
 * Derives pipeline stage statuses strictly from real received events.
 */
export function derivePipelineStages(events: AgentEventEnvelope[]): PipelineStageInfo[] {
  return PIPELINE_STAGES.map((def, idx) => {
    // Find all events associated with this stage's agent
    const matchingEvents = events.filter((evt) => {
      const agent = (evt.agent || '').toLowerCase().replace(/[\s_-]+/g, '');
      const target = def.agentKey.toLowerCase().replace(/[\s_-]+/g, '');
      return agent.includes(target) || target.includes(agent);
    });

    if (matchingEvents.length === 0) {
      return {
        id: def.id,
        name: def.name,
        stageNumber: idx + 1,
        status: 'no_data',
        agentKey: def.agentKey,
      };
    }

    const latest = matchingEvents[matchingEvents.length - 1];
    const type = (latest.eventType || '').toLowerCase();

    let status: PipelineStageInfo['status'] = 'running';
    if (type.includes('finish') || type.includes('complete') || type.includes('pass')) {
      status = 'completed';
    } else if (type.includes('fail') || type.includes('error')) {
      status = 'failed';
    }

    return {
      id: def.id,
      name: def.name,
      stageNumber: idx + 1,
      status,
      lastActiveTime: latest.timestamp,
      agentKey: def.agentKey,
    };
  });
}

/**
 * Quarantined Static Preview demonstration events.
 * Used strictly when in STATIC PREVIEW mode to demonstrate the full UI
 * layout with zero backend dependency.
 */
export const STATIC_PREVIEW_EVENTS: AgentEventEnvelope[] = [
  {
    id: 'evt_preview_01',
    agent: 'Planner',
    step: '1.1',
    eventType: 'agent.step_finish',
    model: 'preview-llm-1',
    timestamp: new Date(Date.now() - 45000).toISOString(),
    payload: {
      message: 'Decomposed repository requirements and identified target files.',
      details: 'Architecture plan finalized with 3 phase deliverables.',
    },
  },
  {
    id: 'evt_preview_02',
    agent: 'Retrieval',
    step: '1.2',
    eventType: 'tool.call_finish',
    tool: 'ripgrep',
    model: 'preview-llm-1',
    timestamp: new Date(Date.now() - 30000).toISOString(),
    payload: {
      query: 'useAgentRunSocket',
      matches: 4,
      path: 'frontend/src/hooks',
    },
  },
  {
    id: 'evt_preview_03',
    agent: 'Coder',
    step: '2.1',
    eventType: 'llm.stream_chunk',
    model: 'preview-llm-2',
    timestamp: new Date(Date.now() - 15000).toISOString(),
    payload: {
      tokenDelta: 'export function LiveConsole({ runId }: LiveConsoleProps)',
      stage: 'implementation',
    },
  },
  {
    id: 'evt_preview_04',
    agent: 'Coder',
    step: '2.2',
    eventType: 'tool.call_start',
    tool: 'patch_file',
    model: 'preview-llm-2',
    timestamp: new Date().toISOString(),
    payload: {
      targetFile: 'frontend/src/components/LiveConsole/LiveConsole.tsx',
      operation: 'modify',
      status: 'in-flight',
    },
  },
];
