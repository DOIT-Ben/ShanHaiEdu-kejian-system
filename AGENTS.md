# ShanHaiEdu Repository Constitution

This file is the mandatory operating agreement for every human developer, vendor and coding agent working in this repository. It describes how work is performed. Product behavior belongs in `docs/product/`, `docs/workflows/` and `contracts/`.

## 1. Sources of truth

Use each source for one purpose only:

1. `README.md`: stable project introduction and start commands.
2. `AGENTS.md`: stable repository-wide rules.
3. `docs/governance/项目记忆与接手索引.md`: stable fact routing, verification entry points and recurring takeover pitfalls only.
4. `CURRENT_STATUS.md`: current milestone, active work and next gate only.
5. GitHub Issues: task scope, acceptance criteria, decisions and task status.
6. GitHub Pull Requests: changed code, verification evidence and handoff.
7. `docs/product/` and `docs/workflows/`: current product intent and business semantics.
8. `contracts/`: current machine-readable boundaries.
9. Current code, migrations and tests: implemented runtime behavior.
10. Git history: superseded versions and historical context.

当产品意图、合同与实现不一致时，先确认是否存在“当前 Issue”。一个 Issue 只有同时满足以下条件，才可作为当前任务的变更依据：

- Issue 处于开放状态，并由当前任务的唯一负责人持有。
- Issue 已关联当前任务分支或 Pull Request。
- Issue 明确写出目标、范围、非范围、验收标准和已经确认的决定。
- 当前冲突确实落在该 Issue 的显式范围内。

不存在符合条件的当前 Issue 时，必须停止并新建或更新 Issue；不得静默选择一种行为、同时支持互相矛盾的口径，或用补充说明代替正式变更。

存在符合条件的当前 Issue 时，它只授权其范围、验收标准和决定明确描述的变更。实施 Pull Request 必须在同一变更中同步受影响的现行文档、合同和测试，使仓库只保留一套当前口径。

如果变更涉及持久架构或产品行为、已发布 Release、既有项目绑定或跨模块合同，当前 Issue 本身必须是 Decision Issue，或明确链接已经批准的 Decision Issue；否则仍须停止并补齐决策。普通实现 Issue 不得越过这些边界。

上述优先级不得覆盖平台或安全规则、用户当前明确指令，也不得把无关或历史 Issue 当作当前需求。当前 Issue 未明确变更的事实继续遵循既有产品设计、合同和实现边界。

## 2. Required takeover sequence

Before changing files:

1. Read `README.md`, this file, `docs/governance/项目记忆与接手索引.md` and `CURRENT_STATUS.md`.
2. Run `git fetch origin --prune` and inspect branch, HEAD, upstream and dirty files.
3. Read the assigned Issue and linked Pull Request.
4. Read only the module documents, contracts, code and tests relevant to the task.
5. State the task goal, completed work, blockers and next action before continuing.

Do not begin by reading all Git history, all documents or prior chat transcripts. Do not modify files when the Issue, Pull Request and current status materially disagree.

## 3. Task contract

- Every change starts from a GitHub Issue with goal, scope, non-scope, acceptance criteria, risks, dependencies and tests.
- One Issue has one current owner, one primary task branch and one primary Pull Request.
- Before a substantive Pull Request is merged, the primary agent assigns one read-only subagent that did not implement the change to review the complete base-to-head diff. This starts one review engagement: if findings are raised, the same reviewer verifies the fixes and rebinds the final head instead of starting repeated whole-diff reviews. Use a replacement reviewer only when the original reviewer is unavailable or the scope materially changes, and record the reason in the Pull Request. The subagent report is the repository's engineering approval evidence.
- Large outcomes use a parent Issue and independently acceptable child Issues.
- Task states are `ready`, `in-progress`, `blocked`, `review` and `done`.
- GitHub Issues and Pull Requests are the task and handoff truth. Do not add task journals to the repository.

See `docs/governance/TEAM_WORKFLOW.md` for the full lifecycle.

### 3.1 Vertical product delivery

Frontend and backend remain separate code ownership areas, but user-facing completion is never assessed separately.

Every current product slice must have one parent Issue that contains a page–API–fact–acceptance matrix. Before implementation starts, that matrix must identify:

- the exact teacher action and route;
- the active OpenAPI `operationId` used by the page;
- the formal PostgreSQL, object-storage or immutable runtime fact read or written;
- loading, empty, error, conflict, permission and refresh-recovery behavior;
- the backend integration test and real-API Playwright flow that prove completion.

A backend endpoint is not a finished product capability because its unit tests, CLI or deterministic Fake pass. A frontend page is not a finished capability because its Storybook, MSW or visual tests pass. The slice is done only when the production page consumes the active contract, the runtime persists the intended fact, refresh recovery succeeds and all mandatory checks pass.

For the current release, delivery order and concurrency are controlled by the latest approved Decision Issue and `docs/governance/DELIVERY_ROADMAP.md`. Long-term product documents and planned contracts do not authorize implementation by themselves.

Mandatory integration rules:

- Production session bootstrap, authorization and server-side CSRF validation are prerequisites for any browser write-flow milestone.
- Active OpenAPI, FastAPI runtime registration, generated TypeScript client and the current consumer must change together or through explicitly ordered blocking Issues.
- Planned OpenAPI never enters generated clients, MSW runtime handlers or availability claims.
- The owner of the parent slice is accountable for both implementation PRs and the final browser result, even when frontend and backend engineers are different people.
- Shared contracts, generated clients, authentication bootstrap, artifact approval and published content releases have a single active writer.
- A product slice cannot close while any required consumer is a placeholder, read-only shell, known-ID deep link or production-disabled action.
- New media or downstream slices cannot bypass an unfinished upstream release gate merely because fixtures or golden handbooks exist.
- Every current Pull Request must select exactly one `vertical-slice-required` or `vertical-slice-not-required` declaration. A Pull Request that changes production pages, API routers or active OpenAPI cannot opt out. A required slice must change one `contracts/delivery-slices/<issue>-<slice>.yaml` whose Issue matches the PR `Closes` declaration, and whose rows bind concrete registered page routes and navigation paths to active HTTP methods/paths, exact SQLAlchemy table classes, exact integration-test selectors and exact Playwright titles under `apps/web/e2e/real-api/`. The PR body unions must exactly match that manifest. `pending`, `N/A`, planned or unavailable routes, conceptual facts, service/DTO/Pydantic classes, skipped tests and intercepted or MSW browser flows fail the governance check. Real-API Playwright uses its dedicated configuration and CI workflow to start FastAPI, PostgreSQL and Redis, observe actual requests without interception and run every declared selector. Machine checks prove structural consistency and execution, while the independent reviewer remains responsible for the sufficiency of the business assertions.


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
- External memory may point to this repository and its project memory index, but must not replace live project facts or store task branches, commits, ports or Pull Request state.

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

Independent review is mandatory before a Pull Request becomes Ready or merges. The reviewer subagent reports findings first with file and line references, verifies the relevant commands, and records residual risk. The review evidence binds the exact base SHA and head SHA. Any push, rebase or other head change invalidates the approval; within the same review engagement, the same reviewer rechecks the changed delta and final base-to-head diff before rebinding the final head. All P0 and P1 findings must be closed. P2 and P3 findings must be fixed or explicitly accepted with a reason in the Pull Request. The primary agent posts the final review disposition and remains accountable for the merge decision.

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
Recurring collaboration failure mechanisms and their current prevention controls are in `docs/governance/协作机制复盘与防复发.md`.
Stable takeover routing and project-specific memory boundaries are in `docs/governance/项目记忆与接手索引.md`.
