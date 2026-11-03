/**
 * transparencyUtils.ts
 *
 * Types, converters, and quarantined preview fixtures for Task 9: Model / Agent Transparency.
 * Designed strictly within Nikunj Nanda's Frontend/UI scope.
 */

import type { AgentEventEnvelope } from '../../hooks/types';

export type TransparencyInspectMode = 'completed' | 'live' | 'empty' | 'disconnected';

export type AgentStageStatus =
  | 'done'
  | 'running'
  | 'queued'
  | 'pending'
  | 'verified'
  | 'failed'
  | 'no_data';

export type ProviderType = 'llm' | 'classifier' | 'hitl' | 'sandbox' | 'bot' | 'static';

export interface AgentStage {
  id: string;
  name: string;
  stepNumber: number;
  duration?: string;
  summary: string;
  status: AgentStageStatus;
  modelBadge: string;
  providerType: ProviderType;
}

export interface ModelMetrics {
  tokenIngestion: {
    total: number;
    prompt: number;
    completion: number;
    cachePercentage: number;
  };
  invocations: {
    total: number;
    avgLatencyMs: number;
    failures: number;
    p95Ms: number;
    slaPercentage: number;
  };
  contextWindow: {
    currentTokens: number;
    maxTokens: number;
    saturationPercentage: number;
    headroomTokens: number;
  };
  reasoning: {
    decisionsCount: number;
    rollbacks: number;
    treeDepth: number;
    guardrailsPassRate: number;
    confidencePercentage: number;
  };
}

export interface CallInspectorData {
  callId: string;
  status: 'SUCCESS' | 'FAILED' | 'RUNNING';
  modelId: string;
  parameters: {
    temperature: number;
    top_p: number;
  };
  stopReason: string;
  systemPromptSha: string;
  tokenAccounting: {
    inputTokens: number;
    outputTokens: number;
    cacheReadTokens: number;
    savedViaCache: string;
  };
  emittedTools: {
    name: string;
    status: 'Executed' | 'Cached' | 'Failed';
  }[];
  systemPersonaExcerpt: string;
}

export interface SafetyGuardrailsData {
  passedCount: number;
  totalCount: number;
  checks: {
    name: string;
    passed: boolean;
  }[];
  hallucinationRisk: {
    score: number;
    label: 'Low' | 'Medium' | 'High';
  };
  scratchpadVariables: {
    key: string;
    value: string;
  }[];
}

export interface TransparencyEvent {
  id: string;
  agent: string;
  timestamp: string;
  timeFormatted: string;
  eventType: string;
  category: 'all' | 'tools' | 'thoughts' | 'decisions';
  badgeLabel: string;
  title: string;
  content: string;
  subContent?: string;
  model?: string;
  isClassifier?: boolean;
  tokensInfo?: string;
  durationInfo?: string;
  sandboxId?: string;
  exitCode?: number;
  depth?: number;
  confidence?: number;
  hallucinationScore?: string;
  contextRef?: string;
  toolCallName?: string;
  diffSummary?: string;
}

// ============================================================================
// STITCH PREVIEW FIXTURES (Quarantined for offline / completed preview)
// ============================================================================

export const SAMPLE_STAGES: AgentStage[] = [
  {
    id: 'triage',
    name: 'TRIAGE',
    stepNumber: 1,
    duration: '4.2s',
    summary: 'Bug: tokenizer crash',
    status: 'done',
    modelBadge: 'Haiku',
    providerType: 'llm',
  },
  {
    id: 'retrieval',
    name: 'RETRIEVAL',
    stepNumber: 2,
    duration: '18.6s',
    summary: '14 AST files index',
    status: 'done',
    modelBadge: 'Voyage-2',
    providerType: 'classifier',
  },
  {
    id: 'planner',
    name: 'PLANNER',
    stepNumber: 3,
    duration: '24.1s',
    summary: 'Plan v2.md synthesized',
    status: 'done',
    modelBadge: 'Sonnet',
    providerType: 'llm',
  },
  {
    id: 'human_gate',
    name: 'HUMAN GATE',
    stepNumber: 4,
    duration: '1m 12s',
    summary: '@octocat approved',
    status: 'verified',
    modelBadge: 'HITL',
    providerType: 'hitl',
  },
  {
    id: 'coder',
    name: 'CODER',
    stepNumber: 5,
    duration: '48.3s',
    summary: 'Patch +42 / -18',
    status: 'done',
    modelBadge: 'Sonnet',
    providerType: 'llm',
  },
  {
    id: 'test_runner',
    name: 'TEST RUNNER',
    stepNumber: 6,
    duration: '14.8s',
    summary: 'Minitest (15...)',
    status: 'running',
    modelBadge: 'Sandbox VM',
    providerType: 'sandbox',
  },
  {
    id: 'debugger',
    name: 'DEBUGGER',
    stepNumber: 7,
    duration: '--',
    summary: 'Await failure traces',
    status: 'queued',
    modelBadge: 'Auto',
    providerType: 'bot',
  },
  {
    id: 'reviewer',
    name: 'REVIEWER',
    stepNumber: 8,
    duration: '--',
    summary: 'Sanity & PR draft',
    status: 'pending',
    modelBadge: 'PR Bot',
    providerType: 'bot',
  },
];

