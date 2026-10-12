# Settings E2E Audit and Improvement Review

Approved 2026-10-12. Audit and recommendations only; product behavior remains unchanged.

User steering on 2026-10-13: resume without computer use. Native validation completed with Playwright CDP connected to the actual isolated Tauri WebView2; historical UI evidence is preserved. Final audit outcome is documented failures and recommendations, with unexercised ancillary actions/creation inputs explicitly blocked rather than claimed passed.

## Coverage

Trace every default/project setting through UI, API validation, persistence, resolution and runtime consumption. Modes: source API, frozen sidecar API, Vite/source web, built/source web, actual Tauri development/source backend, actual packaged Tauri/frozen backend. Use isolated projects, registry, settings, synthetic credentials and mocked/local provider transports. Never mutate host projects or expose real credentials. Native checks require an isolated audit identifier and verified settings paths before writes.

## Tasks

| ID | Dependencies | Location | Description | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | [] | UI, environment utilities, ProjectConfig, runtime consumers | Inventory every exposed and schema-only setting with defaults, inheritance, aliases, consumer and timing | Complete setting inventory; supported modes and expected behavior recorded | Complete: 144 unique rows |
| T2 | [T1] | scripts/audit, temporary fixtures, src-tauri | Isolate projects A/B, registry/env/app-data; record source/artifact provenance; local provider stub and source spies | Verify paths, process ownership and offline routing before writes | Complete: fresh frontend, frozen sidecar, debug/release audit shells |
| T3 | [T2] | tests, source API, frozen API | Diagnose contracts, boundaries, precedence, reset, restart, disk/process consistency | Reproducible responses, persisted data and consumed values | Complete: source145 diagnostics/runtime cases, frozen102 observations |
| T4 | [T2] | web/e2e, Playwright configuration | Exercise every editable setting in Vite and built web with real API | Save/reload evidence; no interception of settings endpoints | Complete: final 14/14 passed, 125.016s; nine reproduced UI finding groups |
| T5 | [T2] | src-tauri, disposable builds | Actual Windows Tauri dev/release UI; startup seeding, paths, restart and backend ownership | Correct isolated storage/backend; native cases serialized on port 15474 | Complete editable-field coverage: 117 paths per native mode; restart/seed/filesystem fallback/reuse observed; ancillary unexercised checks recorded |
| T6 | [T3,T4,T5] | workflow, agents, scraper, RAG, storage | Compare displayed/persisted/resolved/consumed settings and active/subsequent job behavior | Explain discrepancies; controlled runtime evidence | Complete within mock-only scope: source timing/spies, frozen wire parameters, native UI-started outputs |
| T7 | [T1,T3,T4,T5,T6] | report, inventory, evidence | Findings, per-mode matrix, prioritized recommendations | Pass/fail/blocked/not-applicable for each setting; unresolved required gaps prevent full signoff | Complete: report/matrix, independent review, integrity tests; full suite630 passed; signoff fails due documented defects/coverage gaps |

## Validation

Valid edits and reload/restart for every editable setting; missing/empty/null/false/zero/invalid/boundary inputs; constructor/project/role/shared/default conflicts; A/B isolation; clean/inherited process restart; external changes; read-only and partial saves; config/Bible consistency; stale/concurrent saves; paths with spaces/non-ASCII; provider failures and secret exclusion. Source provider spies validate Google/Interactions request logic; frozen transport uses a local custom-provider stub. Live-provider acceptance is outside this audit.

Prioritize blank chunk 85/70 vs 800/400 defaults, review/quota env-before-project, reconciliation defaults masking env, project dotenv process pollution, assignment validation/coercion and ignored fields, and stale project effective values after global save. Settings-related updates/logs are read/error checks; no updater installation.

## Execution and delivery

T3/T4/T5 may run in parallel with independent fixtures. Standalone APIs use separate ports; native modes sequentially own port 15474, never terminate unrelated listeners. Use existing pytest/Playwright/computer-use capabilities and no new product dependencies. Deliver settings-e2e-audit.md, audit-results/settings inventory/matrix and sanitized evidence. Existing 25 focused tests are baseline, not native E2E proof. Commit and push the verified audit artifacts according to AGENTS.md; do not ship product fixes.
