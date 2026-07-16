# Repository Working Agreement

## Scope

This repository is the single active source for the ShanHaiEdu courseware platform. The first closure is primary-school mathematics. Do not introduce a competing specification, versioned documentation tree, or legacy frontend implementation.

## Required read order

1. `docs/START_HERE.md`
2. `docs/product/REQUIREMENTS_ANALYSIS.md`
3. `docs/product/PRODUCT_SPEC.md`
4. `docs/workflows/END_TO_END_WORKFLOW.md`
5. The applicable `docs/workflows/`, `docs/frontend/` or `docs/backend/` document
6. `contracts/`
7. Current code, migrations, generated OpenAPI and tests in `main`

## Fixed product decisions

- One project represents one small knowledge-point textbook input and contains multiple lesson units.
- Lesson plan is required; PPT and classroom-intro video are independent optional branches.
- The default lesson-plan definition has twelve sections but the renderer and database are schema-driven.
- Image, video and presentation studios are general platform capabilities, not project-mounted spaces.
- Projects export immutable creation packages; selected studio results are atomically saved back to project asset slots.
- Anchor selection cannot read textbook, knowledge point, lesson plan or PPT. Approved anchors are adapted to course knowledge only in later story nodes.
- Video order is master script, rough storyboard, visual master, image assets, fine storyboard, shot candidates, saved clips, audio and assembly.
- Each lesson defaults to a separately versioned three-category/nine-option introduction appendix. Video consumes only the selected option snapshot, never the full lesson plan.
- Final PPTX is hybrid and editable by default; essential text, formulas, data and labels are not baked into AI images.
- Manual, semi-automatic and automatic modes share one runtime.
- Prompts shown to users remain editable within the business layer; locked safety and output constraints are not editable.

## Engineering rules

- New frontend: React 19＋TypeScript＋Vite; do not copy the legacy frontend.
- Backend: modular FastAPI monolith＋workers first; split services only with measured need.
- PostgreSQL is the business truth. Redis is not a source of truth.
- All model calls go through the model gateway; Provider secrets never enter browser code, Git, logs or exports.
- Generate frontend types from backend OpenAPI. Do not duplicate DTOs or server state.
- Add Alembic migrations for every database schema change.
- Version content packages, workflow definitions, Prompt snapshots and artifact versions; never overwrite history.
- New UI capability extends registries and feature modules; do not add large node-type conditionals.

## Verification

- Frontend: lint, typecheck, unit tests, Storybook build, production build and relevant Playwright flows.
- Backend: contract tests, unit/integration tests, migration checks and real artifact smoke tests for Provider or media behavior.
- Documentation: JSON/YAML parsing, local-link validation, checksum verification and archive test.
- Always report exact commands and unresolved checks.
