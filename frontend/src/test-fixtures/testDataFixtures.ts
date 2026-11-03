/**
 * Test Fixtures for Mini-Devin Frontend Unit & Component Tests (Task 13).
 *
 * CRITICAL DATA-INTEGRITY NOTICE:
 * All fixtures defined below represent isolated synthetic test inputs.
 * They are explicitly identified as test data (TEST_FIXTURE_*) and strictly
 * used to validate UI contracts, schema adherence, and state transitions.
 * None of these values represent live runtime data.
 */

import type { AgentRun, SystemMetrics, ArtifactTrail } from '../services/types';
import type { AgentEventEnvelope } from '../hooks/types';
import type { ImplementationPlanData } from '../components/PlanApproval/types';

export const TEST_FIXTURE_RUN_DETAILS: AgentRun = {
  id: 'run-8924a',
  repository: 'octocat/linguist',
  issueId: 482,
  status: 'running',
  branch: 'fix/parser-multibyte',
  createdAt: '2026-10-24T10:00:00Z',
  updatedAt: '2026-10-24T10:05:00Z',
};

export const TEST_FIXTURE_PLAN: ImplementationPlanData = {
  version: 'v1',
  isDraft: true,
  sandboxed: true,
  rationale: 'Enforce multibyte boundary handling in tokenizer parser without regression.',
  issue: {
    priority: 'HIGH',
    repository: 'octocat/linguist',
    issueNumber: 482,
    reporter: 'octocat',
    title: 'Fix UTF-8 multibyte parser boundary error in tokenizer.c',
    description: 'Multibyte UTF-8 sequences trigger boundary out-of-bounds scan.',
    labels: ['bug', 'parser'],
  },
  steps: [
    {
      stepNumber: 1,
      title: 'Inspect stride buffer offset in tokenizer.c',
      targetFile: 'ext/linguist/tokenizer.c',
      lineRange: 'Lines 42-45',
      action: 'Fix multibyte return stride',
      directive: 'Ensure 0xE2 3-byte prefix returns length 3.',
      technicalImpact: 'Prevents out-of-bounds pointer read when scanning multibyte tokens.',
    },
    {
      stepNumber: 2,
      title: 'Run regression test bundle in sandbox',
      targetFile: 'test/test_tokenizer.rb',
      lineRange: 'Lines 1-50',
      action: 'Add test suite',
      directive: 'Assert Japanese multibyte tokens parse correctly.',
      technicalImpact: 'Locks in regression coverage for issue #482.',
    },
  ],
  affectedFiles: [
    {
      path: 'ext/linguist/tokenizer.c',
      status: 'MODIFIED',
      delta: { added: 1, deleted: 1 },
      targetScope: 'Multibyte tokenizer bounds',
    },
    {
      path: 'test/test_tokenizer.rb',
      status: 'MODIFIED',
      delta: { added: 12, deleted: 0 },
      targetScope: 'Multibyte regression tests',
    },
  ],
  risks: [
    {
      category: 'Regression',
      severity: 'LOW RISK',
      description: 'Zero regression on legacy ASCII tokens',
    },
  ],
  verificationGates: [
    {
      command: 'bundle exec rake test',
      description: 'Run full linguist test suite',
      status: 'PLANNED',
    },
  ],
  metadata: {
    plannerModel: 'claude-3-5-sonnet',
    agent: 'Planner',
    version: 'v1',
    tokenConsumption: '1.2k tokens',
    estimatedExecutionTime: '45s',
    targetBranch: 'fix/utf8-tokenizer-boundaries',
  },
};

export const TEST_FIXTURE_DIFF_TEXT = `--- a/ext/linguist/tokenizer.c
+++ b/ext/linguist/tokenizer.c
@@ -42,7 +42,7 @@ static int scan_multibyte(const char *ptr, size_t len) {
-    if ((unsigned char)*ptr == 0xE2) return 2;
+    if ((unsigned char)*ptr == 0xE2) return 3;
     return 1;
 }`;

export const TEST_FIXTURE_EVENT_ENVELOPE: AgentEventEnvelope = {
  id: 'evt-test-101',
  runId: 'run-8924a',
  agent: 'Coder',
  step: '5.1',
  eventType: 'tool_call',
  tool: 'patch_file',
  model: 'claude-3-5-sonnet',
  timestamp: '2026-10-24T10:42:02.112Z',
  payload: {
    targetFile: 'ext/linguist/tokenizer.c',
    diffStat: '+42, -18',
    requirementId: 'R1',
  },
};

export const TEST_FIXTURE_METRICS: SystemMetrics = {
  fixAccuracy: 0.92,
  testPassRate: 0.88,
  averageSelfCorrectionIterations: 2.1,
  sweBenchLiteAccuracy: 0.74,
  tokensPerAgent: {
    planner: 2450,
    coder: 8120,
    test_runner: 1200,
  },
  modelUsage: {
    'claude-3-5-sonnet': 8120,
    'gpt-4o': 3650,
  },
};

export const TEST_FIXTURE_ARTIFACTS: ArtifactTrail = {
  runId: 'run-8924a',
  plan: '# Synthetic Plan Fixture\\n\\n1. Step A\\n2. Step B',
  diff: TEST_FIXTURE_DIFF_TEXT,
  testLog: 'Run options: --seed 1234\\nFinished in 0.05s\\n1 runs, 2 assertions, 0 failures',
  createdAt: '2026-10-24T10:45:00Z',
};
