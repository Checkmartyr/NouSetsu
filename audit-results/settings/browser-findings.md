# Settings browser audit

Audit date: 2026-10-12 (Asia/Bangkok). Product code was not changed.

Final execution: **14/14 Playwright cases passed**, with zero skipped,
unexpected, or flaky cases, in **125.015815 seconds**. Both modes completed
seven cases each. The diagnostic results contain **34 observations**: seven
passes and ten confirmed product failures per mode, with **no blocked harness
records**. The ten failures represent nine finding groups because the two
blank-chunk defaults are recorded separately. These failures were reproduced
equally in source/Vite and source/built modes.

## Method and evidence

`web/playwright.settings-audit.config.ts` starts a real Python backend on 5186,
Vite on 5187, and a second real Python backend serving built frontend assets on
5188. The latter receives `NOUSETSU_SETTINGS_AUDIT_DIST` pointing to the isolated
fresh build. Each backend has independent temporary registry, `.env`, logs,
projects A/B, Bible, and Japanese chapter fixtures. Product settings endpoints,
serialization, persistence, and GET resolution run unchanged. No browser request
interception or simulated Tauri runtime is used. Fixture-only routes supply
reset, sanitized disk evidence, and a localhost custom-provider `/models` stub.
Outbound provider connections are blocked. Keys are synthetic; evidence records
only hashes and configuration status.

Machine-readable observations and field coverage: `browser-results.json`.
Execution status: `browser-playwright.json`. Provenance and fixture paths:
`browser-dev-fixture.json` and `browser-built-fixture.json`. Screenshots:
`web-dev-project.png`, `web-dev-global.png`, `web-built-project.png`, and
`web-built-global.png`.

Successful browser scenarios validate **61 editable project field paths in each
mode** (including four generation controls for each of six roles) and **51
allowlisted non-secret environment keys plus five secret lifecycles in each
mode**. There are no missing editable-field paths in either successful scenario.
They check UI save, real PUT response, YAML/`.env` persistence, real GET, and
browser reload; project B isolation and Bible metadata synchronization are
checked directly. Translation/runtime consumption and process restart are
covered by the backend/native audit, not inferred from these browser passes.

## Confirmed findings

| Priority | Finding | Reproduction and observed result | Recommendation |
|---|---|---|---|
| P1 | A stale full-form save overwrites another form's saved fields | Open two project settings forms. In A, save title `Saved from form A`. In the still-open B form, change only genre to `romance` and save. Disk title becomes `Audit A`. | Send changed fields or reject stale writes with a revision token. |
| P1 | Global generation and numeric defaults lack semantic validation | Save shared temperature `3`, review loops `not-a-number`, and TPM `-1` from global UI. The real backend persists those strings. Project generation temperature `3` is correctly rejected with HTTP 400 and no disk write. | Apply common typed/range validation to project and global values before writing. |
| P2 | Keyboard save gives blank chunk fields unexpected defaults | Clear threshold and press Ctrl+S while focused: persisted value **85**. Clear chunk size and press Ctrl+S: persisted value **70**. Displayed/blur defaults are **800/400**. | Use a single schema-defined default for display, blur, and save paths. |
| P2 | Effective project model display stays stale after global save | Clear project overrides; visit globals and change `NOVEL_MODEL` to `mock-updated-global`, save, then return to Model Routing. Placeholder still says `mock-audit-shared`; fresh real GET says `mock-updated-global`. | Reload resolved project settings after successful global save. |
| P2 | Applying a model preset omits the scraper route | Apply `Current .env Defaults`. The backend preset includes `scraper_model=mock-audit-shared`; the UI saves all other preset models while scraper remains null. The separate `Load .env` action does populate scraper. | Include scraper in the preset application path and verify all preset fields. |
| P2 | Project controls have incomplete accessible labels | The All Project Settings form has **10 switches with no accessible name** and **29 labels without an associated control**. | Associate inputs/selects with IDs and `htmlFor`; give switches `aria-label` or `aria-labelledby`. |
| P2 | Empty registry stalls startup before global settings | With a genuinely empty temporary projects root and registry, startup requests chapters for uninitialized fallback CWD and receives HTTP 400. Global settings require `Skip & Continue`; after skipping they work. | Treat no-project startup as a supported state and skip project chapter readiness checks. |
| P2 | Inherited extractor filtering appears enabled while the resolver disables it | Keep project `filter_extractor_entities=null` and set global `NOVEL_FILTER_EXTRACTOR_ENTITIES=false`. UI switch is checked; the actual project resolver returns false. | Render the effective resolved value with a separate explicit inherit/override state. |
| P2 | Clear-all keeps a legacy Interactions override | Set legacy project `use_interactions_api=false`, global Interactions=true, then click Clear and save. Legacy false remains and all six roles continue resolving Interactions=false. | Clear legacy and role-specific generation overrides together. |

Relevant implementation: `SettingsView.tsx` `handleSave`, `handleApplyPreset`,
`handleSaveEnvironment`, and `ToggleSwitch`; `utils/env.py`
`save_env_settings`; `cli/web_server.py` `update_settings`.

## Additional verified behavior and limits

- Every synthetic API key is replaced, preserved by a blank input, replaced
  again, and explicitly cleared through the UI. Real environment GET responses
  never return any secret value. Password inputs are blank after reload.
- Custom provider catalog discovery uses the real backend and real localhost
  `/models` transport. Route prefix `custom:` persists correctly.
- Explicit project selection, switching A/B, unsaved-form exclusion from
  session storage, section deep links, reload, and Back navigation are checked.
- A 390px viewport has no document-level horizontal overflow. This is a focused
  layout check, not comprehensive accessibility certification.
- Diagnostics render the isolated log root. Update checks run the real backend
  with outbound networking blocked, return HTTP 502, and display the backend's
  error message. Installation and opening external log-folder windows are
  excluded.
- Source/built parity is represented by separate mode records; browser results
  provide no evidence about native Tauri or the frozen sidecar.
- Playwright passing means the audit harness completed. Product defects remain
  `fail` observations in `browser-results.json`; they are not accepted contracts.
- An early no-project fixture iteration still used the repository CWD, causing
  the normal resolver to read its existing `.novel` fallback. No host project
  settings were saved. The final fixture changes CWD to its temporary root;
  Playwright recreates its artifact output directory on each run, and final
  evidence contains only isolated fixtures.
