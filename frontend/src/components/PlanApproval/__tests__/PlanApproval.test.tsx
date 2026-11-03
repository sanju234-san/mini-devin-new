import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { PlanApproval } from '../PlanApproval';
import * as api from '../../../services/api';
import {
  TEST_FIXTURE_PLAN,
  TEST_FIXTURE_RUN_DETAILS,
} from '../../../test-fixtures/testDataFixtures';

// Mock API module
vi.mock('../../../services/api', () => ({
  getPlan: vi.fn(),
  getRunById: vi.fn(),
  approvePlan: vi.fn(),
  rejectPlan: vi.fn(),
}));

describe('Plan Approval Component (Task 5)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially then displays plan details upon fetch', async () => {
    vi.mocked(api.getPlan).mockResolvedValue(TEST_FIXTURE_PLAN);
    vi.mocked(api.getRunById).mockResolvedValue(TEST_FIXTURE_RUN_DETAILS);

    render(<PlanApproval runId="run-8924a" />);

    // Wait for plan to load
    await waitFor(() => {
      expect(screen.getByText(/Fix UTF-8 multibyte parser boundary error in tokenizer.c/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Inspect stride buffer offset in tokenizer.c/i)).toBeInTheDocument();
    expect(screen.getAllByText(/ext\/linguist\/tokenizer.c/i).length).toBeGreaterThan(0);
  });

  it('dispatches approvePlan API call when Approve Plan button is clicked', async () => {
    vi.mocked(api.getPlan).mockResolvedValue(TEST_FIXTURE_PLAN);
    vi.mocked(api.getRunById).mockResolvedValue(TEST_FIXTURE_RUN_DETAILS);
    vi.mocked(api.approvePlan).mockResolvedValue({ status: 'approved', message: 'Proceeding' });

    render(<PlanApproval runId="run-8924a" />);

    await waitFor(() => {
      expect(screen.getByText(/Fix UTF-8 multibyte parser boundary error/i)).toBeInTheDocument();
    });

    const approveButton = screen.getByRole('button', { name: /Approve Plan/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(api.approvePlan).toHaveBeenCalledWith(
        'run-8924a',
        expect.objectContaining({ approved: true })
      );
    });
  });

  it('dispatches rejectPlan API call with reason when Reject action is confirmed', async () => {
    vi.mocked(api.getPlan).mockResolvedValue(TEST_FIXTURE_PLAN);
    vi.mocked(api.getRunById).mockResolvedValue(TEST_FIXTURE_RUN_DETAILS);
    vi.mocked(api.rejectPlan).mockResolvedValue({ status: 'rejected', message: 'Rejected' });

    render(<PlanApproval runId="run-8924a" />);

    await waitFor(() => {
      expect(screen.getByText(/Fix UTF-8 multibyte parser boundary error/i)).toBeInTheDocument();
    });

    const rejectButton = screen.getByRole('button', { name: /Reject Plan/i });
    fireEvent.click(rejectButton);

    // Find feedback input or confirmation
    const input = screen.getByPlaceholderText(/Reason for rejection \(optional\)\.\.\./i);
    fireEvent.change(input, { target: { value: 'Revise boundary buffer size' } });

    const confirmReject = screen.getByRole('button', { name: /Confirm Abort/i });
    fireEvent.click(confirmReject);

    await waitFor(() => {
      expect(api.rejectPlan).toHaveBeenCalledWith('run-8924a', 'Revise boundary buffer size');
    });
  });

  it('displays honest error message when fetching plan fails', async () => {
    vi.mocked(api.getPlan).mockRejectedValue({
      kind: 'HTTP_ERROR',
      message: 'Plan not found on backend.',
      status: 404,
    });
    vi.mocked(api.getRunById).mockResolvedValue(TEST_FIXTURE_RUN_DETAILS);

    render(<PlanApproval runId="run-8924a" />);

    await waitFor(() => {
      expect(screen.getByText(/Plan not found on backend/i)).toBeInTheDocument();
    });
  });
});
