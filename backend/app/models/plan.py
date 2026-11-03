"""Plan decision schemas for the human approval workflow.

Plain-language overview
-----------------------
When the Planner agent finishes writing its implementation plan, the run
pauses and waits for a human developer to review it. The developer can:

  * approve - accept the plan as-is; the Coder starts immediately.
  * edit    - submit a corrected version of the plan; the Coder uses the
              edited version (stored as a separate artifact so the original
              is preserved).
  * reject  - decline the plan entirely; the run is terminated.

This module defines the Pydantic schemas for that decision request (sent
by the frontend to POST /runs/{run_id}/plan/decision) and the internal
record the store keeps once a decision has been made.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Maximum allowed size for the edited plan JSON payload.
# 64 KiB prevents memory abuse while comfortably holding any realistic plan.
_MAX_EDITED_PLAN_BYTES: int = 64 * 1024


class PlanDecision(str, Enum):
    """The three possible decisions a human can make on a proposed plan.

    Values:
        approve: Accept the plan as-is. The Coder proceeds immediately.
        edit:    Submit a modified plan. The Coder uses the edited version.
        reject:  Decline the plan entirely. The run is marked rejected
                 (terminal in the current implementation).
    """

    approve = "approve"
    edit = "edit"
    reject = "reject"


class PlanDecisionIn(BaseModel):
    """Request body for POST /runs/{run_id}/plan/decision.

    Validation rules
    ----------------
    - decision must be one of: approve, edit, reject.
    - edited_plan is required when decision == 'edit' and is forbidden for
      approve/reject (to avoid ambiguous payloads).
    - edited_plan JSON serialisation must be <= 64 KiB.
    - reason is optional for any decision (max 2 000 characters). The
      backend stores it internally but never echoes it back in responses.
    - Extra fields are rejected (extra='forbid') to catch client typos early.
    """

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "edit", "reject"] = Field(
        ...,
        description="Human decision: approve, edit, or reject the proposed plan.",
        examples=["approve"],
    )
    edited_plan: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Modified plan object. Required when decision is 'edit', "
            "forbidden otherwise. Must be <= 64 KiB when serialised to JSON. "
            "The backend does not validate the plan's inner structure."
        ),
    )
    reason: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Optional short rationale for the decision (max 2 000 characters). "
            "Allowed for any decision type. Never echoed in API responses."
        ),
    )

    @model_validator(mode="after")
    def _validate_decision_payload(self) -> "PlanDecisionIn":
        """Cross-field validation: edited_plan is present iff decision == 'edit'.

        WHY THIS CROSS-FIELD CHECK:
        Requiring edited_plan only for 'edit' and forbidding it for 'approve'
        and 'reject' prevents ambiguous payloads where the client sends a plan
        object but a non-edit decision, which would silently discard the plan.
        """
        if self.decision == "edit":
            if self.edited_plan is None:
                raise ValueError(
                    "edited_plan is required when decision is 'edit'."
                )
            # Enforce 64 KiB size limit. We serialise to JSON ourselves to get
            # a consistent byte count regardless of how the client formatted it.
            try:
                encoded = json.dumps(self.edited_plan).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"edited_plan is not JSON-serialisable: {exc}"
                ) from exc
            if len(encoded) > _MAX_EDITED_PLAN_BYTES:
                raise ValueError(
                    f"edited_plan exceeds the 64 KiB limit "
                    f"({len(encoded):,} bytes > {_MAX_EDITED_PLAN_BYTES:,})."
                )
        else:
            # approve or reject: edited_plan must NOT be provided
            if self.edited_plan is not None:
                raise ValueError(
                    f"edited_plan must not be provided when decision "
                    f"is '{self.decision}'."
                )
        return self


class PlanDecisionRecord(BaseModel):
    """Internal-only record stored in the run store after a plan decision.

    This is NEVER returned to API callers. Its sole purpose is to provide
    an internal audit trail of what decision was made and when.

    NOTE: reason is untrusted user input. It is stored as data only, never
    executed, never included in log entries or API responses.
    """

    decision: PlanDecision
    reason: str | None = None
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the decision was recorded.",
    )
