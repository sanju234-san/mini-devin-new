"""GitHub webhook receiver (issue opened/updated, ping, etc.).

This module listens for incoming webhook events sent by GitHub. When a new
issue is opened, Mini-Devin verifies the signature, enforces idempotency,
and automatically schedules an agent run to resolve the issue.

Security Principles:
- Streaming body size limit: Requests larger than 1 MiB are aborted immediately
  during streaming to defend against memory exhaustion and chunked-transfer abuse.
- Raw-bytes verification: Signatures are computed directly over the raw request
  bytes before any JSON parsing to guarantee cryptographic fidelity.
- Constant-time comparison: `hmac.compare_digest` with ASCII bytes prevents timing
  attacks and prevents 500 errors from non-ASCII header values.
- Fail closed: If the webhook secret is unset, requests are rejected with 503.
  If the signature is missing or invalid, requests are rejected with 401.
- No sensitive logs: Request bodies, signatures, and secrets are never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.api.agent_gateway import AgentGateway, run_agent_background_task
from app.api.deps import get_agent_gateway, get_run_store, get_settings_dep
from app.api.run_store import RunStore
from app.config import Settings
from app.models.run import IssueIn, RunSummary

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# 1 MiB maximum payload size to protect against denial-of-service
MAX_WEBHOOK_BYTES = 1_048_576


class GitHubWebhookRepo(BaseModel):
    """Repository subset parsed from the GitHub webhook."""

    model_config = ConfigDict(extra="ignore")
    full_name: str


class GitHubWebhookIssue(BaseModel):
    """Issue subset parsed from the GitHub webhook."""

    model_config = ConfigDict(extra="ignore")
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=256)
    body: str | None = Field(default="", max_length=65536)


class GitHubWebhookOpenedPayload(BaseModel):
    """Validated structure for 'issues' events with 'opened' action."""

    model_config = ConfigDict(extra="ignore")
    action: str
    repository: GitHubWebhookRepo
    issue: GitHubWebhookIssue


@router.post(
    "/github",
    summary="GitHub webhook intake endpoint",
    responses={
        200: {"description": "Ping acknowledged or event ignored"},
        202: {"model": RunSummary, "description": "Issue opened and run queued"},
    },
)
async def github_webhook(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    store: RunStore = Depends(get_run_store),
    gateway: AgentGateway = Depends(get_agent_gateway),
    settings: Settings = Depends(get_settings_dep),
) -> dict | RunSummary:
    """Receive, authenticate, and process GitHub webhook events."""
    # ── 1. Early Content-Length check if provided ───────────────────
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_WEBHOOK_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Payload exceeds 1 MiB limit",
                )
        except ValueError:
            pass

    # ── 2. Stream and count body bytes ──────────────────────────────
    # WHY STREAMING IS USED:
    # A sender can omit Content-Length, lie with a small Content-Length header,
    # or use chunked transfer encoding. Reading chunks via request.stream() while
    # keeping a running byte count allows us to abort immediately with 413 the moment
    # total bytes exceed 1 MiB, without buffering gigabytes into memory.
    body_chunks: list[bytes] = []
    bytes_read = 0
    async for chunk in request.stream():
        bytes_read += len(chunk)
        if bytes_read > MAX_WEBHOOK_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Payload exceeds 1 MiB limit",
            )
        body_chunks.append(chunk)
    body = b"".join(body_chunks)

    # ── 3. Verify webhook secret configuration ──────────────────────
    webhook_secret = settings.GITHUB_WEBHOOK_SECRET
    # Fail closed if the secret has not been configured in the environment
    if webhook_secret is None or not webhook_secret.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    # ── 4. Verify signature header with byte-level comparison ───────
    signature_header = request.headers.get("x-hub-signature-256")
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header",
        )

    # Must start with standard GitHub prefix 'sha256='
    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed X-Hub-Signature-256 header",
        )

    provided_hex = signature_header[len("sha256=") :].strip()
    if not provided_hex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Calculate HMAC-SHA256 digest on the raw byte sequence
    secret_bytes = webhook_secret.get_secret_value().encode("utf-8")
    expected_hex = hmac.new(
        secret_bytes,
        body,
        hashlib.sha256,
    ).hexdigest()

    # WHY ENCODE TO ASCII BYTES:
    # hmac.compare_digest raises a TypeError if given non-ASCII strings, which would
    # crash with an unhandled 500 error. Encoding both sides to ASCII bytes catches
    # non-ASCII headers cleanly and allows constant-time comparison. Lowercase comparison
    # is used to adhere to GitHub's hexadecimal specification case-insensitively.
    try:
        expected_bytes = expected_hex.encode("ascii")
        provided_bytes = provided_hex.lower().encode("ascii")
    except UnicodeEncodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    if not hmac.compare_digest(expected_bytes, provided_bytes):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # ── 5. Parse JSON (only after valid signature check) ────────────
    try:
        raw_json = json.loads(body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in request body",
        )

    # ── 6. Inspect event type ───────────────────────────────────────
    event_type = request.headers.get("x-github-event", "")
    if event_type == "ping":
        return {"msg": "pong"}

    if event_type != "issues":
        return {"msg": "ignored"}

    action = raw_json.get("action") if isinstance(raw_json, dict) else None
    if action != "opened":
        return {"msg": "ignored"}

    # ── 7. Validate issue payload subset with generic error detail ──
    # WHY GENERIC DETAIL IS RETURNED:
    # If GitHub sends a malformed or oversize field, default ValidationError detail
    # echoes the user input back in the response. Using a clean generic message
    # prevents reflecting untrusted or oversize payloads back to clients.
    try:
        opened_payload = GitHubWebhookOpenedPayload.model_validate(raw_json)
        issue_body_str = opened_payload.issue.body or ""
        issue_in = IssueIn(
            repo=opened_payload.repository.full_name,
            issue_number=opened_payload.issue.number,
            title=opened_payload.issue.title,
            body=issue_body_str,
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid issue payload: fields exceed allowed limits or format constraints",
        )

    # ── 8. Atomic idempotency and run creation ──────────────────────
    # Delivery IDs longer than 128 characters are ignored/treated as missing inside the store
    delivery_id = request.headers.get("x-github-delivery")
    run, created = await store.create_run_for_delivery(delivery_id, issue_in)

    # Only schedule agent processing if this delivery newly created the run
    if created:
        background_tasks.add_task(run_agent_background_task, run.id, issue_in, gateway, store)

    response.status_code = status.HTTP_202_ACCEPTED
    return RunSummary(
        id=run.id,
        status=run.status,
        current_step=run.current_step,
        issue=run.issue,
        created_at=run.created_at,
        updated_at=run.updated_at,
        error=run.error,
    )
