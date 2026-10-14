# Settings Repairs Following the Prioritized Audit Findings

Approved execution plan, 2026-10-13. Fix all P1/P2 findings in settings-e2e-audit.md. Preserve existing valid concrete overrides; new/reset env-backed overrides inherit. Require revision preconditions, support procedural settings, no live providers or computer-use tools, local commit only.

## Contract
Validate complete candidate config before writes with strict JSON field types, bounded finite numbers and sanitized errors. Nullable review/quota/reconciliation inherit globals. Shared resolver must agree with runtime; preserve scraper routing exception. Corrupt configs raise visible errors, never silently default.

Resolve immutable environment snapshots: explicit process > project dotenv > selected machine dotenv > normal discovery CWD fallback > built-ins. Honor desktop path fallback, explicit env file and interpolation. Capture snapshots per job; no application load_env mutation. Expose saved/effective/origin without secrets.

GET revision/ETag; PUT requires If-Match (428 missing, 412 stale, 422 invalid, 500 I/O, 503 lock timeout). Dirty-field UI saves preserve drafts on conflict. Atomic dotenv whole-file replacement preserves unrelated keys/comments. Strict writer avoids readonly chmod/inplace fallback. Project reentrant crossprocess lock, five-second timeout, shared by all metadata writers. Fixed config/Bible transaction journal with beforeimages/hashes, durable commit marker, prepared rollback, external-edit protection. Merge current settings metadata into memory writes; conditional Auto language changes only while persisted value still equals initial value.

Fix scene filters, crossfolder flag, overlap zero/all tails, chunk800/400, inherited false rendering, legacy Interactions reset, scraper presets, effective refresh/async guards, all5 procedural controls+globals, language creation defaults, no-project global access, all labels and switches. Explain budget transport capability. Preserve backend reuse, display mode/storage.

## Tasks
| ID | depends_on | location | description | validation |
|---|---|---|---|---|
| T1 | [] | models/config, settings DTOs, web types | schemas/contracts/inheritance/revisions | strict type/bounds/alias/null/zero/legacy tests |
| T2 | [T1] | storage, dotenv persistence | locks/atomic revisions/journal/recovery | failures/concurrency/restart/readonly |
| T3 | [T2] | env/bootstrap/resolvers/factories | immutable snapshots | A/B/restart/interpolation/desktop/spies |
| T4 | [T3] | web_server endpoints/registry | typed API/revisions/creation/corrupt handling | HTTP/disk/resolution/redaction |
| T5 | [T1] | web/src | frontend repairs and client | UI contract/refresh/conflict/a11y |
| T6 | [T3] | runner/workflow/agents/RAG/scraper/TUI | runtime consumption/timing | prompt/chapter/next-job observations |
| T7 | [T4,T5,T6] | tests/tools/docs/build versions | desired regression conversions, client updates, 0.5.3 builds | required checks/fresh artifact hashes |
| T8 | [T7] | isolated audit-results/settings-repair | source/frozen/browser/native signoff | per-setting mode evidence; blocked cases prevent signoff |

T5 parallel after T1; storage/env changes sequential. Independently review implementation/evidence. Preserve historical evidence. Mock providers only; real backend browser tests; actual Tauri WebView2 via Playwright CDP. Native port15474 sequential, verify process ownership. Report settings-repairs-report.md, commit locally, no push/export without separate approval.

## Completion record

T1–T8 completed. Independent implementation review findings were addressed. Final evidence is in audit-results/settings-repair; settings-repairs-report.md records checks, coverage and practical limits. All applicable matrix cells pass. Local commit follows completed verification; no push or publication.
