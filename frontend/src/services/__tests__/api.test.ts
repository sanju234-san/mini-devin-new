import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getRunById,
  getPlan,
  approvePlan,
  rejectPlan,
  getArtifacts,
  getMetrics,
} from '../api';
import {
  TEST_FIXTURE_RUN_DETAILS,
  TEST_FIXTURE_PLAN,
  TEST_FIXTURE_METRICS,
  TEST_FIXTURE_ARTIFACTS,
} from '../../test-fixtures/testDataFixtures';

describe('REST API Client (Task 2)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('fetches run details by id on GET /api/v1/runs/:runId', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => TEST_FIXTURE_RUN_DETAILS,
    });

    const run = await getRunById('run-8924a');
    expect(run.id).toBe('run-8924a');
    expect(run.status).toBe('running');
    expect(run.repository).toBe('octocat/linguist');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/runs/run-8924a'),
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: 'application/json' }),
      })
    );
  });

  it('fetches implementation plan on GET /api/v1/runs/:runId/plan', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => TEST_FIXTURE_PLAN,
    });

    const plan = await getPlan('run-8924a');
    expect(plan.version).toBe('v1');
    expect(plan.steps).toHaveLength(2);
    expect(plan.affectedFiles?.[0]?.path).toBe('ext/linguist/tokenizer.c');
  });

  it('dispatches approval decision on POST /api/v1/runs/:runId/plan/approve', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'approved', message: 'Plan approved. Continuing.' }),
    });

    const res = await approvePlan('run-8924a', { approved: true });
    expect(res.status).toBe('approved');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/runs/run-8924a/plan/approve'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      })
    );
  });

  it('dispatches rejection decision with feedback on POST /api/v1/runs/:runId/plan/reject', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'rejected', message: 'Plan rejected.' }),
    });

    const res = await rejectPlan('run-8924a', 'Need more test coverage');
    expect(res.status).toBe('rejected');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/runs/run-8924a/plan/reject'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Need more test coverage' }),
      })
    );
  });

  it('fetches artifacts trail on GET /api/v1/runs/:runId/artifacts', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => TEST_FIXTURE_ARTIFACTS,
    });

    const artifacts = await getArtifacts('run-8924a');
    expect(artifacts.runId).toBe('run-8924a');
    expect(artifacts.diff).toContain('tokenizer.c');
  });

  it('fetches evaluation metrics on GET /api/v1/metrics', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => TEST_FIXTURE_METRICS,
    });

    const metrics = await getMetrics();
    expect(metrics.fixAccuracy).toBe(0.92);
    expect(metrics.testPassRate).toBe(0.88);
  });

  it('throws structured ApiError when backend returns HTTP 404 or 500', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ message: 'Run not found' }),
    });

    await expect(getRunById('non-existent-run')).rejects.toMatchObject({
      kind: 'HTTP_ERROR',
      status: 404,
    });
  });

  it('throws NetworkError when fetch fails due to connection drop', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(getMetrics()).rejects.toMatchObject({
      kind: 'NETWORK_ERROR',
    });
  });
});
