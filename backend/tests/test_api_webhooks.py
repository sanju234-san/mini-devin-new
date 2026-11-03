"""Tests for POST /webhooks/github route."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.agent_gateway import AgentGateway
from app.api.deps import get_agent_gateway, get_settings_dep
from app.config import Settings
from app.main import create_app
from app.models.run import IssueIn, RunStatus

SECRET = "super-secret-webhook-key"


def sign_payload(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature formatted as sha256=<hex>."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_secret_unset_gives_503():
    settings = Settings(GITHUB_WEBHOOK_SECRET=None)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        body = b'{"action": "ping"}'
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=123456",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Webhook secret not configured"


def test_webhook_secret_override_via_dependency():
    """Verify webhook secret comes from dependency path and can be overridden per-test."""
    app = create_app()
    custom_secret = "overridden-test-secret"
    app.dependency_overrides[get_settings_dep] = lambda: Settings(
        GITHUB_WEBHOOK_SECRET=SecretStr(custom_secret)
    )

    with TestClient(app) as client:
        body = json.dumps({"action": "ping"}).encode("utf-8")
        sig = sign_payload(custom_secret, body)
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"msg": "pong"}

        # Ensure custom_secret is not leaked in response
        assert custom_secret not in response.text


def test_webhook_missing_signature_gives_401():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=b'{"action": "ping"}',
            headers={"X-GitHub-Event": "ping"},
        )
        assert response.status_code == 401
        assert "Missing" in response.json()["detail"]


def test_webhook_malformed_signature_header_gives_401():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=b'{"action": "ping"}',
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "invalid_format_without_prefix",
            },
        )
        assert response.status_code == 401
        assert "Malformed" in response.json()["detail"]


def test_webhook_empty_digest_gives_401():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=b'{"action": "ping"}',
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=",
            },
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]


def test_webhook_non_ascii_signature_gives_401_not_500():
    """Verify non-ASCII signature headers fail with 401, never raising TypeError/500."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=b'{"action": "ping"}',
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": b"sha256=invalid\xfc\xf1\xee\xe7\xf8d\xe9",
            },
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]


def test_webhook_uppercase_hex_digest_accepted():
    """Verify uppercase hex signatures are accepted per GitHub hex digest spec."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        body = json.dumps({"action": "ping"}).encode("utf-8")
        lower_sig = sign_payload(SECRET, body)
        upper_sig = "sha256=" + lower_sig[len("sha256=") :].upper()

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": upper_sig,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"msg": "pong"}


def test_webhook_wrong_signature_gives_401():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            content=b'{"action": "ping"}',
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=deadbeefdeadbeef",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid signature"


def test_webhook_tampered_body_fails():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        original_body = b'{"msg": "original"}'
        sig = sign_payload(SECRET, original_body)

        tampered_body = b'{"msg": "tampered"}'
        response = client.post(
            "/webhooks/github",
            content=tampered_body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid signature"


def test_webhook_oversize_body_rejected_413():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        oversize_body = b"A" * (1_048_576 + 1)
        response = client.post(
            "/webhooks/github",
            content=oversize_body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=somehash",
            },
        )
        assert response.status_code == 413


def test_webhook_oversize_streaming_no_content_length():
    """Verify streaming size limit works even when Content-Length header is omitted."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        def chunk_gen():
            for _ in range(17):
                yield b"X" * 65536  # 17 * 65536 = 1,114,112 bytes > 1 MiB

        # Passing a generator without Content-Length header
        response = client.post(
            "/webhooks/github",
            content=chunk_gen(),
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=fake",
            },
        )
        assert response.status_code == 413


def test_webhook_oversize_streaming_lying_small_content_length():
    """Verify streaming limit aborts even if sender sends a falsely small Content-Length."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        def chunk_gen():
            for _ in range(17):
                yield b"Y" * 65536

        response = client.post(
            "/webhooks/github",
            content=chunk_gen(),
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=fake",
                "Content-Length": "100",  # Lying small header
            },
        )
        assert response.status_code == 413


def test_webhook_body_exactly_at_limit_works():
    """Verify body of exactly 1,048,576 bytes is accepted."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        # Construct valid JSON of exactly 1,048,576 bytes
        prefix = b'{"action":"ping","extra":"'
        suffix = b'"}'
        padding_len = 1_048_576 - len(prefix) - len(suffix)
        body = prefix + (b"A" * padding_len) + suffix
        assert len(body) == 1_048_576

        sig = sign_payload(SECRET, body)
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"msg": "pong"}


