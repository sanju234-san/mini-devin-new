/**
 * evalResultsUtils.ts
 *
 * Types, utilities, and quarantined preview fixtures for Task 10: Evaluation Results View.
 * Strictly within Nikunj Nanda's Frontend/UI scope.
 */

export type EvalInspectMode = 'passed' | 'failed' | 'running' | 'empty' | 'unavailable';

export type EvalItemStatus = 'PASSED' | 'FAILED' | 'SKIPPED' | 'RUNNING';

export interface EvalItem {
  id: string;
  name: string;
  symbol: string;
  status: EvalItemStatus;
  score: number;
  maxScore: number;
  durationMs: number;
  errorMessage?: string;
  detailNote?: string;
  severity?: 'High' | 'Medium' | 'Low';
  subcategory: string;
  suite: string;
}

export interface EvaluationSummary {
  runId: string;
  status: string;
  statusBadge: string;
  duration: string;
  repo: string;
  branch: string;
  issue: string;
  suite: string;
  determinism: string;
  taskSuccessPercentage: number;
  criteriaSatisfiedCount: number;
  criteriaTotalCount: number;
  testPassPercentage: number;
  passedCount: number;
  failedCount: number;
  skippedCount: number;
  totalTests: number;
  avgLatencySec: number;
  p95LatencySec: number;
  medianLatencyMs: number;
  totalTokens: number;
  cachedTokensPercentage: number;
  promptTokens: number;
  completionTokens: number;
  cost: string;
}

export interface ScoreTrendPoint {
  runId: string;
  score: number;
  label: string;
  isCurrent?: boolean;
}

export interface OutcomeCategory {
  name: string;
  passed: number;
  total: number;
  failed?: number;
  skipped?: boolean;
  note?: string;
}

export interface OutcomeBreakdownData {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  categories: OutcomeCategory[];
}

export interface ResourceTelemetryData {
  modelLatencySec: number;
  modelLatencyMaxSec: number;
  memoryMb: number;
  memoryMaxMb: number;
  tokenBudget: number;
  tokenBudgetMax: number;
  cost: number;
  costMax: number;
  isolateLimitSec: number;
}

export interface FailureDetails {
  testSymbol: string;
  failureDescription: string;
  testFilePath: string;
  lineNumber: number;
  diffSnippet: {
    removed: string[];
    added: string[];
  };
  callStack: string[];
  sourceFile: string;
  sourceLineNumber: number;
  agentSynthesis: {
    summary: string;
    confidencePercentage: number;
    patchFile: string;
    patchAvailable: boolean;
  };
}

// ============================================================================
// STITCH PREVIEW FIXTURES (Quarantined for offline / completed preview)
// ============================================================================

export const SAMPLE_EVAL_SUMMARY: EvaluationSummary = {
  runId: 'run-8924a',
  status: 'COMPLETED WITH FAILURES',
  statusBadge: 'FAILED (2/15)',
  duration: '00:01:42',
  repo: 'octocat/linguist',
  branch: 'fix/parser-multibyte',
  issue: '#482: UTF-8 multibyte parser bug',
  suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  determinism: 'Verified 100%',
  taskSuccessPercentage: 86.7,
  criteriaSatisfiedCount: 13,
  criteriaTotalCount: 15,
  testPassPercentage: 80.0,
  passedCount: 12,
  failedCount: 2,
  skippedCount: 1,
  totalTests: 15,
  avgLatencySec: 1.42,
  p95LatencySec: 3.41,
  medianLatencyMs: 840,
  totalTokens: 148290,
  cachedTokensPercentage: 82.4,
  promptTokens: 112000,
  completionTokens: 36200,
  cost: '$0.042',
};