export const SAMPLE_METRICS: ModelMetrics = {
  tokenIngestion: {
    total: 148290,
    prompt: 118400,
    completion: 29890,
    cachePercentage: 82.4,
  },
  invocations: {
    total: 14,
    avgLatencyMs: 1420,
    failures: 0,
    p95Ms: 3410,
    slaPercentage: 100,
  },
  contextWindow: {
    currentTokens: 85600,
    maxTokens: 200000,
    saturationPercentage: 42.8,
    headroomTokens: 114400,
  },
  reasoning: {
    decisionsCount: 37,
    rollbacks: 0,
    treeDepth: 6,
    guardrailsPassRate: 100,
    confidencePercentage: 94.2,
  },
};

export const SAMPLE_CALL_INSPECTOR: CallInspectorData = {
  callId: 'call_8f92a10',
  status: 'SUCCESS',
  modelId: 'anthropic/claude-3.5-sonnet',
  parameters: {
    temperature: 0.2,
    top_p: 0.95,
  },
  stopReason: 'tool_use (natural completion)',
  systemPromptSha: '7c09f029...e01',
  tokenAccounting: {
    inputTokens: 28490,
    outputTokens: 1840,
    cacheReadTokens: 24100,
    savedViaCache: '$0.089 SAVED VIA PROMPT CACHE',
  },
  emittedTools: [
    { name: 'apply_unified_patch', status: 'Executed' },
    { name: 'read_ast_symbol', status: 'Cached' },
  ],
  systemPersonaExcerpt:
    '<system_persona>\nYou are Mini-Devin, a precision software engineer autonomous agent. You reason through state machines, maintain rigorous backwards compatibility, emit unified diff patches with minimal footprint, and verify all invariants via unit tests.\n</system_persona>',
};

export const SAMPLE_SAFETY_GUARDRAILS: SafetyGuardrailsData = {
  passedCount: 6,
  totalCount: 6,
  checks: [
    { name: 'No credential leaks', passed: true },
    { name: 'Shell escape bounds', passed: true },
    { name: 'Valid AST grammar', passed: true },
    { name: 'Bounded loop check', passed: true },
  ],
  hallucinationRisk: {
    score: 0.04,
    label: 'Low',
  },
  scratchpadVariables: [
    { key: '$BUFFER_SIZE', value: '1024 bytes (fixed)' },
    { key: '$MAX_CODEPOINT_LEN', value: '4 bytes (RFC-3629)' },
    { key: '$TARGET_SUITE', value: 'test/test_tokenizer.rb' },
    { key: '$FAILURE_CLASSIFICATION', value: 'Split-Codepoint-Truncation' },
  ],
};