def test_webhook_valid_signature_malformed_json_gives_400():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        malformed_body = b"{not-valid-json: hello"
        sig = sign_payload(SECRET, malformed_body)
        response = client.post(
            "/webhooks/github",
            content=malformed_body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 400
        assert "Malformed JSON" in response.json()["detail"]


def test_webhook_ping_event_acknowledged_200():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        body = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"msg": "pong"}


def test_webhook_non_opened_action_ignored_200():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        body = json.dumps({
            "action": "closed",
            "issue": {"number": 1, "title": "Closed issue", "body": "Closed"},
            "repository": {"full_name": "octocat/Hello-World"},
        }).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"msg": "ignored"}

        runs_list = client.get("/runs").json()
        assert runs_list["total"] == 0


def test_webhook_opened_issue_creates_run_202():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        payload = {
            "action": "opened",
            "issue": {
                "number": 12,
                "title": "Fix regression in payment validator",
                "body": "NullPointerException on checkout",
                "user": {"login": "octocat"},
            },
            "repository": {
                "full_name": "octocat/Hello-World",
                "private": False,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-uuid-1",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == RunStatus.queued.value
        assert data["issue"]["repo"] == "octocat/Hello-World"
        assert data["issue"]["issue_number"] == 12
        assert data["issue"]["title"] == "Fix regression in payment validator"

        run_res = client.get(f"/runs/{data['id']}")
        assert run_res.status_code == 200
        assert run_res.json()["issue_body"] == "NullPointerException on checkout"


def test_webhook_null_issue_body_accepted():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        payload = {
            "action": "opened",
            "issue": {
                "number": 15,
                "title": "Issue without body",
                "body": None,
            },
            "repository": {
                "full_name": "octocat/Hello-World",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 202
        run_id = response.json()["id"]

        run_res = client.get(f"/runs/{run_id}")
        assert run_res.status_code == 200
        assert run_res.json()["issue_body"] == ""


def test_webhook_untrusted_input_limits_422_no_echo():
    """Verify oversize issue title/body returns 422 with generic detail and no payload echo."""
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        malicious_oversize_text = "SECRET_PAYLOAD_" * 5000
        payload = {
            "action": "opened",
            "issue": {
                "number": 1,
                "title": "Title",
                "body": malicious_oversize_text,  # Exceeds 65536 limit
            },
            "repository": {
                "full_name": "octocat/Hello-World",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 422
        # Detail must be generic and not echo the payload text
        data = response.json()
        assert "Invalid issue payload" in data["detail"]
        assert "SECRET_PAYLOAD_" not in response.text


def test_webhook_duplicate_delivery_idempotency():
    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)

    with TestClient(app) as client:
        payload = {
            "action": "opened",
            "issue": {
                "number": 20,
                "title": "Idempotent issue",
                "body": "Body text",
            },
            "repository": {
                "full_name": "octocat/Hello-World",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = sign_payload(SECRET, body)

        res1 = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-unique-token-42",
            },
        )
        assert res1.status_code == 202
        run_id_1 = res1.json()["id"]

        res2 = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-unique-token-42",
            },
        )
        assert res2.status_code == 202
        run_id_2 = res2.json()["id"]

        assert run_id_1 == run_id_2
        runs_list = client.get("/runs").json()
        assert runs_list["total"] == 1


def test_webhook_gateway_failure_handled_gracefully():
    """Verify background task failure in webhook intake marks run failed without crashing."""
    class FailingGateway:
        async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
            raise RuntimeError("Agent sandbox unavailable")

    settings = Settings(GITHUB_WEBHOOK_SECRET=SecretStr(SECRET))
    app = create_app(settings=settings)
    app.dependency_overrides[get_agent_gateway] = lambda: FailingGateway()

    with TestClient(app) as client:
        payload = {
            "action": "opened",
            "issue": {
                "number": 33,
                "title": "Crash test",
                "body": "Body",
            },
            "repository": {
                "full_name": "octocat/Hello-World",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = sign_payload(SECRET, body)

        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issues",
                "X-Hub-Signature-256": sig,
            },
        )
        assert response.status_code == 202
        run_id = response.json()["id"]

        # TestClient executes background task synchronously
        detail = client.get(f"/runs/{run_id}").json()
        assert detail["status"] == "failed"
        assert detail["error"] == "Failed to start agent run"
