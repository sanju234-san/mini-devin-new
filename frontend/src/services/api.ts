/**
 * Mini-Devin REST API Client
 *
 * Single place for all REST calls in the frontend.
 * Strictly uses native fetch and reads the base URL from src/config/env.ts.
 *
 * Where endpoints are missing in docs/api-contract.md, they are quarantined
 * and annotated as contract gaps requiring Tamanna/Sanjeevni coordination.
 */

import { API_BASE_URL } from '../config/env';
import type {
  ApiError,
  HealthResponse,
  AgentRun,
  RunsListResponse,
  ArtifactTrail,
  PlanApprovalPayload,
  PlanApprovalResponse,
  SystemMetrics,
  ImplementationPlanData,
  IssueIn,
  RunSummary,
  RunDetail,
  RunList,
  PlanDecisionIn,
  ArtifactOut,
  ArtifactContent,
  MetricsOut,
} from './types';

// Normalized Base URL without trailing slash
const BASE_URL = API_BASE_URL.replace(/\/+$/, '');

/**
 * Normalizes any error into a structured ApiError.
 */
function normalizeError(error: unknown, endpoint: string, status?: number, statusText?: string): ApiError {
  const timestamp = new Date().toISOString();

  if (error instanceof DOMException && error.name === 'AbortError') {
    return {
      kind: 'NETWORK_ERROR',
      message: `Request timed out or aborted for ${endpoint}`,
      endpoint,
      timestamp,
    };
  }

  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      kind: 'NETWORK_ERROR',
      message: `Backend unreachable at ${BASE_URL}. Ensure the server is running.`,
      endpoint,
      timestamp,
      details: error.message,
    };
  }

  if (status !== undefined) {
    return {
      kind: 'HTTP_ERROR',
      message: (error as { message?: string })?.message || `HTTP ${status} ${statusText || 'Error'}`,
      status,
      statusText,
      endpoint,
      timestamp,
      details: error,
    };
  }

  return {
    kind: 'INVALID_RESPONSE',
    message: error instanceof Error ? error.message : 'Unknown API response error',
    endpoint,
    timestamp,
    details: error,
  };
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

/**
 * Shared native fetch wrapper with timeout, JSON parsing, and normalized error throwing.
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 10000, headers, ...restOptions } = options;
  const endpoint = `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpoint, {
      ...restOptions,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...headers,
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }
      throw normalizeError(errorBody, endpoint, response.status, response.statusText);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    try {
      const data = await response.json();
      return data as T;
    } catch (parseError) {
      throw normalizeError(parseError, endpoint, response.status, 'JSON Parse Error');
    }
  } catch (error) {
    clearTimeout(timeoutId);
    if ((error as ApiError).kind) {
      throw error;
    }
    throw normalizeError(error, endpoint);
  }
}

// ============================================================================
// CONTRACT IMPLEMENTED ENDPOINTS
// ============================================================================

/**
 * Health Check: Verifies backend connectivity.
 * Implemented in backend/app/main.py: GET /health
 */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

// ============================================================================
// OPENAPI 3.1.0 CONNECTED ENDPOINTS (FastAPI Backend)
// ============================================================================

/**
 * Normalizes a backend RunSummary / RunDetail into the frontend AgentRun shape
 * while preserving all original OpenAPI fields.
 */
function normalizeRun(raw: RunSummary | RunDetail | AgentRun): AgentRun {
  const anyRun = raw as Record<string, unknown>;
  const issue = anyRun.issue as { repo?: string; issue_number?: number; title?: string } | undefined;
  return {
    ...anyRun,
    id: String(anyRun.id || ''),
    status: typeof anyRun.status === 'string' ? anyRun.status : undefined,
    createdAt: (anyRun.createdAt as string) || (anyRun.created_at as string),
    updatedAt: (anyRun.updatedAt as string) || (anyRun.updated_at as string),
    repository: (anyRun.repository as string) || issue?.repo,
    issueId: (anyRun.issueId as string | number) ?? issue?.issue_number,
    title: (anyRun.title as string) || issue?.title,
  };
}

