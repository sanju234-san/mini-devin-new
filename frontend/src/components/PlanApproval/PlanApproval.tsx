'use client';

import React, { useState, useEffect, useCallback } from 'react';
import type {
  ImplementationPlanData,
  SimulatorState,
  ApprovalDecision,
} from './types';
import { SYNTHETIC_PREVIEW_PLAN, normalizePlanData } from './planApprovalUtils';
import { getPlan, approvePlan, rejectPlan, getRunById } from '../../services/api';
import type { ApiError } from '../../services/types';
import { useAgentRunSocket } from '../../hooks/useAgentRunSocket';
import { ApprovalBanner } from './ApprovalBanner';
import { IssueContextCard } from './IssueContextCard';
import { ImplementationPlan } from './ImplementationPlan';
import { AffectedFilesMatrix } from './AffectedFilesMatrix';
import { RisksSection } from './RisksSection';
import { VerificationGates } from './VerificationGates';
import { ApprovalPanel } from './ApprovalPanel';
import { PlanMetadata } from './PlanMetadata';
import { SandboxStatusCard } from './SandboxStatusCard';
import { DevStateSimulator } from './DevStateSimulator';

interface PlanApprovalProps {
  runId?: string;
}

export const PlanApproval: React.FC<PlanApprovalProps> = ({ runId = 'sample-run' }) => {
  // Dev Simulator State (gated to development)
  const [simulatorState, setSimulatorState] = useState<SimulatorState>('real');

  // Real API State
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [plan, setPlan] = useState<ImplementationPlanData | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);

  // Approval Action States
  const [decisionState, setDecisionState] = useState<ApprovalDecision>('idle');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedbackText, setFeedbackText] = useState<string>('');
  const [actionResponse, setActionResponse] = useState<{ status: string; message?: string } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Live WebSocket Integration (Task 3 Hook)
  const { events } = useAgentRunSocket(runId, {
    autoConnect: true,
  });

  // Fetch real plan and run details from API
  const fetchPlanData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Fetch Run Status
      try {
        const runData = await getRunById(runId);
        setRunStatus(runData.status || null);
      } catch {
        // Run endpoint may be pending in contract; keep non-fatal
      }

      // 2. Fetch Plan
      const planData = await getPlan(runId);
      setPlan(normalizePlanData(planData));
    } catch (err) {
      setError(err as ApiError);
      setPlan(null);
    } finally {
      setIsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (simulatorState === 'real') {
      fetchPlanData();
    }
  }, [fetchPlanData, simulatorState]);

  // Update status if a WebSocket event signals stage change
  useEffect(() => {
    if (events.length > 0) {
      const latest = events[events.length - 1];
      const type = (latest.eventType || '').toLowerCase();
      if (type.includes('approval') || type.includes('interrupt') || type.includes('hold')) {
        setRunStatus('awaiting_approval');
      }
    }
  }, [events]);

  // Handle Approve Action (Real)
  const handleApprove = async (feedback?: string) => {
    if (isSubmitting || decisionState === 'approved') return;

    if (simulatorState !== 'real') {
      // In dev simulator mode, purely simulate UI transition without calling API
      setIsSubmitting(true);
      setDecisionState('submitting');
      setTimeout(() => {
        setIsSubmitting(false);
        setDecisionState('approved');
        setActionResponse({
          status: 'approved',
          message: 'Plan approved. Backend Coder Agent authorized (Simulated).',
        });
      }, 700);
      return;
    }

    setIsSubmitting(true);
    setDecisionState('submitting');
    setActionError(null);
    try {
      const response = await approvePlan(runId, {
        approved: true,
        feedback,
      });
      setDecisionState('approved');
      setActionResponse(response);
    } catch (err) {
      const apiErr = err as ApiError;
      setActionError(apiErr.message || 'Approval transmission failed.');
      setDecisionState('idle');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Reject Action (Real)
  const handleReject = async (reason?: string) => {
    if (isSubmitting || decisionState === 'rejected') return;

    if (simulatorState !== 'real') {
      // In dev simulator mode, purely simulate UI transition without calling API
      setIsSubmitting(true);
      setDecisionState('submitting');
      setTimeout(() => {
        setIsSubmitting(false);
        setDecisionState('rejected');
        setActionResponse({
          status: 'rejected',
          message: 'Plan rejected. Autonomous execution aborted (Simulated).',
        });
      }, 700);
      return;
    }

    setIsSubmitting(true);
    setDecisionState('submitting');
    setActionError(null);
    try {
      const response = await rejectPlan(runId, reason);
      setDecisionState('rejected');
      setActionResponse(response);
    } catch (err) {
      const apiErr = err as ApiError;
      setActionError(apiErr.message || 'Rejection transmission failed.');
      setDecisionState('idle');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Determine active view data based on simulator state or real API
  let activePlan: ImplementationPlanData | null = plan;
  let activeLoading = isLoading;
  let activeError: ApiError | null = error;
  let activeDecisionState = decisionState;
  let activeIsSubmitting = isSubmitting;
  let isAwaitingApproval = runStatus === 'awaiting_approval';

  if (simulatorState === 'awaiting_approval') {
    activePlan = SYNTHETIC_PREVIEW_PLAN;
    activeLoading = false;
    activeError = null;
    isAwaitingApproval = true;
    activeDecisionState = 'idle';
  } else if (simulatorState === 'loading') {
    activePlan = null;
    activeLoading = true;
    activeError = null;
  } else if (simulatorState === 'submitting') {
    activePlan = SYNTHETIC_PREVIEW_PLAN;
    activeLoading = false;
    activeIsSubmitting = true;
    activeDecisionState = 'submitting';
    isAwaitingApproval = true;
  } else if (simulatorState === 'approved') {
    activePlan = SYNTHETIC_PREVIEW_PLAN;
    activeLoading = false;
    activeDecisionState = 'approved';
    isAwaitingApproval = false;
  } else if (simulatorState === 'changes_requested') {
    activePlan = SYNTHETIC_PREVIEW_PLAN;
    activeLoading = false;
    activeDecisionState = 'changes_requested';
    isAwaitingApproval = false;
  } else if (simulatorState === 'empty') {
    activePlan = null;
    activeLoading = false;
    activeError = null;
  } else if (simulatorState === 'error') {
    activePlan = null;
    activeLoading = false;
    activeError = {
      kind: 'HTTP_ERROR',
      message: 'Failed to fetch plan from backend: Run has been aborted or does not exist.',
      status: 404,
      statusText: 'Not Found',
      endpoint: `/api/v1/runs/${runId}/plan`,
      timestamp: new Date().toISOString(),
    };
  }

  // Pipeline Status Stages
  const stages = [
    { num: '01', name: 'Triage', status: 'completed' },
    { num: '02', name: 'Retrieval', status: 'completed' },
    { num: '03', name: 'Planner', status: 'completed' },
    {
      num: '04',
      name: 'HUMAN APPROVAL',
      gateBadge: 'GATE 01',
      status: isAwaitingApproval ? 'paused' : activeDecisionState === 'approved' ? 'completed' : 'standby',
    },
    { num: '05', name: 'Coder', status: activeDecisionState === 'approved' ? 'running' : 'standby' },
    { num: '06', name: 'Test Runner', status: 'standby' },
    { num: '07', name: 'Debugger', status: 'standby' },
    { num: '08', name: 'Reviewer', status: 'standby' },
    { num: '09', name: 'PR Agent', status: 'standby' },
  ];

  return (
    <div className="flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto pb-space-xl">
      {/* Dev Simulator Notification Banner */}
      {simulatorState !== 'real' && (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/30 px-space-md py-2 flex items-center justify-between text-xs font-mono text-amber-200">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>
              <strong>DEV PREVIEW MODE ({simulatorState})</strong> — Rendering synthetic placeholders. Zero real API mutations.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setSimulatorState('real')}
            className="px-2 py-0.5 rounded bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 text-[11px]"
          >
            Switch to Live API
          </button>
        </div>
      )}

      {/* 1. Top Pipeline Status Strip */}
      <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md flex flex-col gap-2 shadow-sm">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <span className="font-semibold text-on-surface uppercase tracking-wider text-[11px]">
              Autonomous Workflow Stage
            </span>
          </div>
          <span className="text-[10px] text-outline font-mono">
            {isAwaitingApproval ? 'PAUSED AT HUMAN APPROVAL GATE' : 'STANDBY'}
          </span>
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-1.5 pt-1 overflow-x-auto">
          {stages.map((st) => {
            let badgeClass = 'bg-surface-container text-outline border-outline-variant/20';
            let statusText = 'Standby';

            if (st.status === 'completed') {
              badgeClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
              statusText = 'Done';
            } else if (st.status === 'paused') {
              badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40 ring-1 ring-amber-400/40 animate-pulse';
              statusText = 'HOLD';
            } else if (st.status === 'running') {
              badgeClass = 'bg-primary/20 text-primary border-primary/40 ring-1 ring-primary/40 animate-pulse';
              statusText = 'Running';
            }

            return (
              <div
                key={st.num}
                className={`p-2 rounded-lg border flex flex-col justify-between gap-1 text-xs font-mono ${
                  st.status === 'paused'
                    ? 'bg-amber-500/10 border-amber-500/40'
                    : 'bg-surface-container border-outline-variant/20'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] text-outline">
                  <span>{st.num}</span>
                  {st.gateBadge && (
                    <span className="text-[9px] font-bold text-amber-300">{st.gateBadge}</span>
                  )}
                </div>
                <div className="font-semibold text-xs text-on-surface truncate">
                  {st.name}
                </div>
                <span className={`inline-block px-1.5 py-0.2 rounded text-[9px] uppercase tracking-wider border ${badgeClass}`}>
                  {statusText}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Approval Warning Banner (shown when awaiting approval) */}
      <ApprovalBanner isAwaitingApproval={isAwaitingApproval} />

      {/* Loading Skeleton View */}
      {activeLoading && (
        <div className="p-space-xl rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center gap-4 py-20 text-center animate-pulse">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <div className="flex flex-col gap-1">
            <span className="font-mono text-sm text-on-surface font-semibold">
              Loading Implementation Plan...
            </span>
            <span className="text-xs text-outline font-mono">
              Retrieving plan schema and verification gates from backend
            </span>
          </div>
        </div>
      )}

      {/* Error View */}
      {!activeLoading && activeError && (
        <div role="alert" className="p-space-xl rounded-xl bg-surface-container-low border border-red-500/30 flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="p-3 rounded-full bg-red-500/20 text-red-400">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <span className="font-semibold text-sm text-red-200">
            {activeError.message}
          </span>
          <span className="text-xs font-mono text-outline">
            Endpoint: {activeError.endpoint || `/api/v1/runs/${runId}/plan`}
          </span>
          <button
            type="button"
            onClick={fetchPlanData}
            className="mt-2 px-4 py-2 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-mono border border-outline-variant/30 transition-colors"
          >
            Retry Fetch
          </button>
        </div>
      )}

      {/* Empty Plan View */}
      {!activeLoading && !activeError && !activePlan && (
        <div className="p-space-xl rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="p-3 rounded-full bg-surface-container-high text-outline">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <span className="font-semibold text-sm text-on-surface">
            No Implementation Plan Registered
          </span>
          <p className="text-xs text-on-surface-variant font-mono max-w-md">
            The Planner Agent has not yet generated a plan for run <code className="text-primary">{runId}</code>, or the run has not reached Gate 01.
          </p>
        </div>
      )}

      {/* Main 2-Column Responsive Workspace */}
      {!activeLoading && !activeError && activePlan && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
          {/* Left Column (8 cols): Plan & Context Details */}
          <div className="lg:col-span-8 flex flex-col gap-space-lg">
            {/* 1. Issue Context Card */}
            <IssueContextCard issue={activePlan.issue} />

            {/* 2. Implementation Plan with Steps */}
            <ImplementationPlan plan={activePlan} />

            {/* 3. Affected Files Inspection Matrix */}
            <AffectedFilesMatrix files={activePlan.affectedFiles} />

            {/* 4. Risks & System Considerations */}
            <RisksSection risks={activePlan.risks} />

            {/* 5. Planned Verification Gates */}
            <VerificationGates gates={activePlan.verificationGates} />
          </div>

          {/* Right Column (4 cols): Gate 01 Approval Panel & Telemetry */}
          <div className="lg:col-span-4 flex flex-col gap-space-md">
            {/* Gate 01 Action Panel */}
            <ApprovalPanel
              statusText={
                isAwaitingApproval
                  ? 'AWAITING DECISION'
                  : activeDecisionState === 'approved'
                  ? 'APPROVED'
                  : activeDecisionState === 'rejected'
                  ? 'ABORTED'
                  : 'STANDBY'
              }
              isSubmitting={activeIsSubmitting}
              decisionState={activeDecisionState}
              feedbackText={feedbackText}
              onChangeFeedback={setFeedbackText}
              onApprove={handleApprove}
              onReject={handleReject}
              lastResponse={actionResponse}
              error={actionError}
            />

            {/* Plan Metadata & Telemetry */}
            <PlanMetadata metadata={activePlan.metadata} />

            {/* Execution Sandbox Status Card */}
            <SandboxStatusCard
              sandboxed={activePlan.sandboxed}
              sandboxDetails={
                activePlan.sandboxed
                  ? 'Isolated execution sandbox active. Write operations constrained to feature branch.'
                  : undefined
              }
            />
          </div>
        </div>
      )}

      {/* Bottom Dev State Simulator Bar */}
      <DevStateSimulator
        currentState={simulatorState}
        onSelectState={setSimulatorState}
      />
    </div>
  );
};
