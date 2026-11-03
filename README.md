# Mini-Devin

Autonomous GitHub issue-to-pull-request multi-agent system. Reads an issue,
plans a fix, writes the code, verifies it live in an isolated sandbox, and
opens a documented pull request — with a human approving the plan before
any file is touched.

## Structure

- `backend/` — FastAPI REST layer + the LangGraph agent orchestration (8 sub-agents)
- `frontend/` — React dashboard (Live Console, Plan approval, Diff viewer, Tests & Preview, Artifacts)
- `chainlit_console/` — live streaming console for watching an agent run in real time
- `evaluation/` — benchmark harness (fix accuracy, test-pass rate, SWE-bench Lite mini-eval)
- `docs/` — synopsis, activity diagram, UI design prompts
- `infra/` — CI/CD and local dev orchestration (`docker-compose.yml`)

## Local development

```bash
cp .env.example .env   # fill in your keys
docker compose -f infra/docker-compose.yml up
```

Backend: http://localhost:8000 · Frontend: http://localhost:5173 · Chainlit: http://localhost:8001
