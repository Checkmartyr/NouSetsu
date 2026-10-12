# Fix novel initialization and persistent web navigation

Approved 2026-10-12. Romanize URL-import title defaults; verify startup once per
tab session; restore workspace/project/chapter/trace through paths and history.

| Task | Dependencies | Location | Acceptance |
| --- | --- | --- | --- |
| T1 Title autofill | [] | NewProjectModal | Romanized/fallback title, manual edits and stale requests safe |
| T2 Session startup | [] | StartupLoadingScreen, serviceChecker | Single-flight full checks, lightweight refresh, recovery |
| T3 Path router | [] | navigation service | Typed URL codec, history, session snapshots |
| T4 Workspace integration | [T2,T3] | App, workspace components | Exact volume/chapter selection, serialized project switches |
| T5 Import tests | [T1] | new-project-url Playwright suite | Mocked imports and retries |
| T6 Navigation tests | [T4] | routing/startup suites, web-server tests | Refresh/history/races/deep links |
| T7 Verification/delivery | [T5,T6] | Build, regressions, docs | Green checks and commit/push |

No new dependencies, API contract changes, existing-project rename, or unfinished
form persistence. URL selection wins over per-workspace session snapshots,
reader bookmarks, then defaults. Root folder means omitted folder, matched exactly.

Implementation complete. Validation: production frontend build; 34 isolated
Python web-server/scraper tests; 22 title/startup browser checks; existing reader,
analytics and updater regressions; desktop/mobile routing and race tests; built
bundle routes and a simulated Tauri runtime. Mobile-only hidden project-selector
cases are covered on desktop. Native Tauri window interaction was unavailable.

Final review also preserved active-project snapshots on bare workspace URLs and
local trace uploads during navigation. Built assets and user guides are updated.
