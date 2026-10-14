# Settings repairs: implementation and verification

All prioritized P1/P2 improvements from the historical `settings-e2e-audit.md` are implemented. The final 144-setting matrix contains no failures or blocked cells in any of the six measured modes. Each pass establishes its cited scenario; runtime consumption, provider transport and persistence evidence remain explicitly distinguished.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Complete Python suite | 721 passed | [JUnit](audit-results/settings-repair/python-junit.xml) |
| Frontend draft/revision regressions | 5 passed | `web/tests/settingsDraft.spec.ts` |
| Real-backend web development + built assets | 16 scenarios passed | [Playwright results](audit-results/settings-repair/browser-playwright.json) |
| Source Python HTTP backend | 125 observations passed; 5 controlled stage calls | [Source results](audit-results/settings-repair/source-results.json) |
| Fresh frozen sidecar HTTP backend | 125 observations passed; 5 controlled stage calls | [Frozen results](audit-results/settings-repair/frozen-results.json) |
| Actual Tauri development WebView2 | 123 observations; 140 distinct setting/action IDs | [Native development](audit-results/settings-repair/native-dev-cdp-results.json) |
| Actual Tauri packaged WebView2 | 123 observations; 140 distinct setting/action IDs | [Native packaged](audit-results/settings-repair/native-release-cdp-results.json) |
| Rust compatibility/lifecycle tests | 6 passed | `cargo test --offline` in the isolated build tree |
| Packaged relaunch, seeding and directory fallback | Passed | [Lifecycle evidence](audit-results/settings-repair/native-release-lifecycle.json) |
| Compatible source-backend reuse and visible mode/owner/storage context | Passed in the actual packaged WebView | [Reuse evidence](audit-results/settings-repair/native-backend-reuse.json) |

The aggregate generation-settings container receives separate coverage from its individually exercised children, explaining the distinction between 140 directly identified native setting/action IDs and 141 applicable matrix rows.

| Mode | Pass | Not applicable | Fail / blocked |
|---|---:|---:|---:|
| Source API | 139 | 5 | 0 / 0 |
| Frozen API | 139 | 5 | 0 / 0 |
| Web development | 142 | 2 | 0 / 0 |
| Web built | 142 | 2 | 0 / 0 |
| Native development | 141 | 3 | 0 / 0 |
| Native packaged | 141 | 3 | 0 / 0 |

See the [setting-by-mode matrix](audit-results/settings-repair/setting-mode-matrix.csv), [current inventory](audit-results/settings-repair/setting-inventory.csv), and [summary](audit-results/settings-repair/matrix-summary.json). Non-applicable cells concern UI-only actions at the API layer, fields without independent editable controls, and excluded external file-manager opening. Historical audit evidence remains unchanged.

## Finding closure