/**
 * GET /runs?limit=...&offset=...
 * Retrieves a paginated list of agent runs ordered newest first.
 */
export async function getRuns(limit = 20, offset = 0): Promise<RunsListResponse> {
  const raw = await request<RunList | RunsListResponse>(`/runs?limit=${limit}&offset=${offset}`);
  const items = Array.isArray((raw as RunList).items)
    ? (raw as RunList).items
    : Array.isArray((raw as RunsListResponse).runs)
    ? (raw as RunsListResponse).runs
    : [];
  return {
    runs: items.map((r) => normalizeRun(r)),
    total: typeof raw.total === 'number' ? raw.total : items.length,
  };
}

/**
 * GET /runs/{run_id}
 * Fetches complete details for a run, including the original issue body.
 */
export async function getRunById(runId: string): Promise<AgentRun> {
  const raw = await request<RunDetail | AgentRun>(`/runs/${encodeURIComponent(runId)}`);
  return normalizeRun(raw);
}

/**
 * POST /issues/ingest
 * Ingests a GitHub issue and queues an autonomous run (HTTP 202).
 */
export async function ingestIssue(payload: IssueIn): Promise<RunSummary> {
  return request<RunSummary>('/issues/ingest', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * GET /runs/{run_id}/artifacts/{artifact_id}
 * Retrieves the text content and metadata of a specific artifact.
 */
export async function getArtifactById(runId: string, artifactId: string): Promise<ArtifactContent> {
  return request<ArtifactContent>(
    `/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`
  );
}

/**
 * GET /runs/{run_id}/artifacts
 * Lists all artifacts for a run and resolves text contents into ArtifactTrail.
 */
export async function getArtifacts(runId: string): Promise<ArtifactTrail> {
  if (!runId) {
    return { runId: '', items: [] };
  }

  let raw: ArtifactOut[] | ArtifactTrail;
  try {
    raw = await request<ArtifactOut[] | ArtifactTrail>(
      `/runs/${encodeURIComponent(runId)}/artifacts`
    );
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status?: number }).status === 404) {
      return { runId, items: [] };
    }
    throw err;
  }

  // If already in legacy/fixture ArtifactTrail format, return directly
  if (!Array.isArray(raw)) {
    return raw as ArtifactTrail;
  }

  const trail: ArtifactTrail = {
    runId,
    items: raw,
  };

  await Promise.all(
    raw.map(async (art) => {
      if (art.type === 'screenshot' || art.type === 'recording') {
        return;
      }
      try {
        const detail = await getArtifactById(runId, art.id);
        if (art.type === 'implementation_plan' && !trail.plan) {
          trail.plan = detail.content;
        } else if (art.type === 'code_diff' && !trail.diff) {
          trail.diff = detail.content;
        } else if (art.type === 'test_log' && !trail.testLog) {
          trail.testLog = detail.content;
        } else if (art.type === 'walkthrough') {
          if (art.name === 'pull_request.md' || detail.content.includes('**URL**:')) {
            (trail as Record<string, unknown>).prMarkdown = detail.content;
            const match = detail.content.match(/\*\*URL\*\*:\s*(\S+)/);
            if (match?.[1]) {
              trail.prUrl = match[1];
            }
          } else if (art.name === 'code_review_report.md') {
            (trail as Record<string, unknown>).reviewMarkdown = detail.content;
          }
        }
      } catch {
        // Ignore individual artifact fetch failures
      }
    })
  );

  return trail;
}

/**
 * POST /runs/{run_id}/plan/decision
 * Submits a human plan decision (approve / edit / reject) to FastAPI (HTTP 202).
 */
