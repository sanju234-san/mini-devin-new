/**
 * TestsAndPreview Utility Types, Parsers, and Preview State Fixtures
 *
 * Implements Task 7 data structures and Stitch design specifications.
 * All preview fixtures are strictly quarantined for preview/demo modes.
 */

export type PreviewState = 'running' | 'passed' | 'failed' | 'skeleton' | 'offline';

export type LogFilterCategory = 'all' | 'stdout' | 'stderr' | 'test_runner';

export type TestResultFilter = 'all' | 'failed' | 'passed';

export type TestItemStatus = 'passed' | 'failed' | 'skipped';

export interface TestCaseResult {
  id: string;
  name: string;
  status: TestItemStatus;
  durationMs: number;
  filePath: string;
  lineNumber?: number;
  assertionError?: string;
  description?: string;
  inlineDiff?: {
    expected: string;
    actual: string;
  };
  stackTraceLocation?: string;
  targetFile?: string;
}

export interface TestSuiteSummary {
  status: 'RUNNING' | 'PASSED' | 'FAILED' | 'OFFLINE';
  totalTests: number;
  executedTests: number;
  passedCount: number;
  failedCount: number;
  skippedCount: number;
  durationSec: number;
  concurrency: string;
  exitCode: number | null;
  isolationStatus: 'Healthy' | 'Degraded' | 'Offline';
  resourceLoadPercent: number;
  memoryUsageMb: number;
  sandboxVmId: string;
}

export interface LogLine {
  id: string;
  timestamp: string;
  tag: 'info' | 'test' | 'pass' | 'fail' | 'warn' | 'skip';
  category: 'stdout' | 'stderr' | 'test_runner';
  content: string;
  details?: {
    expected?: string;
    actual?: string;
    location?: string;
  };
}

// ============================================================================
// STITCH PREVIEW FIXTURES (MIRRORING ATTACHED SCREENSHOT)
// ============================================================================

export const RUNNING_LOGS: LogLine[] = [
  {
    id: 'log-01',
    timestamp: '10:42:01',
    tag: 'info',
    category: 'stdout',
    content: 'Bootstrapping Docker sandbox: ruby-3.2.2-slim with jemalloc allocator...',
  },
  {
    id: 'log-02',
    timestamp: '10:42:03',
    tag: 'info',
    category: 'stdout',
    content: 'Cloning octocat/linguist @ fix/parser-multibyte (commit 4b8d72e)...',
  },
  {
    id: 'log-03',
    timestamp: '10:42:04',
    tag: 'info',
    category: 'stdout',
    content: 'Applying AST patch to lib/linguist/tokenizer.rb (+28, -12 lines)...',
  },
  {
    id: 'log-04',
    timestamp: '10:42:05',
    tag: 'info',
    category: 'stdout',
    content: 'Running dependency audit: bundle install --frozen-lockfile (cache hit 2.1s)...',
  },
  {
    id: 'log-05',
    timestamp: '10:42:07',
    tag: 'test',
    category: 'test_runner',
    content: 'Starting Minitest runner suite (15 total tests, concurrency: 4 workers)...',
  },
  {
    id: 'log-06',
    timestamp: '10:42:08',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/test_basic_tokenization.rb (0.12s)',
  },
  {
    id: 'log-07',
    timestamp: '10:42:09',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/test_c_lexer_fallback.rb (0.24s)',
  },
  {
    id: 'log-08',
    timestamp: '10:42:10',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/test_shebang_heuristics.rb (0.08s)',
  },
  {
    id: 'log-09',
    timestamp: '10:42:11',
    tag: 'fail',
    category: 'stderr',
    content: 'FAIL test/tokenizer_test.rb:42:test_multibyte_utf8_boundary',
    details: {
      expected: '["\\u3053\\u3093\\u306B\\u306F", "world"]',
      actual: '["\\uFFFD\\uFFFD", "world"]',
      location: 'lib/linguist/tokenizer.rb:45:in `tokenize\'',
    },
  },
  {
    id: 'log-10',
    timestamp: '10:42:13',
    tag: 'warn',
    category: 'stderr',
    content: 'WARN: Deprecated regexp flag /u ignored in modern Ruby 3.2 runtime context',
  },
  {
    id: 'log-11',
    timestamp: '10:42:14',
    tag: 'fail',
    category: 'stderr',
    content: 'FAIL test/test_json_benchmark.rb:18:test_payload_roundtrip\n      AssertionError: Tokenizer length mismatch: expected 148, got 146',
  },
  {
    id: 'log-12',
    timestamp: '10:42:15',
    tag: 'skip',
    category: 'test_runner',
    content: 'SKIP test/test_fixture_corpus.rb (flag --fast enabled)',
  },
  {
    id: 'log-13',
    timestamp: '10:42:16',
    tag: 'info',
    category: 'test_runner',
    content: '12 passed, 2 failed, 1 skipped in 14.82s',
  },
];

