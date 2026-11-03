/**
 * REST API Client Types for Mini-Devin
 *
 * Types in this file adhere strictly to the contracts defined in docs/api-contract.md.
 * Where the contract is incomplete or pending, types are quarantined under CONTRACT GAPS
 * with clear TODO markers.
 */

// ============================================================================
// REQUEST & ERROR STATES
// ============================================================================

export type ApiErrorKind = 'NETWORK_ERROR' | 'HTTP_ERROR' | 'INVALID_RESPONSE';

export interface ApiError {
  kind: ApiErrorKind;
  message: string;
  status?: number;
  statusText?: string;
  details?: unknown;
  endpoint?: string;
  timestamp: string;
}

export type RequestStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

export interface RequestState<T> {
  status: RequestStatus;
  data?: T;
  error?: ApiError;
}

// ============================================================================
// CONTRACT IMPLEMENTED: HEALTH
// Defined in backend/app/main.py: @app.get("/health")
// ============================================================================

export interface HealthResponse {
  status: string;
}

// ============================================================================
// OPENAPI 3.1.0 BACKEND SCHEMAS (FastAPI Contract)
// ============================================================================

export type RunStatus =
  | 'queued'
  | 'running'
  | 'awaiting_plan_approval'
  | 'completed'
  | 'failed'
  | 'rejected'
  | 'escalated';

export interface IssueIn {
  repo: string;
  issue_number: number;
  title: string;
  body?: string;
}

export interface IssueRef {
  repo: string;
  issue_number: number;
  title: string;
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  current_step?: string | null;
  issue: IssueRef;
  created_at: string;
  updated_at: string;
  error?: string | null;
}

export interface RunDetail extends RunSummary {
  issue_body?: string;
}

export interface RunList {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export type PlanDecisionType = 'approve' | 'edit' | 'reject';

export interface PlanDecisionIn {
  decision: PlanDecisionType;
  edited_plan?: Record<string, unknown> | null;
  reason?: string | null;
}

export type BackendArtifactType =
  | 'implementation_plan'
  | 'code_diff'
  | 'test_log'
  | 'screenshot'
  | 'recording'
  | 'walkthrough';

export interface ArtifactOut {
  id: string;
  run_id: string;
  type: BackendArtifactType;
  name: string;
  content_type: string;
  size_bytes: number;
  created_at?: string;
  agent?: string | null;
  model_used?: string | null;
}

export interface ArtifactContent {
  artifact: ArtifactOut;
  content: string;
}

export interface SWEBenchLiteMetrics {
  resolved: number;
  total: number;
  resolve_rate: number;
}

export interface MetricsOut {
  available: boolean;
  fix_accuracy?: number | null;
  test_pass_rate?: number | null;
  avg_self_correction_iterations?: number | null;
  swe_bench_lite?: SWEBenchLiteMetrics | null;
  updated_at?: string | null;
}

// ============================================================================
// CONTRACT GAPS — PENDING TAMANNA (BACKEND API OWNER) & SANJEEVNI (METRICS OWNER)
//
// docs/api-contract.md is currently 0 bytes.
//
// The following interfaces represent placeholder models for future endpoints.
// Do NOT invent fields or assume payloads until Tamanna and Sanjeevni update
// docs/api-contract.md.
// ============================================================================

/**
 * CONTRACT GAP: Run schema is not yet defined in docs/api-contract.md.
 * Coordination required with: Tamanna (Backend API)
 */
export interface AgentRun {
  id: string;
  status?: string;
  createdAt?: string;
  repository?: string;
  issueId?: string | number;
  [key: string]: unknown;
}

/**
 * CONTRACT GAP: Runs list response structure is not yet defined in docs/api-contract.md.
 * Coordination required with: Tamanna (Backend API)
 */
export interface RunsListResponse {
  runs: AgentRun[];
  total: number;
}

/**
 * CONTRACT GAP: Artifact trail schema is not yet defined in docs/api-contract.md.
 * Coordination required with: Tamanna (Backend API)
 */
export interface ArtifactTrail {
  runId: string;
  plan?: string;
  diff?: string;
  testLog?: string;
  prUrl?: string;
  [key: string]: unknown;
}

/**
 * CONTRACT GAP: Plan approval request & response schema is not yet defined in docs/api-contract.md.
 * Coordination required with: Tamanna (Backend API)
 */
export interface PlanApprovalPayload {
  approved: boolean;
  feedback?: string;
  modifiedPlan?: string;
}

export interface PlanApprovalResponse {
  status: string;
  message?: string;
}

/**
 * CONTRACT GAP: Metrics format is not yet defined in docs/api-contract.md.
 * Coordination required with: Sanjeevni (Metrics / Evaluation)
 */
export interface SystemMetrics {
  [key: string]: unknown;
}

/**
 * CONTRACT GAP: Implementation Plan structure is not yet defined in docs/api-contract.md.
 * Coordination required with: Sanjeevni (Planner Agent) & Tamanna (Backend API)
 */
export interface PlanStep {
  stepNumber: number;
  title: string;
  targetFile?: string;
  lineRange?: string;
  action?: string;
  directive?: string;
  technicalImpact?: string;
}

export interface AffectedFile {
  path: string;
  status: 'MODIFIED' | 'ADDED' | 'DELETED';
  delta?: {
    added: number;
    deleted: number;
  };
  targetScope?: string;
}

export interface PlanRisk {
  category: string;
  severity: 'LOW RISK' | 'MEDIUM ATTENTION' | 'HIGH RISK' | 'MITIGATED';
  description: string;
}

export interface VerificationGate {
  command: string;
  description: string;
  status: 'PLANNED';
}

export interface PlanMetadata {
  plannerModel?: string;
  agent?: string;
  version?: string;
  tokenConsumption?: string;
  estimatedExecutionTime?: string;
  targetBranch?: string;
}

export interface IssueContext {
  priority?: string;
  repository?: string;
  issueNumber?: number | string;
  reporter?: string;
  title?: string;
  description?: string;
  labels?: string[];
  category?: string;
}

export interface ImplementationPlanData {
  version?: string;
  isDraft?: boolean;
  sandboxed?: boolean;
  rationale?: string;
  steps: PlanStep[];
  affectedFiles?: AffectedFile[];
  risks?: PlanRisk[];
  verificationGates?: VerificationGate[];
  metadata?: PlanMetadata;
  issue?: IssueContext;
}

