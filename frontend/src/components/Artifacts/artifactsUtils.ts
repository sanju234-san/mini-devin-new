/**
 * Artifact Trail Viewer Types, Utilities & Stitch Preview Fixtures
 *
 * Implements Task 8 data structures matching the Stitch design specification.
 * Supports Plans, Code Patches, Test Logs/XML, AST Trees, Screenshots, and Manifests.
 */

export type InspectState = 'active' | 'loading' | 'empty' | 'unavailable';

export type ArtifactType =
  | 'all'
  | 'plan'
  | 'patch'
  | 'test_suite'
  | 'log'
  | 'image'
  | 'manifest'
  | 'expired';

export type ViewModeTab =
  | 'formatted'
  | 'raw'
  | 'manifest'
  | 'provenance';

export interface ArtifactItem {
  id: string;
  name: string;
  type: 'plan' | 'patch' | 'test_suite' | 'log' | 'image' | 'manifest' | 'expired';
  typeLabel: string;
  sizeBytes: number;
  sizeFormatted: string;
  createdAt: string;
  timestampFormatted: string;
  sha256: string;
  mimeType: string;
  status: 'available' | 'purged';
  linesCount?: number;
  wordsCount?: number;
  content: string;
  rawSource: string;
  metaBadge?: string;
  diffSummary?: {
    added: number;
    deleted: number;
  };
  testSummary?: {
    passed: number;
    failed: number;
  };
  imageResolution?: string;
  manifestJson?: Record<string, unknown>;
  provenanceTrail?: {
    originatingAgent: string;
    stepNumber: number;
    modelUsed: string;
    executionDuration: string;
    gitCommit: string;
    verifiedSignature: string;
  };
}

export interface ArtifactMetrics {
  totalArtifacts: number;
  indexedPercentage: number;
  plansAndDocsCount: number;
  plansAndDocsSize: string;
  codeChangesCount: number;
  codeChangesDelta: string;
  testReportsCount: number;
  testReportsFormat: string;
  screenshotsCount: number;
  screenshotsLabel: string;
  astAndLogsCount: number;
  astAndLogsLabel: string;
  totalSizeMb: number;
  quotaSizeMb: number;
}

// ============================================================================
// STITCH PREVIEW FIXTURES
// ============================================================================

export const SAMPLE_METRICS: ArtifactMetrics = {
  totalArtifacts: 14,
  indexedPercentage: 100,
  plansAndDocsCount: 2,
  plansAndDocsSize: '34.2 KB',
  codeChangesCount: 3,
  codeChangesDelta: '+128 / -42',
  testReportsCount: 4,
  testReportsFormat: 'JUnit & TAP',
  screenshotsCount: 2,
  screenshotsLabel: 'Render Diff',
  astAndLogsCount: 3,
  astAndLogsLabel: 'Streams & AST',
  totalSizeMb: 2.4,
  quotaSizeMb: 50,
};