export const SAMPLE_SCORE_TREND: ScoreTrendPoint[] = [
  { runId: '8918', score: 72, label: '-8918' },
  { runId: '8919', score: 78, label: '-8919' },
  { runId: '8920', score: 75, label: '-8920' },
  { runId: '8921', score: 84, label: '-8921' },
  { runId: '8922', score: 79, label: '-8922' },
  { runId: '8923', score: 86, label: '-8923' },
  { runId: '8924a', score: 86.7, label: '-8924a', isCurrent: true },
];

export const SAMPLE_OUTCOME_BREAKDOWN: OutcomeBreakdownData = {
  total: 15,
  passed: 12,
  failed: 2,
  skipped: 1,
  categories: [
    {
      name: 'Syntax & AST Parser',
      passed: 3,
      total: 3,
    },
    {
      name: 'Multi-byte UTF-8 Tokenizer',
      passed: 2,
      total: 4,
      failed: 2,
    },
    {
      name: 'Regression Corpus (Ruby 3.2)',
      passed: 7,
      total: 7,
    },
    {
      name: 'Performance Benchmarks',
      passed: 0,
      total: 1,
      skipped: true,
      note: 'Skipped (--fast)',
    },
  ],
};

export const SAMPLE_RESOURCE_TELEMETRY: ResourceTelemetryData = {
  modelLatencySec: 1.42,
  modelLatencyMaxSec: 5.0,
  memoryMb: 412,
  memoryMaxMb: 1024,
  tokenBudget: 148300,
  tokenBudgetMax: 200000,
  cost: 0.042,
  costMax: 2.0,
  isolateLimitSec: 120,
};

