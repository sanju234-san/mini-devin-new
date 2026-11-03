'use client';

import React, { useState } from 'react';
import type { ReviewCriteriaItem, ApprovalDecision } from './types';
import { DEFAULT_REVIEW_CRITERIA } from './planApprovalUtils';

interface ApprovalPanelProps {
  statusText?: string;
  isSubmitting: boolean;
  decisionState: ApprovalDecision;
  feedbackText: string;
  onChangeFeedback: (text: string) => void;
  onApprove: (feedback?: string) => Promise<void>;
  onReject: (reason?: string) => Promise<void>;
  lastResponse?: { status: string; message?: string } | null;
  error?: string | null;
}

export const ApprovalPanel: React.FC<ApprovalPanelProps> = ({
  statusText = 'AWAITING DECISION',
  isSubmitting,
  decisionState,
  feedbackText,
  onChangeFeedback,
  onApprove,
  onReject,
  lastResponse,
  error,
}) => {
  const [criteria, setCriteria] = useState<ReviewCriteriaItem[]>(DEFAULT_REVIEW_CRITERIA);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const toggleCriterion = (id: string) => {
    setCriteria((prev) =>
      prev.map((c) => (c.id === id ? { ...c, checked: !c.checked } : c))
    );
  };

  const checkedCount = criteria.filter((c) => c.checked).length;
  const isTerminal = decisionState === 'approved' || decisionState === 'rejected';

  const handleConfirmReject = async () => {
    setShowRejectConfirm(false);
    await onReject(rejectReason.trim() || undefined);
  };

  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/30 p-space-md sm:p-space-lg flex flex-col gap-4 shadow-md sticky top-20">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
          <h3 className="font-bold text-xs sm:text-sm text-on-surface uppercase tracking-wider font-mono">
            Gate 01: Approval
          </h3>
        </div>

        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-300 border border-amber-500/30">
          {statusText}
        </span>
      </div>

      {/* Explanation of Consequence */}
      <div className="p-3 rounded-lg bg-surface-container/60 border border-outline-variant/20 flex items-start gap-2.5 text-xs">
        <svg className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          Approving this plan authorizes the <strong className="text-on-surface font-semibold">backend Coder Agent</strong> to synthesize code patches and launch containerized tests in the sandbox.
        </p>
      </div>

      {/* Reviewer Verification Criteria Checklist */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-wider text-outline font-semibold">
            Reviewer Verification Criteria
          </span>
          <span className="font-mono text-[10px] text-primary">
            {checkedCount}/{criteria.length} checked
          </span>
        </div>
        <p className="text-[10px] text-outline font-mono italic">
          (Review aid only — not submitted to backend)
        </p>

        <div className="flex flex-col gap-1.5 pt-1">
          {criteria.map((item) => (
            <label
              key={item.id}
              className="flex items-start gap-2.5 p-1.5 rounded-md hover:bg-surface-container/40 transition-colors cursor-pointer select-none text-xs"
            >
              <input
                type="checkbox"
                checked={item.checked}
                disabled={isSubmitting || isTerminal}
                onChange={() => toggleCriterion(item.id)}
                className="mt-0.5 w-3.5 h-3.5 rounded bg-surface-container-high border-outline-variant/50 text-primary focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <span className={`text-[11px] leading-tight ${item.checked ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                {item.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Agent Steering / Feedback Textarea */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="agent-feedback" className="font-mono text-[10px] uppercase tracking-wider text-outline font-semibold">
            Agent Steering / Feedback
          </label>
          <span className="text-[10px] text-outline font-mono">optional instructions</span>
        </div>
        <textarea
          id="agent-feedback"
          value={feedbackText}
          disabled={isSubmitting || isTerminal}
          onChange={(e) => onChangeFeedback(e.target.value)}
          placeholder="Provide specific guidance, files to exclude, or constraints before the Coder Agent proceeds..."
          rows={3}
          className="w-full text-xs font-mono bg-surface-container rounded-lg border border-outline-variant/30 p-2.5 text-on-surface placeholder:text-outline focus:outline-none focus:border-primary transition-colors resize-none disabled:opacity-60"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col gap-2 pt-1" aria-busy={isSubmitting}>
        {/* 1. Primary Approve Button */}
        <button
          type="button"
          disabled={isSubmitting || isTerminal}
          onClick={() => onApprove(feedbackText.trim() || undefined)}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-primary-container text-on-primary-container font-semibold text-xs transition-all shadow-sm hover:brightness-110 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
        >
          {isSubmitting && decisionState === 'submitting' ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-on-primary-container border-t-transparent rounded-full animate-spin" />
              <span>Transmitting Approval...</span>
            </>
          ) : decisionState === 'approved' ? (
            <>
              <svg className="w-4 h-4 text-emerald-950" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>Plan Approved & Handed Off</span>
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>Approve Plan & Start Coder Agent</span>
            </>
          )}
        </button>

        {/* 2. Secondary Request Changes Button (Disabled Contract Gap) */}
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="CONTRACT GAP: Request Changes / Revise Plan endpoint not yet defined in API contract"
          className="w-full flex items-center justify-between py-2 px-3 rounded-lg bg-surface-container text-outline border border-outline-variant/30 text-xs font-mono cursor-not-allowed opacity-70"
        >
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            <span>Request Changes / Revise Plan</span>
          </div>
          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-surface-container-high border border-outline-variant/30 text-outline">
            Contract Gap
          </span>
        </button>

        {/* 3. Reject Button with Confirmation Dialog */}
        {!showRejectConfirm ? (
          <button
            type="button"
            disabled={isSubmitting || isTerminal}
            onClick={() => setShowRejectConfirm(true)}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500/20 text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            <span>Reject Plan & Abort Run</span>
          </button>
        ) : (
          <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 flex flex-col gap-2 animate-fadeIn text-xs">
            <span className="text-red-200 font-semibold leading-tight">
              Confirm Run Abort?
            </span>
            <p className="text-[11px] text-red-300/80 leading-relaxed">
              Rejecting will terminate the autonomous loop. This action cannot be undone.
            </p>
            <input
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection (optional)..."
              className="w-full text-xs font-mono bg-surface-container rounded border border-outline-variant/30 p-1.5 text-on-surface"
            />
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleConfirmReject}
                className="flex-1 py-1.5 px-2 rounded bg-red-600 hover:bg-red-500 text-white font-semibold text-xs transition-colors disabled:opacity-50"
              >
                Confirm Abort
              </button>
              <button
                type="button"
                onClick={() => setShowRejectConfirm(false)}
                className="py-1.5 px-3 rounded bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-mono transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Backend Response or Error Feedbacks */}
      {lastResponse && (
        <div className="p-2.5 rounded-lg bg-surface-container border border-outline-variant/30 text-xs font-mono flex flex-col gap-1">
          <div className="flex items-center justify-between text-[10px] text-outline">
            <span>Backend Response:</span>
            <span className="text-primary font-semibold uppercase">{lastResponse.status}</span>
          </div>
          {lastResponse.message && (
            <p className="text-[11px] text-on-surface-variant">{lastResponse.message}</p>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs font-mono">
          {error}
        </div>
      )}
    </div>
  );
};