export const SAMPLE_ACTIVITY_EVENTS: TransparencyEvent[] = [
  {
    id: 'evt_tr_01',
    agent: 'Test-Runner Agent',
    timestamp: '2026-10-15T10:42:15Z',
    timeFormatted: '10:42:15',
    eventType: 'tool_execution',
    category: 'tools',
    badgeLabel: 'Tool Exec',
    title: 'Executed bash command: bundle exec rake test TEST=test/test_tokenizer.rb',
    content:
      'Minitest Failure Detected in test_multibyte_utf8_boundary [app/test/test_tokenizer.rb:142]\n1) Failure:\nTestTokenizer#test_multibyte_utf8_boundary [app/test/test_tokenizer.rb:142]\nExpected: "valid_token_utf8"\nActual: "\\xEF\\xDF\\xDD (Malformed UTF-8 at byte 1024)"\nrake aborted! Command failed with status (1)',
    sandboxId: 'sandbox-vm-c8a',
    exitCode: 1,
    subContent: 'Handing trace to Debugger Agent → View full sandbox logs',
  },
  {
    id: 'evt_tr_02',
    agent: 'Coder Agent',
    timestamp: '2026-10-15T10:42:06Z',
    timeFormatted: '10:42:06',
    eventType: 'model_completion',
    category: 'tools',
    badgeLabel: 'Model Completion',
    title: 'Claude 3.5 Sonnet generated patch for lib/linguist/scanner.c',
    content:
      'Tool Call: write_file_patch\nTarget: scanner.c:advance_multibyte_stream() with bounded 4-byte UTF-8 sequence forward scanner.',
    model: 'anthropic/claude-3.5-sonnet',
    isClassifier: false,
    tokensInfo: '4,120 tokens',
    durationInfo: '3.4s',
    toolCallName: 'write_file_patch',
    diffSummary: '+42 / -18 lines',
  },
  {
    id: 'evt_tr_03',
    agent: 'Coder Agent',
    timestamp: '2026-10-15T10:41:52Z',
    timeFormatted: '10:41:52',
    eventType: 'chain_of_thought',
    category: 'thoughts',
    badgeLabel: 'Chain-of-Thought (Scratchpad)',
    title: 'AGENT SELF-REFLECTION',
    content:
      '"Analyzing UTF-8 chunk boundary edge cases where multibyte glyphs span 1024-byte buffer boundaries. If a 4-byte sequence begins at byte 1023, reading 1 byte leaves the stream in an incomplete codepoint state. Injecting sliding cursor lookahead to accumulate continuation bytes prior to delegating to the Ragel state machine."',
    depth: 4,
    confidence: 96.8,
    hallucinationScore: 'Pass (<0.02)',
    contextRef: '#AST_CHUNK_SCANNER',
  },
  {
    id: 'evt_tr_04',
    agent: 'Planner Agent',
    timestamp: '2026-10-15T10:41:10Z',
    timeFormatted: '10:41:10',
    eventType: 'strategic_rationale',
    category: 'decisions',
    badgeLabel: 'Strategic Rationale',
    title: 'Decomposed reproduction strategy into 3 sub-phases:',
    content:
      '• Synthesize failing reproduction test isolating multi-byte boundary slices in Ruby Minitest.\n• Modify C extension scanner.c to handle 1..4 byte UTF-8 window buffers.\n• Execute regression suite across all 250 repository language sample fixtures.',
    model: 'claude-3.5-sonnet',
    isClassifier: false,
    contextRef: 'Plan v2.md',
  },
  {
    id: 'evt_tr_05',
    agent: 'Retrieval Agent',
    timestamp: '2026-10-15T10:40:22Z',
    timeFormatted: '10:40:22',
    eventType: 'vector_search',
    category: 'tools',
    badgeLabel: 'Vector Search',
    title: 'Query: "tokenizer multibyte encoding UTF-8 buffer slicing"',
    content: 'lib/linguist/tokenizer.rb  0.94 score   lib/linguist/scanner.c  0.91 score',
    model: 'Voyage-Code-2',
    isClassifier: true,
  },
];

// ============================================================================
// CONVERTER: Transform real WebSocket envelopes to Transparency Events
// ============================================================================

export function convertEnvelopesToTransparencyEvents(
  envelopes: AgentEventEnvelope[]
): TransparencyEvent[] {
  return envelopes.map((env, idx) => {
    const rawTime = env.timestamp ? new Date(env.timestamp) : new Date();
    const timeFormatted = isNaN(rawTime.getTime())
      ? '00:00:00'
      : rawTime.toLocaleTimeString();

    const eventTypeLower = (env.eventType || '').toLowerCase();
    const agent = env.agent || 'SYSTEM';

    let category: TransparencyEvent['category'] = 'tools';
    let badgeLabel = 'Event';

    if (eventTypeLower.includes('tool') || env.tool) {
      category = 'tools';
      badgeLabel = 'Tool Exec';
    } else if (
      eventTypeLower.includes('thought') ||
      eventTypeLower.includes('reason') ||
      eventTypeLower.includes('reflect')
    ) {
      category = 'thoughts';
      badgeLabel = 'Chain-of-Thought';
    } else if (
      eventTypeLower.includes('plan') ||
      eventTypeLower.includes('decision') ||
      eventTypeLower.includes('gate')
    ) {
      category = 'decisions';
      badgeLabel = 'Decision Branch';
    } else {
      category = 'tools';
      badgeLabel = env.eventType || 'Step';
    }

    const payloadObj =
      typeof env.payload === 'object' && env.payload !== null
        ? (env.payload as Record<string, unknown>)
        : {};

    const title =
      (payloadObj.message as string) ||
      (payloadObj.query as string) ||
      env.tool ||
      `Step ${env.step || idx + 1}`;

    const content =
      (payloadObj.details as string) ||
      (payloadObj.tokenDelta as string) ||
      (payloadObj.targetFile ? `Target: ${payloadObj.targetFile}` : '') ||
      JSON.stringify(env.payload || env.raw || {}, null, 2);

    return {
      id: env.id || `live_evt_${idx}`,
      agent,
      timestamp: env.timestamp || new Date().toISOString(),
      timeFormatted,
      eventType: env.eventType || 'agent.step',
      category,
      badgeLabel,
      title,
      content,
      model: env.model,
      // Note: In real live data, kind is not supplied, so we do not infer isClassifier
      isClassifier: false,
      toolCallName: env.tool,
    };
  });
}