export const SAMPLE_EVAL_ITEMS: EvalItem[] = [
  {
    id: 'eval_item_01',
    name: 'test_multibyte_utf8_boundary',
    symbol: 'test_multibyte_utf8_boundary',
    status: 'FAILED',
    score: 0.0,
    maxScore: 1.0,
    durationMs: 42,
    errorMessage: 'AssertionError: Tokenizer length mi..',
    severity: 'High',
    subcategory: 'Multi-byte UTF-8 Tokenizer',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_02',
    name: 'test_payload_roundtrip',
    symbol: 'test_payload_roundtrip',
    status: 'FAILED',
    score: 0.0,
    maxScore: 1.0,
    durationMs: 18,
    errorMessage: 'AssertionError: Expected 148 got 146',
    severity: 'High',
    subcategory: 'Multi-byte UTF-8 Tokenizer',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_03',
    name: 'Syntax & Keyword Lexer',
    symbol: 'Syntax & Keyword Lexer',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 120,
    detailNote: 'Grammar and tokens parsed without warning',
    subcategory: 'Syntax & AST Parser',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_04',
    name: 'test_c_lexer_fallback',
    symbol: 'test_c_lexer_fallback',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 240,
    detailNote: 'Fallback to Ragel Lexer verified',
    subcategory: 'Syntax & AST Parser',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_05',
    name: 'test_shebang_heuristics',
    symbol: 'test_shebang_heuristics',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 80,
    detailNote: 'Rules parsed: #!/usr/bin/env python',
    subcategory: 'Syntax & AST Parser',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_06',
    name: 'test_ast_grammar_invariants',
    symbol: 'test_ast_grammar_invariants',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 310,
    detailNote: '312 nodes balanced in AST tree',
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_07',
    name: 'test_fixture_corpus_large',
    symbol: 'test_fixture_corpus_large',
    status: 'SKIPPED',
    score: 0.0,
    maxScore: 1.0,
    durationMs: 0,
    detailNote: 'Skipped via test flag --fast',
    subcategory: 'Performance Benchmarks',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_08',
    name: 'test_multibyte_continuation',
    symbol: 'test_multibyte_continuation',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 160,
    detailNote: 'UTF-8 continuation runes intact',
    subcategory: 'Multi-byte UTF-8 Tokenizer',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_09',
    name: 'test_ragel_buffer_offset',
    symbol: 'test_ragel_buffer_offset',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 95,
    detailNote: 'Window size bounded at 4 bytes',
    subcategory: 'Multi-byte UTF-8 Tokenizer',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_10',
    name: 'test_unicode_normalization',
    symbol: 'test_unicode_normalization',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 110,
    detailNote: 'NFC normalization verified',
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_11',
    name: 'test_encoding_detector',
    symbol: 'test_encoding_detector',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 130,
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_12',
    name: 'test_stream_eof_handling',
    symbol: 'test_stream_eof_handling',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 45,
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_13',
    name: 'test_ruby_gem_manifest',
    symbol: 'test_ruby_gem_manifest',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 210,
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_14',
    name: 'test_security_sandbox_boundary',
    symbol: 'test_security_sandbox_boundary',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 75,
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
  {
    id: 'eval_item_15',
    name: 'test_lexer_token_sequence',
    symbol: 'test_lexer_token_sequence',
    status: 'PASSED',
    score: 1.0,
    maxScore: 1.0,
    durationMs: 85,
    subcategory: 'Regression Corpus (Ruby 3.2)',
    suite: 'SWE-bench / Ruby Minitest Regression v2.4',
  },
];

export const SAMPLE_FAILURE_DETAILS: FailureDetails = {
  testSymbol: 'test_multibyte_utf8_boundary',
  failureDescription:
    'Multibyte characters were sliced mid-rune resulting in replacement chars \\uFFFD in chunk buffer boundary.',
  testFilePath: 'test/tokenizer_test.rb',
  lineNumber: 42,
  diffSnippet: {
    removed: ['- ["\\u3053\\u3093\\u306B\\u306F"]'],
    added: ['+ ["\\uFFFD\\uFFFD"]'],
  },
  callStack: [
    "at lib/linguist/tokenizer.rb:45 in 'tokenize'",
    "at test/tokenizer_test.rb:42 in 'block in <class:TestTokenizer>'",
  ],
  sourceFile: 'lib/linguist/tokenizer.rb:45',
  sourceLineNumber: 45,
  agentSynthesis: {
    summary:
      'Coder Agent proposed patch in lib/linguist/scanner.c:142 using a 4-byte lookahead window. Test runner detected boundary overrun at offset 1024.',
    confidencePercentage: 94.8,
    patchFile: 'lib/linguist/scanner.c:142',
    patchAvailable: true,
  },
};

/**
 * Safely maps raw response from GET /api/v1/metrics or run evaluation endpoint
 * to structured evaluation models. Returns null if data is empty or invalid.
 */
export function parseRealMetrics(raw: unknown, defaultRunId: string): {
  summary: EvaluationSummary;
  items: EvalItem[];
  breakdown: OutcomeBreakdownData;
  trend: ScoreTrendPoint[];
  telemetry: ResourceTelemetryData;
} | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;

  // Check if payload contains any actual metrics data
  const hasData =
    'metrics' in obj ||
    'test_pass_rate' in obj ||
    'fix_accuracy' in obj ||
    'runs' in obj ||
    'items' in obj ||
    'criteria' in obj;

  if (!hasData) return null;

  // Derive summary fields honestly from backend response
  const passRate = typeof obj.test_pass_rate === 'number' ? obj.test_pass_rate : 0;
  const fixAccuracy = typeof obj.fix_accuracy === 'number' ? obj.fix_accuracy : 0;
  const criteriaList =
    Array.isArray(obj.items) || Array.isArray(obj.criteria)
      ? ((obj.items || obj.criteria) as Record<string, unknown>[])
      : [];

  const items: EvalItem[] = criteriaList.map((c, idx) => ({
    id: (c.id as string) || `eval_item_${idx}`,
    name: (c.name as string) || (c.symbol as string) || `Test ${idx + 1}`,
    symbol: (c.symbol as string) || (c.name as string) || `test_${idx + 1}`,
    status: (c.status as EvalItemStatus) || (c.passed ? 'PASSED' : 'FAILED'),
    score: typeof c.score === 'number' ? c.score : c.passed ? 1.0 : 0.0,
    maxScore: typeof c.maxScore === 'number' ? c.maxScore : 1.0,
    durationMs: typeof c.durationMs === 'number' ? c.durationMs : 0,
    errorMessage: c.errorMessage as string | undefined,
    detailNote: c.detailNote as string | undefined,
    severity: c.severity as 'High' | 'Medium' | 'Low' | undefined,
    subcategory: (c.subcategory as string) || 'Default Suite',
    suite: (c.suite as string) || 'Test Suite',
  }));

  const passedCount = items.filter((i) => i.status === 'PASSED').length;
  const failedCount = items.filter((i) => i.status === 'FAILED').length;
  const skippedCount = items.filter((i) => i.status === 'SKIPPED').length;
  const totalTests = items.length || 1;

  const summary: EvaluationSummary = {
    runId: (obj.run_id as string) || defaultRunId,
    status: failedCount > 0 ? 'COMPLETED WITH FAILURES' : 'ALL TESTS PASSED',
    statusBadge:
      failedCount > 0
        ? `FAILED (${failedCount}/${totalTests})`
        : `PASSED (${passedCount}/${totalTests})`,
    duration: (obj.duration as string) || '00:00:00',
    repo: (obj.repo as string) || 'Repository',
    branch: (obj.branch as string) || 'main',
    issue: (obj.issue as string) || '#Issue',
    suite: (obj.suite as string) || 'Evaluation Suite',
    determinism: (obj.determinism as string) || '100%',
    taskSuccessPercentage: fixAccuracy || (passedCount / totalTests) * 100,
    criteriaSatisfiedCount: passedCount,
    criteriaTotalCount: totalTests,
    testPassPercentage: passRate || (passedCount / totalTests) * 100,
    passedCount,
    failedCount,
    skippedCount,
    totalTests,
    avgLatencySec: typeof obj.avg_latency_sec === 'number' ? obj.avg_latency_sec : 0,
    p95LatencySec: typeof obj.p95_latency_sec === 'number' ? obj.p95_latency_sec : 0,
    medianLatencyMs: typeof obj.median_latency_ms === 'number' ? obj.median_latency_ms : 0,
    totalTokens: typeof obj.total_tokens === 'number' ? obj.total_tokens : 0,
    cachedTokensPercentage:
      typeof obj.cached_tokens_pct === 'number' ? obj.cached_tokens_pct : 0,
    promptTokens: typeof obj.prompt_tokens === 'number' ? obj.prompt_tokens : 0,
    completionTokens: typeof obj.completion_tokens === 'number' ? obj.completion_tokens : 0,
    cost: (obj.cost as string) || '$0.00',
  };

  const breakdown: OutcomeBreakdownData = {
    total: totalTests,
    passed: passedCount,
    failed: failedCount,
    skipped: skippedCount,
    categories: [
      {
        name: 'Evaluation Suite',
        passed: passedCount,
        total: totalTests,
        failed: failedCount,
      },
    ],
  };

  const trend: ScoreTrendPoint[] = Array.isArray(obj.trend)
    ? (obj.trend as ScoreTrendPoint[])
    : [
        {
          runId: defaultRunId,
          score: summary.testPassPercentage,
          label: `#${defaultRunId}`,
          isCurrent: true,
        },
      ];

  const telemetry: ResourceTelemetryData = {
    modelLatencySec: summary.avgLatencySec,
    modelLatencyMaxSec: 5.0,
    memoryMb: typeof obj.memory_mb === 'number' ? obj.memory_mb : 0,
    memoryMaxMb: 1024,
    tokenBudget: summary.totalTokens,
    tokenBudgetMax: 200000,
    cost: parseFloat(summary.cost.replace(/[^0-9.]/g, '')) || 0,
    costMax: 2.0,
    isolateLimitSec: 120,
  };

  return { summary, items, breakdown, trend, telemetry };
}