export const PASSED_LOGS: LogLine[] = [
  {
    id: 'pass-01',
    timestamp: '10:42:01',
    tag: 'info',
    category: 'stdout',
    content: 'Bootstrapping Docker sandbox: ruby-3.2.2-slim with jemalloc allocator...',
  },
  {
    id: 'pass-02',
    timestamp: '10:42:03',
    tag: 'info',
    category: 'stdout',
    content: 'Applying updated AST patch to lib/linguist/tokenizer.rb...',
  },
  {
    id: 'pass-03',
    timestamp: '10:42:06',
    tag: 'test',
    category: 'test_runner',
    content: 'Running Minitest suite with full UTF-8 codepoint regression assertions...',
  },
  {
    id: 'pass-04',
    timestamp: '10:42:08',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/tokenizer_test.rb:42:test_multibyte_utf8_boundary (0.04s)',
  },
  {
    id: 'pass-05',
    timestamp: '10:42:09',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/test_json_benchmark.rb:18:test_payload_roundtrip (0.02s)',
  },
  {
    id: 'pass-06',
    timestamp: '10:42:10',
    tag: 'pass',
    category: 'test_runner',
    content: 'PASS test/test_basic_tokenization.rb (0.11s)',
  },
  {
    id: 'pass-07',
    timestamp: '10:42:12',
    tag: 'info',
    category: 'test_runner',
    content: 'ALL 15 TESTS PASSED in 11.45s (Exit Code: 0). Verification gate cleared.',
  },
];

export const FAILED_LOGS: LogLine[] = [
  ...RUNNING_LOGS,
  {
    id: 'fail-01',
    timestamp: '10:42:18',
    tag: 'fail',
    category: 'stderr',
    content: 'ERROR: Test suite terminated with non-zero exit code (1). 2 regression tests failed.',
  },
  {
    id: 'fail-02',
    timestamp: '10:42:19',
    tag: 'warn',
    category: 'stderr',
    content: 'Sandbox container halted. Logs preserved for Debugger agent revision.',
  },
];

export const RUNNING_TEST_CASES: TestCaseResult[] = [
  {
    id: 'tc-1',
    name: 'test_multibyte_utf8_boundary',
    status: 'failed',
    durationMs: 42,
    filePath: 'test/tokenizer_test.rb:42',
    assertionError: 'Expected token match for UTF-8 boundary',
    description: 'Multibyte characters were sliced mid-rune resulting in replacement chars \\uFFFD.',
    inlineDiff: {
      expected: '["\\u3053\\u3093\\u306B\\u306F", "world"]',
      actual: '["\\uFFFD\\uFFFD", "world"]',
    },
    stackTraceLocation: 'at lib/linguist/tokenizer.rb:45:in `tokenize\'',
    targetFile: 'lib/linguist/tokenizer.rb',
  },
  {
    id: 'tc-2',
    name: 'test_payload_roundtrip',
    status: 'failed',
    durationMs: 18,
    filePath: 'test/test_json_benchmark.rb:18',
    assertionError: 'AssertionError: Tokenizer length mismatch: expected 148, got 146',
    targetFile: 'lib/linguist/tokenizer.rb',
  },
  {
    id: 'tc-3',
    name: 'test_basic_tokenization',
    status: 'passed',
    durationMs: 120,
    filePath: 'test/test_basic_tokenization.rb',
  },
  {
    id: 'tc-4',
    name: 'test_c_lexer_fallback',
    status: 'passed',
    durationMs: 240,
    filePath: 'test/test_c_lexer_fallback.rb',
  },
  {
    id: 'tc-5',
    name: 'test_shebang_heuristics',
    status: 'passed',
    durationMs: 80,
    filePath: 'test/test_shebang_heuristics.rb',
  },
  {
    id: 'tc-6',
    name: 'test_fixture_corpus',
    status: 'skipped',
    durationMs: 0,
    filePath: 'test/test_fixture_corpus.rb',
    description: 'Skipped: --fast flag enabled',
  },
];

