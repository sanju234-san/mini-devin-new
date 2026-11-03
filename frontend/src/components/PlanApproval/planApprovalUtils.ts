/**
 * Plan Approval Utilities and Synthetic Dev Preview Data
 *
 * Implements pure frontend helpers for Plan Approval UI.
 * Quarantined synthetic preview data uses generic placeholders only
 * and never mixes into runtime API state.
 */

import type {
  ImplementationPlanData,
  ReviewCriteriaItem,
} from './types';

export const DEFAULT_REVIEW_CRITERIA: ReviewCriteriaItem[] = [
  { id: 'crit-1', label: 'Directly resolves issue scope without regressions', checked: false },
  { id: 'crit-2', label: 'Proposed code changes remain minimal and targeted', checked: false },
  { id: 'crit-3', label: 'Implementation steps are sequentially staged and verifiable', checked: false },
  { id: 'crit-4', label: 'Safety, type boundaries, and potential side-effects evaluated', checked: false },
  { id: 'crit-5', label: 'Validation gates provide adequate test coverage depth', checked: false },
];

/**
 * Quarantined synthetic preview plan for Dev Simulator only.
 * Gated and clearly labeled. Contains NO Stitch example identifiers.
 */
export const SYNTHETIC_PREVIEW_PLAN: ImplementationPlanData = {
  version: 'v0.1-preview',
  isDraft: true,
  sandboxed: true,
  rationale:
    'Targeted refactor isolating boundary validation logic in dedicated helper before delegating to runtime parser. Preserves ABI compatibility while preventing unhandled exceptions.',
  steps: [
    {
      stepNumber: 1,
      title: 'Inspect boundary handling & validate input length bounds',
      targetFile: 'src/parser/boundary_guard.ts',
      lineRange: 'Lines 120-145',
      action: 'Boundary Guard',
      directive: 'Validate byte-offset mapping against total array length. Ensure boundary guard safely rejects truncated sequences.',
      technicalImpact: 'Guarantees offset indexing never exceeds buffer bounds, preventing memory faults.',
    },
    {
      stepNumber: 2,
      title: 'Update slice calculation & character counter logic',
      targetFile: 'src/parser/slice_calculator.ts',
      lineRange: 'Lines 180-210',
      action: 'Algorithm Refactor',
      directive: 'Replace manual loop with boundary-safe slicing helper and add replacement character handling.',
      technicalImpact: 'Full compliance with specification while maintaining processing throughput.',
    },
    {
      stepNumber: 3,
      title: 'Add regression test coverage for multibyte edge cases',
      targetFile: 'tests/boundary_test.ts',
      lineRange: 'Lines 45-80',
      action: 'Test Expansion',
      directive: 'Introduce test cases containing mixed multi-byte code blocks, asserting extracted tokens match expectations.',
      technicalImpact: 'Locks in reproducibility and prevents regression during future optimizations.',
    },
    {
      stepNumber: 4,
      title: 'Run automated verification & verify leak-free execution',
      targetFile: 'Sandbox: container-runtime-env',
      action: 'Verification Probe',
      directive: 'Execute test suite under sandbox memory probe and verify clean termination.',
      technicalImpact: 'Guarantees clean test execution prior to pull request generation.',
    },
  ],
  affectedFiles: [
    {
      path: 'src/parser/boundary_guard.ts',
      status: 'MODIFIED',
      delta: { added: 24, deleted: 5 },
      targetScope: 'Core Parser Boundary Logic',
    },
    {
      path: 'src/parser/slice_calculator.ts',
      status: 'MODIFIED',
      delta: { added: 38, deleted: 2 },
      targetScope: 'Slice Algorithm Implementation',
    },
    {
      path: 'tests/fixtures/multibyte_sample.txt',
      status: 'ADDED',
      delta: { added: 30, deleted: 0 },
      targetScope: 'Test Corpus Fixture',
    },
  ],
  risks: [
    {
      category: 'Performance Impact',
      severity: 'LOW RISK',
      description: 'Benchmark probes confirm negligible CPU overhead on large inputs compared to previous unaligned parser.',
    },
    {
      category: 'Foreign Interface Bindings',
      severity: 'MEDIUM ATTENTION',
      description: 'Ensure boundary pointers continuously receive aligned pointers to prevent invalid memory dereferences.',
    },
    {
      category: 'Regression Surface',
      severity: 'MITIGATED',
      description: 'Comprehensive edge-case test suite covers multi-byte sequences before changes are committed.',
    },
  ],
  verificationGates: [
    {
      command: 'npm run test:units',
      description: 'Standard unit regression suite with full assertions',
      status: 'PLANNED',
    },
    {
      command: 'npm run test:boundaries',
      description: 'Dedicated multibyte boundary matrix test suite',
      status: 'PLANNED',
    },
    {
      command: 'npm run lint',
      description: 'AST syntax conformance and static type analysis',
      status: 'PLANNED',
    },
    {
      command: 'npm run build',
      description: 'Hermetic production bundle compilation check',
      status: 'PLANNED',
    },
  ],
  metadata: {
    plannerModel: 'Autonomous Planner Model (n/a)',
    agent: 'planner_graph (n/a)',
    version: 'v0.1-preview',
    tokenConsumption: 'n/a',
    estimatedExecutionTime: 'n/a',
    targetBranch: 'main (provisional)',
  },
  issue: {
    priority: 'P1 HIGH',
    repository: 'sample-org/sample-repo',
    issueNumber: 101,
    reporter: 'repo-maintainer',
    title: 'Resolve multi-byte boundary truncation in stream parser',
    description:
      'Issue report detailing byte-offset truncation when parsing multibyte sequences. When slicing hits unaligned character byte boundaries, unmapped bytes cause intermittent parser exceptions during processing.',
    labels: ['bug', 'parser', 'priority-p1'],
    category: 'Stream Parser Bug',
  },
};

