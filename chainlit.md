# Welcome to Mini-Devin 🤖🚀

**Autonomous GitHub Issue-to-Pull-Request Multi-Agent System**

Mini-Devin turns GitHub issues into tested, peer-reviewed pull requests with human-in-the-loop oversight and frozen cryptographic plan binding.

### How to use:
- **GitHub Issue URL:** Paste any public issue link (e.g., `https://github.com/owner/repo/issues/42`)
- **Repository & Issue:** Type `owner/repo: Fix null pointer in auth service`
- **Free Text / Demo Mode:** Type any bug report or feature request to run against the demo repository

### Workflow Architecture:
1. **Triage Agent:** Classifies issues into bug fixes, feature requests, or tests, filtering out-of-scope tasks.
2. **Retrieval Agent:** Scans the codebase to gather grounded code snippets and context.
3. **Planner Agent:** Synthesizes code evidence into a frozen implementation plan with cryptographic hash verification.
4. **Operator Approval:** The full plan opens automatically in the **right-side preview panel** (`implementation_plan.md`) for your review before any code modifications occur.
5. **Execution Pipeline:** Coder, Test Runner, Debugger, Reviewer, and PR Agent handle implementation, testing, and pull request submission once approved.
