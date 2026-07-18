# ShanHaiEdu Repository Constitution

This file is the mandatory operating agreement for every human developer, vendor and coding agent working in this repository. It describes how work is performed. Product behavior belongs in `docs/product/`, `docs/workflows/` and `contracts/`.

## 1. Sources of truth

Use each source for one purpose only:

1. `README.md`: stable project introduction and start commands.
2. `AGENTS.md`: stable repository-wide rules.
3. `CURRENT_STATUS.md`: current milestone, active work and next gate only.
4. GitHub Issues: task scope, acceptance criteria, decisions and task status.
5. GitHub Pull Requests: changed code, verification evidence and handoff.
6. `docs/product/` and `docs/workflows/`: current product intent and business semantics.
7. `contracts/`: current machine-readable boundaries.
8. Current code, migrations and tests: implemented runtime behavior.
9. Git history: superseded versions and historical context.

If intent, contract and implementation disagree, stop and open or update an Issue. Do not silently choose one, support contradictory behavior, or add a patch note.

## 2. Required takeover sequence

Before changing files:

1. Read `README.md`, this file and `CURRENT_STATUS.md`.
2. Run `git fetch origin --prune` and inspect branch, HEAD, upstream and dirty files.
3. Read the assigned Issue and linked Pull Request.
4. Read only the module documents, contracts, code and tests relevant to the task.
5. State the task goal, completed work, blockers and next action before continuing.

Do not begin by reading all Git history, all documents or prior chat transcripts. Do not modify files when the Issue, Pull Request and current status materially disagree.

## 3. Task contract

- Every change starts from a GitHub Issue with goal, scope, non-scope, acceptance criteria, risks, dependencies and tests.
- One Issue has one current owner, one primary task branch and one primary Pull Request.
- Before a substantive Pull Request is merged, the primary agent assigns a read-only subagent that did not implement the change to review the complete base-to-head diff. The subagent report is the repository's engineering approval evidence.
- Large outcomes use a parent Issue and independently acceptable child Issues.
- Task states are `ready`, `in-progress`, `blocked`, `review` and `done`.
- GitHub Issues and Pull Requests are the task and handoff truth. Do not add task journals to the repository.

See `docs/governance/TEAM_WORKFLOW.md` for the full lifecycle.

## 4. Branch and commit rules