| Historical finding | Implemented behavior | Main source |
|---|---|---|
| B01, B07: invalid project values and Boolean coercion | Complete candidates validate before writes; JSON types are strict; unknown/read-only fields and invalid ranges return sanitized `422` errors. Corrupt files produce a clear error instead of silently resetting the configuration. | `models/config.py`, `cli/web_server.py`, `storage/repository.py` |
| B02: invalid global values | Allowlisted values receive semantic validation, including finite numeric bounds, supported Boolean tokens, cadence, thinking controls and custom endpoint syntax. | `utils/env.py` |
| B03: displayed review/quota values differ from runtime | Shared resolvers apply constructor overrides where supported, then project overrides, captured environment and built-ins. Existing concrete saved values stay overrides. | `models/config.py`, `batch/runner.py` |
| B04, B08: inconsistent inheritance and reset | Review/quota/reconciliation defaults are nullable; reset restores inheritance. Model reset also clears legacy Interactions controls. | `models/config.py`, `SettingsView.tsx` |
| B05: project dotenv pollution | Immutable mappings replace application dotenv mutation and flow through agents, providers, RAG, procedural refinement and scraper subprocesses. Project A/B values remain isolated. | `utils/env.py`, runtime consumers |
| B09: ineffective scene filtering | Resolved filtering gates drafter, critic and polisher rosters and related RAG queries; extractor filtering remains independent. | `graph/workflow.py`, `agents/` |
| B10: ineffective cross-folder memory | Project configuration is authoritative for rolling retrieval and coherently mirrors the compatibility Bible field. | `graph/workflow.py`, `storage/repository.py` |
| B11: overlap zero ignored | Explicit zero is preserved and configured overlap drives drafting, polishing and subdivision context tails. | `batch/runner.py`, `agents/drafter.py`, `agents/polisher.py` |
| B12, B13: partial persistence | Global changes use one strict atomic replacement. Config/Bible metadata uses a shared reentrant process/thread lock and recoverable transaction journal with a durable committed marker. | `utils/env.py`, `storage/repository.py`, `storage/settings_store.py` |
| B14: stale full-form overwrite | Mandatory revision preconditions and dirty-field saves reject stale requests with `412`. Refreshes retain dirty drafts and their original revision; explicit reload is required. | `cli/web_server.py`, `dashboardApi.ts`, `settingsDraft.ts`, `SettingsView.tsx` |
| B15: ignored procedural fields | All five project controls and their existing global defaults are exposed, validated, persisted and consumed. | Models, API, settings UI and runner |
| B16: creation ignores language defaults | Omitted creation languages inherit effective globals; explicit choices win. All six creation controls were exercised through UI, API, disk and reload in browser and native modes. | `cli/web_server.py`, `NewProjectModal.tsx` |
| Inherited false displayed as true | Effective values render separately from raw inheritance state. | `SettingsView.tsx` |
| Blank chunk fields save 85/70 | Display, blur and keyboard save use shared 800/400 defaults. | `settingsDraft.ts`, `SettingsView.tsx` |
| Global save leaves project values stale | Effective project values refresh without discarding drafts or silently advancing a dirty revision. Responses from obsolete project requests are ignored. | `SettingsView.tsx` |
| Preset omits scraper | Presets and environment loading apply all six role routes. | `SettingsView.tsx`, `cli/web_server.py` |
| Empty registry blocks globals | Invalid fallback projects no longer start chapter readiness requests; globals remain available without Skip. | `cli/web_server.py`, frontend startup integration |
| Unnamed switches / unassociated labels | Settings switches have names and controls have associated labels, including project-creation controls. | Settings and creation components |
| B17: transport capability unclear | The UI explains that retained budget applies only to supported non-Interactions transport. No unsupported Interactions budget field was invented. | Generation settings editor |
| Backend reuse lacks visible context | Compatible sharing is retained; actual backend mode, owner PID, environment file and registry location are displayed and verified. | `/api/desktop-info`, settings UI |

Independent review also closed lower-layer credential redaction, secret-dependent interpolation, invalid inherited-reset persistence, desktop readiness with malformed dotenv, explicit relative project-directory precedence, malformed interpolation fragments, refresh conflict bypass, and a development-mode React updater replay race. Runnable regressions accompany the relevant fixes.

## Compatibility and practical limits

- Version manifests, lockfiles and runtime version are synchronized to **0.5.3**. Tracked `web/dist` was rebuilt so normal production/source-desktop serving uses the new revision-aware UI. Older direct settings clients must GET a revision and send the quoted `If-Match` token. See [settings API and recovery guide](docs/settings.md).
- Explicit process variables continue to override saved file values. Global saves do not mutate `os.environ`; the UI shows effective origins. Existing valid concrete project overrides are preserved, and no migration guesses historical intent.
- Jobs capture controls at construction. Subsequent saves affect later jobs. Config-owned Bible metadata and conditional Auto-language updates protect newer user settings from memory workers.
- Native verification used actual Tauri WebView2 through Playwright CDP, never computer-use tools. Port 15474 ran sequentially; only verified audit processes and fixtures were written or stopped.
- Provider traffic was local and controlled. Source spies cover Google/Interactions payload decisions; the frozen transport exercises a local OpenAI-compatible stub. No commercial-provider compatibility or live-API-cost claim is made.
- Update checks exercised controlled error handling. Native fixtures used a loopback no-update feed and a loopback proxy that refused external tunnels; production updater endpoints and TLS configuration were unchanged. Update download/installation and external file-manager opening were excluded. The local-feed configuration follows the [official Tauri updater documentation](https://tauri.app/plugin/updater/).
- Directory fallback used owned regular files to block install-directory creation. This exercises filesystem failure, not Windows ACL denial. Read-only saves and crash/recovery failures have separate regression evidence.
- Application locks coordinate cooperating writers. Unexpected external changes during recovery retain the journal and block recovery. Malformed dotenv syntax requires manual correction of the selected file; safe global diagnostics remain available.
- Audit executables use the separate identifier `com.nousetsu.settingsrepair`. [Provenance](audit-results/settings-repair/provenance.json) records source snapshots and fresh artifacts; older installed executables were not replaced or certified. All audit helpers were stopped and preserved audit settings restored.

The complete plan is recorded in [settings-repairs-plan.md](settings-repairs-plan.md). This delivery is local only; no push, publication, updater installation or external messaging was performed.