export const SAMPLE_ARTIFACTS: ArtifactItem[] = [
  {
    id: 'art-01',
    name: 'implementation_plan_v2.md',
    type: 'plan',
    typeLabel: 'PLAN',
    sizeBytes: 15155,
    sizeFormatted: '14.8 KB',
    createdAt: '2026-10-15T10:42:04Z',
    timestampFormatted: '10:42:04',
    sha256: 'a8f2c0199f3458b29f0ce4a108b3c99023ab8d72e811c0f4931a29388ffc019a',
    mimeType: 'text/markdown',
    status: 'available',
    linesCount: 84,
    wordsCount: 1420,
    metaBadge: 'PLAN DOCUMENT',
    content: `# Autonomous Agent Strategic Rationale (Confidence Score: 94.8%)

## 01 // IMPLEMENTATION STEPS (3 of 4 phases completed)

- [x] **Synthesize failing reproduction test suite in \`test/test_multibyte_utf8.rb\`** (10:41:40)
  Asserted expected token output against sample files containing UTF-8 glyphs (emoji, CJK, and multi-codepoint sequences).
- [x] **Patch tokenizer scanner chunking in \`lib/linguist/scanner.c\`** (10:42:06)
  Replace fixed 1024-byte window with multibyte-aware UTF-8 character boundary detection prior to chunk slicing.
- [x] **Recompile native C extensions & run regression suite** (10:42:15)
  Invoked bundle exec rake compile && bundle exec rake test in sandbox container.
- [ ] **Final sanity benchmark and pull request composition** (Pending)
  Measure throughput impact against baseline corpus and submit branch to origin repository.

## 02 // CODE STRUCTURE MODIFICATION
Target File: \`lib/linguist/scanner.c\` (Lines 142–158)`,
    rawSource: `# Autonomous Agent Strategic Rationale
Target: octocat/linguist @ fix/parser-multibyte
Plan Version: v2 (Approved)
Step R1: Multibyte token boundary slicing
Step R2: Regression test harness
Step R3: Performance benchmark under 5% jitter threshold.`,
    manifestJson: {
      schemaVersion: 'v2.1',
      author: 'Planner-Agent-Pro',
      reviewedBy: 'Supervisor Gate',
      status: 'APPROVED',
      revisionCount: 2,
      checksumValid: true,
    },
    provenanceTrail: {
      originatingAgent: 'PlannerAgent (v0.9.4)',
      stepNumber: 2,
      modelUsed: 'gemini-1.5-pro (T1-Heavy)',
      executionDuration: '4.2s',
      gitCommit: '4b8d72e9f01a',
      verifiedSignature: 'sig_rsa_sha256_9941a80f',
    },
  },
  {
    id: 'art-02',
    name: 'parser_multibyte.patch',
    type: 'patch',
    typeLabel: 'PATCH',
    sizeBytes: 8396,
    sizeFormatted: '8.2 KB',
    createdAt: '2026-10-15T10:42:06Z',
    timestampFormatted: '10:42:06',
    sha256: 'bc94821a774209bf018aef943b128c709e45110d984c0172e811f0923ba81109',
    mimeType: 'text/x-diff',
    status: 'available',
    linesCount: 60,
    wordsCount: 480,
    metaBadge: 'UNIFIED DIFF',
    diffSummary: {
      added: 42,
      deleted: 18,
    },
    content: `diff --git a/lib/linguist/scanner.c b/lib/linguist/scanner.c
index 92a10b4..88e4012 100644
--- a/lib/linguist/scanner.c
+++ b/lib/linguist/scanner.c
@@ -142,10 +142,18 @@ static VALUE tokenizer_scan_chunk(VALUE self, VALUE str) {
-    /* Fixed buffer does not slice UTF-8 code point */
-    while (cursor < max_len && *cursor != '\\0') {
-        chunk_buffer[idx++] = *cursor++;
-    }
+    /* Multibyte boundary aware scanner chunking */
+    while (cursor < max_len && *cursor != '\\0') {
+        int seq_len = utf8_codepoint_length(*cursor);
+        if (cursor + seq_len > max_len) {
+            break; /* Defer trailing bytes to next window */
+        }
+        for (int i = 0; i < seq_len; i++) {
+            chunk_buffer[idx++] = *cursor++;
+        }
+    }`,
    rawSource: `--- a/lib/linguist/scanner.c
+++ b/lib/linguist/scanner.c
@@ -142,6 +142,14 @@
+  int seq_len = utf8_codepoint_length(*cursor);`,
    manifestJson: {
      patchFormat: 'git-unified-v1',
      targetRepository: 'octocat/linguist',
      sourceBranch: 'fix/parser-multibyte',
      filesModified: ['lib/linguist/scanner.c', 'lib/linguist/tokenizer.rb'],
      totalHunks: 3,
    },
    provenanceTrail: {
      originatingAgent: 'CoderAgent (v0.9.4)',
      stepNumber: 4,
      modelUsed: 'claude-3-5-sonnet',
      executionDuration: '7.8s',
      gitCommit: 'fix(tokenizer): prevent slicing multibyte characters mid-rune',
      verifiedSignature: 'sig_git_sha256_bc94821a',
    },
  },
  {
    id: 'art-03',
    name: 'minitest_runner_junit.xml',
    type: 'test_suite',
    typeLabel: 'TEST SUITE',
    sizeBytes: 12697,
    sizeFormatted: '12.4 KB',
    createdAt: '2026-10-15T10:42:11Z',
    timestampFormatted: '10:42:11',
    sha256: '4190c74f192b09a4718cd9a93012e84c90e1823901bce47101a93e810a9c8011',
    mimeType: 'application/xml',
    status: 'available',
    linesCount: 42,
    wordsCount: 310,
    metaBadge: 'JUNIT REPORT',
    testSummary: {
      passed: 12,
      failed: 2,
    },
    content: `<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Minitest::TokenizerSuite" tests="15" failures="2" errors="0" skipped="1" time="14.82">
  <testcase name="test_basic_tokenization" classname="TokenizerTest" time="0.120" status="passed"/>
  <testcase name="test_c_lexer_fallback" classname="TokenizerTest" time="0.240" status="passed"/>
  <testcase name="test_shebang_heuristics" classname="TokenizerTest" time="0.080" status="passed"/>
  <testcase name="test_multibyte_utf8_boundary" classname="TokenizerTest" time="0.042" status="failed">
    <failure message="Expected token match for UTF-8 boundary" type="AssertionError">
      Multibyte characters were sliced mid-rune resulting in replacement chars \\uFFFD.
      at lib/linguist/tokenizer.rb:45:in \`tokenize'
    </failure>
  </testcase>
  <testcase name="test_payload_roundtrip" classname="JsonBenchmarkTest" time="0.018" status="failed">
    <failure message="Tokenizer length mismatch: expected 148, got 146" type="AssertionError"/>
  </testcase>
  <testcase name="test_fixture_corpus" classname="CorpusTest" time="0.000" status="skipped">
    <skipped message="Flag --fast enabled"/>
  </testcase>
</testsuite>`,
    rawSource: `<testsuite name="Minitest::TokenizerSuite" tests="15" failures="2" errors="0" skipped="1" time="14.82">`,
    manifestJson: {
      testRunner: 'Minitest v5.20',
      totalAssertions: 48,
      exitCode: 1,
      durationSeconds: 14.82,
    },
    provenanceTrail: {
      originatingAgent: 'TestRunnerAgent (Sandbox)',
      stepNumber: 5,
      modelUsed: 'deterministic-sandbox-exec',
      executionDuration: '14.82s',
      gitCommit: 'ruby-3.2.2-slim-e8a',
      verifiedSignature: 'sig_e2b_sha256_4190c74f',
    },
  },
  {
    id: 'art-04',
    name: 'terminal_stdout_stream.log',
    type: 'log',
    typeLabel: 'LOG',
    sizeBytes: 94310,
    sizeFormatted: '92.1 KB',
    createdAt: '2026-10-15T10:42:16Z',
    timestampFormatted: '10:42:16',
    sha256: '99281a04f981ca9012389e018a4710189ae4710189a018bc94017a0129bc8112',
    mimeType: 'text/plain',
    status: 'available',
    linesCount: 184,
    wordsCount: 2840,
    metaBadge: 'RAW STREAM',
    content: `[10:42:01] [info] Bootstrapping Docker sandbox: ruby-3.2.2-slim with jemalloc allocator...
[10:42:03] [info] Cloning octocat/linguist @ fix/parser-multibyte (commit 4b8d72e)...
[10:42:04] [info] Applying AST patch to lib/linguist/tokenizer.rb (+28, -12 lines)...
[10:42:05] [info] Running dependency audit: bundle install --frozen-lockfile (cache hit 2.1s)...
[10:42:07] [test] Starting Minitest runner suite (15 total tests, concurrency: 4 workers)...
[10:42:08] [pass] PASS test/test_basic_tokenization.rb (0.12s)
[10:42:09] [pass] PASS test/test_c_lexer_fallback.rb (0.24s)
[10:42:10] [pass] PASS test/test_shebang_heuristics.rb (0.08s)
[10:42:11] [fail] FAIL test/tokenizer_test.rb:42:test_multibyte_utf8_boundary
[10:42:13] [warn] WARN: Deprecated regexp flag /u ignored in modern Ruby 3.2 runtime context
[10:42:14] [fail] FAIL test/test_json_benchmark.rb:18:test_payload_roundtrip
[10:42:15] [skip] SKIP test/test_fixture_corpus.rb (flag --fast enabled)
[10:42:16] [info] 12 passed, 2 failed, 1 skipped in 14.82s`,
    rawSource: `[10:42:01] [info] Bootstrapping Docker sandbox...`,
    manifestJson: {
      streamType: 'stdout-stderr-multiplexed',
      encoding: 'UTF-8',
      byteLength: 94310,
      totalLines: 184,
    },
    provenanceTrail: {
      originatingAgent: 'SandboxDaemon',
      stepNumber: 5,
      modelUsed: 'none',
      executionDuration: '16.2s',
      gitCommit: 'vm-instance-e8a',
      verifiedSignature: 'sig_stream_sha256_99281a04',
    },
  },
  {
    id: 'art-05',
    name: 'diff_syntax_preview.png',
    type: 'image',
    typeLabel: 'IMAGE',
    sizeBytes: 253952,
    sizeFormatted: '248 KB',
    createdAt: '2026-10-15T10:42:18Z',
    timestampFormatted: '10:42:18',
    sha256: '772910fa8912e9471901a8470189a0129bc81123901bce47101a93e810a9c801',
    mimeType: 'image/webp',
    status: 'available',
    imageResolution: '1280x800 webp',
    metaBadge: 'RENDER DIFF',
    content: 'IMAGE_PREVIEW_REPRESENTATION',
    rawSource: 'data:image/svg+xml;utf8,<svg ... />',
    manifestJson: {
      dimensions: { width: 1280, height: 800 },
      format: 'WEBP',
      compressionRatio: '84%',
    },
    provenanceTrail: {
      originatingAgent: 'PlaywrightRunner',
      stepNumber: 6,
      modelUsed: 'chromium-headless-v122',
      executionDuration: '1.4s',
      gitCommit: 'playwright-session-1',
      verifiedSignature: 'sig_img_sha256_772910fa',
    },
  },
  {
    id: 'art-06',
    name: 'ast_mutation_tree.json',
    type: 'manifest',
    typeLabel: 'MANIFEST',
    sizeBytes: 5734,
    sizeFormatted: '5.6 KB',
    createdAt: '2026-10-15T10:42:03Z',
    timestampFormatted: '10:42:03',
    sha256: '0189ae4710189a018bc94017a0129bc81123901bce47101a93e810a9c8011928',
    mimeType: 'application/json',
    status: 'available',
    linesCount: 32,
    wordsCount: 220,
    metaBadge: 'VALID JSON',
    content: `{
  "targetLanguage": "Ruby",
  "rootModule": "Linguist::Tokenizer",
  "nodes": [
    {
      "id": "node_01",
      "type": "ClassDef",
      "name": "Tokenizer",
      "file": "lib/linguist/tokenizer.rb",
      "mutations": [
        {
          "type": "ChunkBoundaryOverride",
          "line": 45,
          "severity": "LOW_REGRESSION_RISK",
          "requirementId": "R1"
        }
      ]
    }
  ]
}`,
    rawSource: `{"targetLanguage":"Ruby","rootModule":"Linguist::Tokenizer"}`,
    manifestJson: {
      treeDepth: 4,
      totalAstNodes: 82,
      parserBackend: 'tree-sitter-ruby',
    },
    provenanceTrail: {
      originatingAgent: 'RetrievalAgent (AST)',
      stepNumber: 1,
      modelUsed: 'static-ast-analyzer',
      executionDuration: '0.8s',
      gitCommit: 'ast-snapshot-rev1',
      verifiedSignature: 'sig_ast_sha256_0189ae47',
    },
  },
  {
    id: 'art-07',
    name: 'sandbox_core_dump.bin',
    type: 'expired',
    typeLabel: 'EXPIRED',
    sizeBytes: 1258291,
    sizeFormatted: '1.2 MB',
    createdAt: '2026-10-15T10:30:00Z',
    timestampFormatted: '10:30:00',
    sha256: '0000000000000000000000000000000000000000000000000000000000000000',
    mimeType: 'application/octet-stream',
    status: 'purged',
    metaBadge: 'POLICY TTL',
    content: '[ARTIFACT PURGED BY RETENTION POLICY: Ephemeral sandbox binary cores expire 10 minutes post execution]',
    rawSource: '[PURGED]',
    manifestJson: {
      retentionPolicy: 'TTL_10_MINUTES',
      purgedAt: '2026-10-15T10:40:00Z',
      reason: 'Sandbox binary core auto-scrub to preserve workspace quota.',
    },
    provenanceTrail: {
      originatingAgent: 'SandboxGarbageCollector',
      stepNumber: 0,
      modelUsed: 'system-ttl-daemon',
      executionDuration: '0.1s',
      gitCommit: 'system',
      verifiedSignature: 'sig_purged',
    },
  },
];
