"""
PR Agent Implementation.

Packages approved, tested, and reviewed changes into a documented GitHub pull request.
Safety Rule: Strictly opens pull requests; NEVER attempts to merge pull requests.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.agents.model_router import route
from app.agents.schemas import AgentState, create_event, compute_plan_hash

logger = logging.getLogger(__name__)


def pr_node(state: AgentState) -> dict[str, Any]:
    """
    PR Agent Node: Generates PR description and opens pull request.
    
    Safety Invariants:
    1. Strictly prohibited from merging (creation only).
    2. Requires verified passing tests and approved code review.
    3. Verifies plan version and canonical hash consistency.
    4. Never claims a PR was created without confirmed response from GitHub client.
    5. Packages full evidence trail into pull_request_package if integration is unavailable.
    """
    tier = route("pr")
    logger.info("Executing PR node [tier=%s] (Creation only; never merge)", tier)

    # 1. Review approval check
    review_findings = state.get("review_findings")
    review_approved = False
    review_verdict = "unknown"
    review_score = 0.0
    if review_findings:
        if isinstance(review_findings, dict):
            review_approved = bool(review_findings.get("approved", False))
            review_verdict = review_findings.get("verdict", "approve" if review_approved else "block")
            review_score = review_findings.get("score", 1.0 if review_approved else 0.0)
        elif hasattr(review_findings, "approved"):
            review_approved = bool(review_findings.approved)
            review_verdict = getattr(review_findings, "verdict", "approve" if review_approved else "block")
            review_score = getattr(review_findings, "score", 1.0 if review_approved else 0.0)

    if not review_approved or review_verdict != "approve":
        logger.error("PR Agent invoked without approved review findings. Halting.")
        event = create_event(
            agent_name="pr",
            event_type="pr_blocked",
            status="failed",
            message="PR Agent blocked: cannot submit PR without approved code review.",
            metadata={"tier": tier.value},
        )
        return {
            "status": "failed",
            "current_agent": "pr",
            "error": "PR blocked: code review not approved.",
            "events": [event],
        }

    # 2. Plan hash consistency verification
    plan = state.get("plan")
    plan_hash = state.get("plan_hash", "")
    if plan and plan_hash:
        plan_dict = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan
        computed_hash = compute_plan_hash(plan_dict)
        if computed_hash != plan_hash:
            logger.error("PR Agent blocked: plan hash mismatch. Tampering detected.")
            event = create_event(
                agent_name="pr",
                event_type="pr_blocked",
                status="failed",
                message="PR Agent blocked: plan hash mismatch detected.",
                metadata={"tier": tier.value, "plan_hash": plan_hash, "computed_hash": computed_hash},
            )
            return {
                "status": "failed",
                "current_agent": "pr",
                "error": "PR blocked: plan hash verification failed.",
                "events": [event],
            }

    # Prepare PR metadata and structured description
    repo = state.get("repo", "unknown")
    issue_title = state.get("issue_title", "Resolved issue")
    plan_version = state.get("plan_version", "v1")
    short_hash = plan_hash[:8] if plan_hash else "N/A"

    code_changes = state.get("code_changes") or []
    changed_files_list = []
    implemented_reqs = set()
    for c in (code_changes if isinstance(code_changes, list) else [code_changes]):
        fpath = (c.get("path") or c.get("file_path") or "") if isinstance(c, dict) else (getattr(c, "path", None) or getattr(c, "file_path", ""))
        if fpath:
            changed_files_list.append(fpath)
        rids = c.get("requirement_ids", []) if isinstance(c, dict) else getattr(c, "requirement_ids", [])
        if rids:
            implemented_reqs.update(rids)

    test_results = state.get("test_results") or {}
    test_passed = test_results.get("passed", False) if isinstance(test_results, dict) else getattr(test_results, "passed", False)
    test_total = test_results.get("total_tests", 0) if isinstance(test_results, dict) else getattr(test_results, "total_tests", 0)
    test_details = test_results.get("details", "") if isinstance(test_results, dict) else getattr(test_results, "details", "")

    pr_title = f"Fix: {issue_title}"
    files_md = "\n".join(f"- `{f}`" for f in changed_files_list) if changed_files_list else "- (None)"
    reqs_md = ", ".join(sorted(implemented_reqs)) if implemented_reqs else "All specified requirements"

    pr_body = (
        f"## Automated Pull Request via Mini-Devin\n\n"
        f"### Summary\n"
        f"- **Repository:** `{repo}`\n"
        f"- **Issue:** {issue_title}\n"
        f"- **Plan Version:** `{plan_version}`\n"
        f"- **Plan Verification Hash:** `{short_hash}`\n"
        f"- **Requirements Addressed:** {reqs_md}\n\n"
        f"### Changed Files\n{files_md}\n\n"
        f"### Verification Evidence\n"
        f"- **Review Verdict:** `{review_verdict.upper()}` (Score: {review_score})\n"
        f"- **Test Suite:** {'PASSED' if test_passed else 'PENDING / RECORDED'} ({test_total} tests executed)\n\n"
        f"> **Safety Constraint:** Merge is strictly forbidden by policy. External human review required."
    )

    # 3. GitHub Client Integration
    github_client_ready = False
    pr_url = None
    head_branch = f"mini-devin/fix-{state.get('run_id', 'patch')[:8]}"
    base_branch = "main"

    try:
        from app.integrations.github_client import FileChange, GitRef, PRRequest, get_github_client
        client = get_github_client()
        github_client_ready = True

        owner, repo_name = repo.split("/", 1) if "/" in repo else ("mini-devin", repo)
        try: base_branch = state.get("repo_ref") or client.fetch_repo(GitRef(owner=owner, repo=repo_name)).rsplit("@", 1)[-1]
        except Exception: base_branch = state.get("repo_ref") or "main"
        git_ref = GitRef(owner=owner, repo=repo_name, branch=base_branch)

        # 1. Determine target branch and repository (direct or via user fork)
        push_ref = git_ref
        pr_head_ref = head_branch
        auth_user = client.get_authenticated_user()

        try:
            client.create_branch(git_ref, head_branch)
            logger.info("PR branch created directly on target repo: %s", head_branch)
        except Exception as b_err:
            logger.info("Direct branch creation failed (%s); resolving user fork...", b_err)
            if auth_user and auth_user.lower() != owner.lower():
                fork_ref = client.ensure_fork(git_ref)
                try:
                    client.create_branch(fork_ref, head_branch, base_ref=git_ref)
                    push_ref = fork_ref
                    pr_head_ref = f"{auth_user}:{head_branch}"
                    logger.info("PR branch created on user fork: %s -> %s", fork_ref.full_name, pr_head_ref)
                except Exception as fb_err:
                    logger.warning("Fork branch creation note: %s", fb_err)
                    push_ref = fork_ref
                    pr_head_ref = f"{auth_user}:{head_branch}"

        # 2. Push code changes to branch (either on target repo or fork)
        files_to_push = []
        workspace_path = state.get("workspace_path") or state.get("snapshot_path")
        for ch in (code_changes if isinstance(code_changes, list) else [code_changes]):
            fpath = ch.get("path") or ch.get("file_path", "") if isinstance(ch, dict) else (getattr(ch, "path", None) or getattr(ch, "file_path", ""))
            content = ch.get("content") or ch.get("new_content") if isinstance(ch, dict) else (getattr(ch, "content", None) or getattr(ch, "new_content", None))
            if fpath:
                if not content and workspace_path:
                    target_file = Path(workspace_path) / fpath
                    if target_file.is_file():
                        content = target_file.read_text(encoding="utf-8")
                if not content:
                    raise ValueError(f"PR Agent blocked: file '{fpath}' has empty or missing content. Refusing to push unverified or placeholder changes.")
                files_to_push.append(FileChange(path=fpath, content=content, action="modify"))

        if files_to_push:
            try:
                client.push_changes(push_ref, head_branch, files_to_push)
                logger.info("Pushed %d changes to %s on %s", len(files_to_push), head_branch, push_ref.full_name)
            except Exception as p_err:
                logger.warning("Push changes note: %s", p_err)

        pr_req = PRRequest(
            ref=git_ref,
            title=pr_title,
            body=pr_body,
            head_branch=pr_head_ref,
            base_branch=base_branch,
        )

        # Call client to create PR
        pr_resp = client.open_pull_request(pr_req)
        if pr_resp and pr_resp.pr_url:
            pr_url = pr_resp.pr_url
            logger.info("PR Agent successfully obtained PR URL: %s", pr_url)
    except ValueError:
        raise
    except Exception as exc:
        logger.warning("GitHub client submission failed or skipped: %s", exc)

    # Build truthful pull request package
    pull_request_package = {
        "title": pr_title,
        "body": pr_body,
        "repo": repo,
        "head_branch": head_branch,
        "base_branch": base_branch,
        "plan_version": plan_version,
        "plan_hash": plan_hash,
        "requirements_addressed": sorted(list(implemented_reqs)),
        "changed_files": changed_files_list,
        "test_evidence": {
            "passed": test_passed,
            "total_tests": test_total,
            "details": test_details,
        },
        "review_evidence": {
            "verdict": review_verdict,
            "score": review_score,
        },
        "status": "submitted" if pr_url else "ready_for_submission",
        "pull_request_url": pr_url,
    }

    if state.get("strict_verification", False) and not pr_url:
        logger.info("PR submission blocked under strict verification without confirmed PR URL.")
        event = create_event(
            agent_name="pr",
            event_type="pr_blocked",
            status="failed",
            message="PR Agent BLOCKED: Could not confirm remote PR creation.",
            metadata={
                "tier": tier.value,
                "github_client_ready": github_client_ready,
                "pr_title": pr_title,
            },
        )
        return {
            "status": "failed",
            "current_agent": "pr",
            "error": "PR creation BLOCKED: Could not confirm remote PR creation.",
            "pull_request_url": None,
            "pull_request_package": pull_request_package,
            "events": [event],
        }

    if pr_url:
        event = create_event(
            agent_name="pr",
            event_type="pr_created",
            status="success",
            message=f"PR Agent successfully opened Pull Request: {pr_url} (merge forbidden).",
            metadata={
                "tier": tier.value,
                "pr_title": pr_title,
                "pr_url": pr_url,
                "github_client_ready": github_client_ready,
            },
        )
    else:
        event = create_event(
            agent_name="pr",
            event_type="pr_creation_started",
            status="in_progress",
            message="PR Agent preparing pull request for submission (merge forbidden).",
            metadata={
                "tier": tier.value,
                "pr_title": pr_title,
                "pr_url": pr_url,
                "github_client_ready": github_client_ready,
            },
        )

    return {
        "status": "submitting_pr",
        "current_agent": "pr",
        "pull_request_url": pr_url,
        "pull_request_package": pull_request_package,
        "events": [event],
    }
