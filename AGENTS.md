# Repository Working Agreement

## Scope

This repository is the single active source for the ShanHaiEdu courseware workbench. The first product closure is primary-school mathematics. Preserve extension points, but do not expand product scope without an approved specification.

## Read order

1. `docs/START_HERE.md`
2. The applicable product or architecture document.
3. The current OpenAPI, workflow schema, tests, and code in `main`.

## Fixed decisions

- New frontend: React 19 + TypeScript + Vite. Do not revive or copy the legacy frontend.
- Backend baseline: migrate reusable FastAPI capabilities from `DOIT-Ben/shanhaiedu-v1.0.0`; do not rewrite without evidence.
- All model calls go through the backend model gateway.
- Preserve editable prompts, versioned outputs, approvals, assets, job history, and downstream references.
- Use one workflow state machine for manual, semi-automatic, and automatic modes.

## Change rules

- Work on focused branches and merge by Pull Request.
- Treat backend OpenAPI as the integration source of truth.
- Add Alembic migrations for schema changes.
- Version workflow definitions and Prompt templates; never mutate history in place.
- Never commit secrets, `.env`, generated user media, local databases, or sensitive Provider responses.
- Do not claim completion with mocks, placeholders, screenshots, or unverified generated files.

## Verification

- Frontend: lint, typecheck, unit tests, production build, and relevant Playwright flows.
- Backend: contract tests, targeted unit/integration tests, migration checks, and a real artifact smoke test when Provider or media behavior changes.
- Always report the exact commands run and any checks that could not run.
