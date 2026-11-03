# Mini-Devin — Chainlit Live Console

Welcome to the **Mini-Devin Live Agent Console** (`chainlit_console`). This console provides a lightweight, real-time observation view complementing the Next.js developer dashboard.

### Capabilities
- **Live Event Streaming**: Subscribes to backend agent execution step events (`started`, `tool_call`, `completed`, `failed`, `retry`, `paused`, `escalated`) streamed over WebSocket (`/ws/runs/{run_id}`).
- **8-Stage Pipeline Visibility**: Observes agent progression through Triage, Retrieval, Planner, Gate, Coder, Test-Runner, Debugger, and PR Agent.
- **Structured Step Inspection**: Formats tool calls, execution parameters, exit codes, and error diagnostics using native Chainlit steps.
- **Connection & Telemetry Status**: Displays honest connection states (`CONNECTING`, `CONNECTED`, `DISCONNECTED`, `ERROR`) without obscuring backend unavailability.

### Operational Boundaries & Limitations
- **Read-Only Telemetry**: Operator actions in this console are strictly observational to maintain agent sandbox isolation.
- **No Direct Workflow Mutation**: Interactive plan approvals, diff editing, and manual test triggers must be conducted via the Next.js dashboard.
- **Data Contract**: Step events adhere strictly to the schema in `docs/design/schemas.md` §4 and `frontend/src/hooks/types.ts`. Full agent reasoning traces are archived to MLflow rather than streamed over step events.
- **Illustrative Preview Mode**: An isolated preview mode (`/demo`) is available for interface verification when the backend WebSocket endpoint is offline or pending implementation.
