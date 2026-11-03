import { describe, it, expect } from 'vitest';
import {
  categorizeEvent,
  filterEvents,
  derivePipelineStages,
  PIPELINE_STAGES,
} from '../liveConsoleUtils';
import type { AgentEventEnvelope } from '../../../hooks/types';
import { TEST_FIXTURE_EVENT_ENVELOPE } from '../../../test-fixtures/testDataFixtures';

describe('Live Console Event Derivation & Filters (Task 4)', () => {
  it('correctly categorizes tool calls, errors, thoughts, and general events', () => {
    expect(categorizeEvent(TEST_FIXTURE_EVENT_ENVELOPE)).toBe('tools');

    const errorEvent: AgentEventEnvelope = {
      eventType: 'failed',
      agent: 'Test-Runner',
      payload: { error: 'AssertionError: Length mismatch' },
    };
    expect(categorizeEvent(errorEvent)).toBe('errors');

    const thoughtEvent: AgentEventEnvelope = {
      eventType: 'agent.step_finish',
      agent: 'Planner',
      payload: { message: 'Decomposed plan into 3 phases' },
    };
    expect(categorizeEvent(thoughtEvent)).toBe('thoughts');
  });

  it('filters event stream cleanly without mutating original array', () => {
    const events: AgentEventEnvelope[] = [
      TEST_FIXTURE_EVENT_ENVELOPE, // tool
      { eventType: 'failed', agent: 'Test-Runner' }, // error
      { eventType: 'thought', agent: 'Planner' }, // thought
    ];

    expect(filterEvents(events, 'all')).toHaveLength(3);
    expect(filterEvents(events, 'tools')).toHaveLength(1);
    expect(filterEvents(events, 'errors')).toHaveLength(1);
    expect(filterEvents(events, 'thoughts')).toHaveLength(1);
  });

  it('derives accurate 8-stage pipeline statuses based on received node events', () => {
    const events: AgentEventEnvelope[] = [
      {
        agent: 'Triage',
        eventType: 'completed',
        timestamp: '10:41:14Z',
      },
      {
        agent: 'Retrieval',
        eventType: 'completed',
        timestamp: '10:41:18Z',
      },
      {
        agent: 'Planner',
        eventType: 'completed',
        timestamp: '10:41:24Z',
      },
      {
        agent: 'Coder',
        eventType: 'completed',
        timestamp: '10:42:02Z',
      },
      {
        agent: 'Test Runner',
        eventType: 'failed',
        timestamp: '10:42:21Z',
      },
    ];

    const stages = derivePipelineStages(events);
    expect(stages).toHaveLength(8);

    // Stage 1 (Triage) completed
    expect(stages[0].id).toBe('triage');
    expect(stages[0].status).toBe('completed');

    // Stage 5 (Test Runner) failed
    const testRunnerStage = stages.find((s) => s.id === 'test_runner');
    expect(testRunnerStage?.status).toBe('failed');

    // Stage 7 (Debugger) has no events yet
    const debuggerStage = stages.find((s) => s.id === 'debugger');
    expect(debuggerStage?.status).toBe('no_data');
  });
});