- `main` is protected, reviewable and releasable. Never force-push it.
- Branch from an up-to-date `main` using `<type>/<issue>-<short-name>`.
- Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore` and `hotfix`.
- Open a Draft Pull Request on the day work starts.
- Target three working days per task branch. Re-scope a branch that remains unmergeable after five working days.
- Use Conventional Commit messages such as `feat(workflow): add lesson-plan node`.
- Default to Squash Merge. The Pull Request title becomes the main-branch commit.
- Delete the remote branch after merge and prune local branches and worktrees.
- Never use ordinary `--force`; `--force-with-lease` is allowed only on a clean private task branch after an intentional rebase.

Do not create permanent `develop`, `frontend`, `backend`, personal or version branches.

## 5. Handoff and session closure

Before pausing, switching owners or ending a development session:

1. Separate unrelated changes.
2. Run risk-appropriate tests.
3. Commit a safe checkpoint; an explicit `WIP:` commit is allowed on a task branch.
4. Push the task branch and update its Draft Pull Request.
5. Add the handoff block from `docs/governance/TEAM_WORKFLOW.md` to the Issue or Pull Request.

Uncommitted local files are not a handoff. Never claim work is saved without a verifiable commit and remote branch.

## 6. Documentation rules

- The current tree contains one active version of each fact.
- Edit the canonical document in place and delete the superseded document in the same Pull Request.
- Never add `v1`, `v2`, `final`, `latest`, dated copies, addenda or running histories to active documentation.
- Discussions, alternatives, temporary implementation plans and daily logs stay in Issues and Pull Requests.
- A document has one responsibility. At more than 300 lines, split it or explain the exception in review.
- New documents must have an owner, audience, canonical path and deletion or replacement rule.
- Durable architectural or product changes require a Decision Issue before canonical documents are changed.

See `docs/governance/DOCUMENT_POLICY.md` for placement and lifecycle rules.

## 7. Engineering boundaries

- Frontend: React 19, TypeScript strict, Vite, React Router, Tailwind CSS, Radix/shadcn, TanStack Query and Zustand for UI state only.
- Backend: Python 3.12 modular FastAPI monolith plus workers. Split services only after measured need.
- PostgreSQL is the business source of truth. Redis is not.
- All text, image, video and TTS calls go through the server-side model gateway.
- Provider secrets never enter browser code, Git, logs, exported packages or prompts shown to users.
- Frontend types are generated from OpenAPI. Do not maintain duplicate DTOs.
- Database changes require Alembic migrations. Production must not auto-create tables.
- Workflow, Prompt, content definition and artifact versions are immutable after publication.
- General creation studios exchange immutable creation packages and atomic save operations with projects.

## 8. Code quality rules

- Organize backend code by business module and frontend code by feature, not by dumping all controllers, services or components into global folders.
- A module exposes an application interface; another module must not reach into its internal repository or tables.
- Extend node and content behavior through registries, schemas and capabilities, not growing type conditionals.
- Remove dead code in the same change. Do not keep commented-out implementations, `.old`, `.bak`, `_copy` or `_final` files.
- A temporary feature flag must link to a removal Issue and target milestone.
- The third repetition of business logic must be extracted or explicitly justified.
- Files over 400 lines, functions over 60 lines and React components over 250 lines trigger a split-or-explain review.
- Pull Requests over 20 business source files or 800 net non-generated lines require a review map and a reason they cannot be divided.

Generated code, schemas, migrations and focused fixtures may exceed size triggers but must remain isolated.

## 9. Verification and completion

Use test-driven development for domain behavior and bug fixes. Report exact commands and failures.

Independent review is mandatory before a Pull Request becomes Ready or merges. The reviewer subagent reports findings first with file and line references, verifies the relevant commands, and records residual risk. The review evidence binds the exact base SHA and head SHA. Any push, rebase or other head change invalidates the approval and requires a new review of the final diff. All P0 and P1 findings must be closed. P2 and P3 findings must be fixed or explicitly accepted with a reason in the Pull Request. The primary agent posts the final review disposition and remains accountable for the merge decision.

This evidence-based approval does not require a second GitHub account and must not be represented as a fabricated GitHub `APPROVED` review. GitHub branch protection enforces required checks, linear history and resolved conversations; the Pull Request records the subagent review evidence.

- Frontend: format, lint, typecheck, unit tests, Storybook build, production build and relevant Playwright flows.
- Backend: format, lint, typecheck, unit/integration tests, migration checks and contract tests.
- Contracts: OpenAPI lint, JSON Schema compilation, compatibility review and consumer tests.
- Providers and media: deterministic fakes in ordinary CI; real-provider smoke tests for adapter changes and milestone golden projects.
- Documents: link validation, naming-policy checks and archive integrity checks.

A task is done only after acceptance criteria pass, implementation and canonical documents agree, the independent subagent review is approved, the Pull Request is merged, the Issue is closed and the branch is removed. A milestone additionally requires a real, demonstrable user outcome.

## 10. Local cleanliness and safety

- Keep uploads, model responses, media intermediates, logs, caches, local databases and temporary exports outside the repository.
- Use the operating-system temporary directory or configured object storage for generated artifacts.
- Parallel worktrees live outside the repository and are removed after merge.
- Keep only the current explicitly required external deliverable in `deliverables/`; replace it instead of accumulating dated archives.
- Never commit secrets, personal data, licensed textbook source files or raw sensitive model responses.
- Preserve unrelated user changes. Do not use destructive Git or filesystem commands to solve a scoped task.

Detailed placement rules are in `docs/governance/DOCUMENT_POLICY.md`; current delivery gates are in `docs/governance/DELIVERY_ROADMAP.md`.
