/**
 * Plan Approval Types for Mini-Devin Dashboard
 *
 * Types for the Human-in-the-loop Gate 01 Plan Approval screen.
 * Interfaces adhere to contract boundaries between Tamanna (REST/Backend)
 * and Sanjeevni (Agents/LangGraph).
 */

import type {
  ImplementationPlanData,
  PlanStep,
  AffectedFile,
  PlanRisk,
  VerificationGate,
  PlanMetadata,
  IssueContext,
  ApiError,
} from '../../services/types';

export type {
  ImplementationPlanData,
  PlanStep,
  AffectedFile,
  PlanRisk,
  VerificationGate,
  PlanMetadata,
  IssueContext,
};

export type ApprovalDecision = 'idle' | 'submitting' | 'approved' | 'rejected' | 'changes_requested';

export interface ReviewCriteriaItem {
  id: string;
  label: string;
  checked: boolean;
}

export type SimulatorState =
  | 'real'
  | 'awaiting_approval'
  | 'loading'
  | 'submitting'
  | 'approved'
  | 'changes_requested'
  | 'empty'
  | 'error';

export interface PlanApprovalUiState {
  isLoading: boolean;
  error: ApiError | null;
  plan: ImplementationPlanData | null;
  decisionState: ApprovalDecision;
  feedbackText: string;
  isSubmitting: boolean;
}
