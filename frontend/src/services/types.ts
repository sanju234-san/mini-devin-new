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