/**
 * Normalizes incoming Plan payload from backend/LangGraph.
 * Seamlessly adapts Sanjeevni's authoritative Plan schema (docs/design/schemas.md §1)
 * while preserving frontend-native ImplementationPlanData structures.
 */
export function normalizePlanData(raw: any): ImplementationPlanData {
  if (!raw || typeof raw !== 'object') {
    return raw;
  }

  const version = raw.version || raw.version_id || 'v1';
  const isDraft = raw.isDraft ?? (raw.status === 'draft' || raw.status === undefined);
  const sandboxed = raw.sandboxed ?? true;
  const rationale = raw.rationale || raw.scope || 'Plan synthesized by Planner Agent.';

  // Normalize Issue Context
  const issue = raw.issue || {
    title: raw.intent || 'Synthesized Implementation Plan',
    description: raw.scope || raw.rationale || '',
    priority: 'NORMAL',
    labels: Array.isArray(raw.requirements)
      ? raw.requirements.map((r: any) => r.id || 'REQ')
      : ['plan'],
  };

  // Normalize Affected Files
  let affectedFiles = raw.affectedFiles;
  if (!affectedFiles && Array.isArray(raw.affected_files)) {
    affectedFiles = raw.affected_files.map((item: any) => {
      if (typeof item === 'string') {
        return {
          path: item,
          status: 'MODIFIED' as const,
          targetScope: 'Affected by plan',
        };
      }
      return item;
    });
  }

  // Normalize Steps
  let steps = raw.steps;
  if (Array.isArray(steps)) {
    steps = steps.map((s: any, idx: number) => ({
      stepNumber: s.stepNumber ?? idx + 1,
      title: s.title || s.description || `Step ${idx + 1}`,
      targetFile: s.targetFile || (Array.isArray(s.files) ? s.files[0] : undefined),
      directive: s.directive || s.description,
      action: s.action || 'Execute step',
      technicalImpact: s.technicalImpact,
      lineRange: s.lineRange,
    }));
  } else {
    steps = [];
  }

  // Normalize Verification Gates
  let verificationGates = raw.verificationGates;
  if (!verificationGates && Array.isArray(raw.expected_tests)) {
    verificationGates = raw.expected_tests.map((cmd: any) => ({
      command: typeof cmd === 'string' ? cmd : String(cmd),
      description: 'Planned test suite verification',
      status: 'PLANNED' as const,
    }));
  }

  return {
    version,
    isDraft,
    sandboxed,
    rationale,
    steps,
    affectedFiles,
    risks: raw.risks || [],
    verificationGates,
    metadata: raw.metadata || {
      plannerModel: 'Autonomous Planner',
      agent: raw.author || 'Planner',
      version,
    },
    issue,
  };
}