export async function submitPlanDecision(
  runId: string,
  payload: PlanDecisionIn
): Promise<RunSummary> {
  return request<RunSummary>(
    `/runs/${encodeURIComponent(runId)}/plan/decision`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Approves the proposed plan via POST /runs/{run_id}/plan/decision.
 */
export async function approvePlan(
  runId: string,
  payload: PlanApprovalPayload
): Promise<PlanApprovalResponse> {
  try {
    const raw = await request<RunSummary | PlanApprovalResponse>(
      `/runs/${encodeURIComponent(runId)}/plan/decision`,
      {
        method: 'POST',
        body: JSON.stringify({
          decision: 'approve',
          reason: payload.feedback || 'Plan looks good',
        }),
      }
    );
    return {
      status: raw.status || 'approved',
      message: (raw as PlanApprovalResponse).message || 'Plan approved. Continuing.',
    };
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status?: number }).status === 409) {
      return {
        status: 'approved',
        message: 'Plan already approved. Coder Agent execution in progress.',
      };
    }
    throw err;
  }
}

/**
 * Rejects the proposed plan via POST /runs/{run_id}/plan/decision.
 */
export async function rejectPlan(
  runId: string,
  reason?: string
): Promise<PlanApprovalResponse> {
  const raw = await request<RunSummary | PlanApprovalResponse>(
    `/runs/${encodeURIComponent(runId)}/plan/decision`,
    {
      method: 'POST',
      body: JSON.stringify({
        decision: 'reject',
        reason: reason || 'Plan rejected by user',
      }),
    }
  );
  return {
    status: raw.status || 'rejected',
    message: (raw as PlanApprovalResponse).message || 'Plan rejected.',
  };
}

/**
 * GET /metrics
 * Retrieves system evaluation and benchmark metrics.
 */
export async function getMetrics(): Promise<SystemMetrics> {
  const raw = await request<MetricsOut & SystemMetrics>('/metrics');
  return {
    ...raw,
    fixAccuracy: raw.fixAccuracy ?? raw.fix_accuracy ?? undefined,
    testPassRate: raw.testPassRate ?? raw.test_pass_rate ?? undefined,
    averageSelfCorrectionIterations:
      raw.averageSelfCorrectionIterations ?? raw.avg_self_correction_iterations ?? undefined,
  };
}

/**
 * Retrieves the implementation plan for a run from its artifacts or plan endpoint.
 */
export async function getPlan(runId: string): Promise<ImplementationPlanData> {
  if (!runId) {
    return { steps: [] };
  }

  let raw: ArtifactOut[] | ImplementationPlanData;
  try {
    raw = await request<ArtifactOut[] | ImplementationPlanData>(
      `/runs/${encodeURIComponent(runId)}/artifacts`
    );
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status?: number }).status === 404) {
      return { steps: [] };
    }
    throw err;
  }

  // If response is already an ImplementationPlanData object (e.g. unit test mock), return it
  if (!Array.isArray(raw) && raw && typeof raw === 'object' && 'steps' in raw) {
    return raw as ImplementationPlanData;
  }

  if (Array.isArray(raw)) {
    const planArt = raw.find((a) => a.type === 'implementation_plan');
    if (planArt) {
      const detail = await getArtifactById(runId, planArt.id);
      try {
        return JSON.parse(detail.content) as ImplementationPlanData;
      } catch {
        const lines = detail.content
          .split('\n')
          .map((l) => l.trim())
          .filter((l) => /^\d+\.\s+/.test(l));
        return {
          version: 'v1',
          isDraft: false,
          sandboxed: true,
          rationale: detail.content,
          steps:
            lines.length > 0
              ? lines.map((l, idx) => ({
                  stepNumber: idx + 1,
                  title: l.replace(/^\d+\.\s+/, ''),
                  directive: l,
                }))
              : [
                  {
                    stepNumber: 1,
                    title: 'Implementation Plan',
                    directive: detail.content,
                  },
                ],
        };
      }
    }
  }

  return { steps: [] };
}
