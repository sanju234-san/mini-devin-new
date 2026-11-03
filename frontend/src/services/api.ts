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
// CONTRACT GAPS — PROVISIONAL REST FUNCTIONS
//
// docs/api-contract.md is currently 0 bytes.
// The endpoints below are isolated and modular. When Tamanna (API) or
// Sanjeevni (Metrics) finalizes the contract paths and payloads, only this
// file and types.ts will require updates.
// ============================================================================

/**
 * CONTRACT GAP: GET /api/v1/runs
 * Coordination required: Tamanna (Backend API)
 */
export async function getRuns(): Promise<RunsListResponse> {
  return request<RunsListResponse>('/api/v1/runs');
}

/**
 * CONTRACT GAP: GET /api/v1/runs/:id
 * Coordination required: Tamanna (Backend API)
 */
export async function getRunById(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

/**
 * CONTRACT GAP: GET /api/v1/runs/:id/artifacts
 * Coordination required: Tamanna (Backend API)
 */
export async function getArtifacts(runId: string): Promise<ArtifactTrail> {
  return request<ArtifactTrail>(`/api/v1/runs/${encodeURIComponent(runId)}/artifacts`);
}

/**
 * CONTRACT GAP: POST /api/v1/runs/:id/plan/approve
 * Coordination required: Tamanna (Backend API)
 */
export async function approvePlan(
  runId: string,
  payload: PlanApprovalPayload
): Promise<PlanApprovalResponse> {
  return request<PlanApprovalResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/plan/approve`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * CONTRACT GAP: POST /api/v1/runs/:id/plan/reject
 * Coordination required: Tamanna (Backend API)
 */
export async function rejectPlan(
  runId: string,
  reason?: string
): Promise<PlanApprovalResponse> {
  return request<PlanApprovalResponse>(
    `/api/v1/runs/${encodeURIComponent(runId)}/plan/reject`,
    {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'Plan rejected by user' }),
    }
  );
}

/**
 * CONTRACT GAP: GET /api/v1/metrics
 * Coordination required: Sanjeevni (Metrics / Evaluation)
 */
export async function getMetrics(): Promise<SystemMetrics> {
  return request<SystemMetrics>('/api/v1/metrics');
}

/**
 * CONTRACT GAP: GET /api/v1/runs/:id/plan
 * Coordination required: Tamanna (Backend API) & Sanjeevni (Planner Agent)
 */
export async function getPlan(runId: string): Promise<ImplementationPlanData> {
  return request<ImplementationPlanData>(`/api/v1/runs/${encodeURIComponent(runId)}/plan`);
}