export const PASSED_TEST_CASES: TestCaseResult[] = RUNNING_TEST_CASES.map((tc) => ({
  ...tc,
  status: tc.status === 'skipped' ? 'skipped' : 'passed',
  assertionError: undefined,
  inlineDiff: undefined,
  description: tc.status === 'skipped' ? tc.description : undefined,
}));

export const FAILED_TEST_CASES: TestCaseResult[] = RUNNING_TEST_CASES;

export const RUNNING_SUMMARY: TestSuiteSummary = {
  status: 'RUNNING',
  totalTests: 15,
  executedTests: 15,
  passedCount: 12,
  failedCount: 2,
  skippedCount: 1,
  durationSec: 14.8,
  concurrency: '4/4',
  exitCode: 1,
  isolationStatus: 'Healthy',
  resourceLoadPercent: 38,
  memoryUsageMb: 412,
  sandboxVmId: 'sandbox-vm-e8a',
};

export const PASSED_SUMMARY: TestSuiteSummary = {
  status: 'PASSED',
  totalTests: 15,
  executedTests: 15,
  passedCount: 14,
  failedCount: 0,
  skippedCount: 1,
  durationSec: 11.4,
  concurrency: '4/4',
  exitCode: 0,
  isolationStatus: 'Healthy',
  resourceLoadPercent: 24,
  memoryUsageMb: 380,
  sandboxVmId: 'sandbox-vm-e8a',
};

export const FAILED_SUMMARY: TestSuiteSummary = {
  status: 'FAILED',
  totalTests: 15,
  executedTests: 15,
  passedCount: 12,
  failedCount: 2,
  skippedCount: 1,
  durationSec: 14.8,
  concurrency: '4/4',
  exitCode: 1,
  isolationStatus: 'Healthy',
  resourceLoadPercent: 42,
  memoryUsageMb: 430,
  sandboxVmId: 'sandbox-vm-e8a',
};

export const OFFLINE_SUMMARY: TestSuiteSummary = {
  status: 'OFFLINE',
  totalTests: 0,
  executedTests: 0,
  passedCount: 0,
  failedCount: 0,
  skippedCount: 0,
  durationSec: 0,
  concurrency: '0/0',
  exitCode: null,
  isolationStatus: 'Offline',
  resourceLoadPercent: 0,
  memoryUsageMb: 0,
  sandboxVmId: 'none',
};

/**
 * Formats a LogLine object with ANSI escape sequences for xterm.js rendering
 */
export function formatLogLineForXterm(line: LogLine, index: number): string {
  const lineNum = String(index + 1).padStart(2, '0');
  const dim = '\x1b[90m';
  const reset = '\x1b[0m';
  const bold = '\x1b[1m';

  // Tag styling
  let tagColor = '\x1b[36m'; // cyan
  if (line.tag === 'pass') tagColor = '\x1b[32m'; // green
  if (line.tag === 'fail') tagColor = '\x1b[91m'; // bright red
  if (line.tag === 'warn') tagColor = '\x1b[33m'; // yellow
  if (line.tag === 'skip') tagColor = '\x1b[90m'; // gray

  let formatted = `${dim}${lineNum}${reset}  ${dim}[${line.timestamp}]${reset} ${tagColor}[${line.tag}]${reset} `;

  if (line.tag === 'fail') {
    formatted += `\x1b[91m${line.content}${reset}\r\n`;
    if (line.details) {
      if (line.details.expected && line.details.actual) {
        formatted += `      ${dim}Expected:${reset} \x1b[32m${line.details.expected}${reset}\r\n`;
        formatted += `      ${dim}Actual:  ${reset} \x1b[31m${line.details.actual}${reset}\r\n`;
        formatted += `      ${dim}Inline Diff:${reset}\r\n`;
        formatted += `      \x1b[31m- ${line.details.expected}\x1b[0m\r\n`;
        formatted += `      \x1b[32m+ ${line.details.actual}\x1b[0m\r\n`;
      }
      if (line.details.location) {
        formatted += `      ${dim}at ${line.details.location}${reset}\r\n`;
      }
    }
  } else if (line.tag === 'pass') {
    formatted += `\x1b[32m${line.content}${reset}\r\n`;
  } else if (line.tag === 'warn') {
    formatted += `\x1b[33m${line.content}${reset}\r\n`;
  } else if (line.tag === 'test') {
    formatted += `\x1b[36m${line.content}${reset}\r\n`;
  } else {
    formatted += `${line.content}\r\n`;
  }

  return formatted;
}
