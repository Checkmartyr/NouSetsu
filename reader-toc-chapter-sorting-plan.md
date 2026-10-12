# Plan: Reader table of contents and chapter sorting

**Generated:** 2026-10-12
**State:** Approved 2026-10-12; implementation complete and verification passed.

## Confirmed requirements

- Add a table of contents (ToC) to the Reader page, with **50 chapters per page**.
- Add chapter sorting in both Studio and Reader: chapter number ascending/descending and title ascending/descending.
- Reader Previous/Next Chapter must keep **story order by volume and chapter number**, independently of the display sort.

## Overview and UI contract

Reader will gain a Contents toggle and a collapsible chapter panel. On desktop the panel sits beside the reading column; on narrow screens it overlays the body and closes after chapter selection, with an explicit close button, Escape support, initial focus, focus containment/background inertness while open, and focus return. Prefer native dialog behavior for the mobile modal if practical, without a modal library. Retain the existing accessible chapter dropdown as a quick selector and to preserve existing navigation tests. Its options use the same display order as the ToC.

The ToC shows chapter number, title (filename fallback for an empty title), volume/root label, translation availability, and saved/current chapter indicators. Include untranslated chapters so every chapter remains reachable; selecting one uses the existing untranslated message. Use the existing Pagination component with a fixed pageSize of 50 and no page-size selector. Page changes browse the ToC only: they never change the chapter, URL, bookmark, or reading scroll position. No chapter-text pagination or Studio pagination is included.

Use native labeled selects with the same four sort options in both tabs. Default to chapter number ascending. Persist the chosen sort separately per project and workspace through useSessionState, matching existing filter persistence; validate restored string values against the four supported options. Studio retains its current natural volume order (root first); sort chapters inside each volume accordion, and sort the flat list when a single volume is selected. Reader's ToC/dropdown sort across the full project roster, with visible volume labels and deterministic ties.

Sorting or opening the ToC reveals the page containing the current chapter. Chapter changes through dropdown, Previous/Next, bookmark resume, URL, or history likewise reveal its page. Manual page browsing must remain possible without an effect immediately snapping back. Closing/reopening reveals the current chapter; do not persist the page number. Clamp the page used for both the slice and Pagination when the roster shrinks. A project switch resets transient page/open state and restores only that project's sort.

Chapter identity remains the exact pair `(folder || null, chapter_num)`, including root versus named volumes. Sort changes preserve that pair and current content. Story navigation uses a separate canonical array: root first, volume names in natural ascending order, then numeric chapter number ascending. Neither display sorting nor pagination changes translation execution order or export order.

## Source-grounded findings

- `web/src/components/ReaderView.tsx` fetches the complete roster, selects by exact volume/number, guards stale content responses, and handles routed selection and bookmarks. Its dropdown and Previous/Next currently share the unsorted roster.
- `web/src/components/StudioView.tsx` filters by search/status/volume, groups results into natural-order volume accordions, and refreshes chapter data after upload and translation actions.
- `web/src/components/Pagination.tsx` already supports first/previous/numbered/next/last controls, compact mobile presentation, range counts, and fixed-size usage by omitting onPageSizeChange. It hides itself for zero items; the ToC must supply an empty state.
- `web/src/services/navigation.ts` provides project/workspace session display state and routed chapter navigation. Its generic restoration checks primitive type, not enum membership: validate sort values at the consumer/helper boundary.
- `web/src/types/dashboard.ts` defines ChapterItem with chapter_num, title, file_name, folder, is_completed, and translated_exists. No timestamp or new backend field is needed.
- `web/e2e/helpers/mockBackend.ts` already blocks real backend access. Existing Reader bookmark/routing tests rely on the `Select chapter to read` combobox.
- `web/dist/` is tracked. The final implementation must regenerate the shipped bundle.

## Prerequisites and documentation

Use the installed React 19, TypeScript, Vite, Lucide icons, and Playwright stack. No new package, server-side pagination, API change, or Python change is required.

Context7 is unavailable in this session; the required documentation lookup used primary web sources instead:

- [React: updating arrays in state](https://react.dev/learn/updating-arrays-in-state): copy before sorting to preserve state arrays.
- [React: rendering lists](https://react.dev/learn/rendering-lists): use stable chapter identity keys across reorders.
- [React: useMemo](https://react.dev/reference/react/useMemo): derive sorted arrays with complete dependencies rather than duplicating chapter state.
- [Playwright: mocking APIs](https://playwright.dev/docs/mock): use isolated route fixtures for deterministic browser checks.

## Dependency graph

```text
T1 shared ordering ──┬── T2 Studio ──┐
                    └── T3 Reader ──┼── T5 browser verification ── T6 delivery
T4 fixture preparation ─────────────┘
```

## Tasks

### T1: Shared chapter ordering contract

- **id:** T1
- **depends_on:** []
- **location:** `web/src/utils/chapterOrdering.ts` (new); consume `web/src/types/dashboard.ts`.
- **description:** Define the four typed sort values and labels, safe sort-value normalization, a non-mutating display sort, and a canonical story sort. Use copy-then-sort rather than Array.toSorted because web/tsconfig.json targets ES2020. Compare chapter numbers numerically; compare titles case-insensitively with natural numeric collation using explicit deterministic tie breakers. Empty titles fall back to file_name, then chapter number. Display ties use natural folder order (root first), chapter number, and filename. Canonical story sorting compares folder before chapter number. Keep this a small shared utility, without a generic table framework or new global store.
- **validation:** T5's deliberately shuffled fixture proves numeric order for 1/2/10, title directions, root/duplicate-number identity, tie stability, unsupported stored sort fallback, and unchanged story navigation under every display sort. Neither sorting function mutates its input.
- **status:** Completed
- **log:** Immutable natural number/title sorting, safe restored values, and separate canonical story order; frozen-input and browser order checks pass.
- **files edited/created:** web/src/utils/chapterOrdering.ts

### T2: Studio sorting controls and list integration

- **id:** T2
- **depends_on:** [T1]
- **location:** `web/src/components/StudioView.tsx`.
- **description:** Add a labeled chapter-sort select beside the existing sidebar filters. Restore/persist sort through useSessionState. Derive a display-sorted array from filteredChapters for rendering/grouping; keep root/volume accordion ordering and existing collapse state. Preserve selected chapter/content on sorting and preserve existing route precedence over restored filters. Keep selection-repair effects on filter/source arrays rather than display-sorted arrays, and do not mark a sort change as userChangedFilters. Retain the existing behavior where explicit user filter edits can select the first remaining row when they exclude the active chapter. Refresh/upload and status updates recompute ordering without resetting the user's choice. Sorting controls affect display only and never enter translation payloads.
- **validation:** All four sorts work in flat and grouped displays alongside search/status/volume filters; sort changes preserve the active chapter even when restored filters hide it; explicit filter edits retain existing selection behavior; same-number chapters in different volumes select exact content; refresh and project switching restore the correct sort; accordion Run and chapter translation actions preserve their current behavior.
- **status:** Completed
- **log:** Session-scoped sort controls and memoized display lists retain volume groups, filters, and exact chapter selection; repeated selection preserves content.
- **files edited/created:** web/src/components/StudioView.tsx

### T3: Reader ToC, fixed pagination, and sorting

- **id:** T3
- **depends_on:** [T1]
- **location:** `web/src/components/ReaderView.tsx`; reuse `web/src/components/Pagination.tsx` without changing its existing public behavior.
- **description:** Add the Contents toggle and accessible responsive panel described above. Derive a display-sorted roster and a separate canonical story roster. Use display order for the ToC and existing dropdown; use canonical order for currentIndex, Previous/Next, and story-position count in header/footer. Add the sort select inside the ToC and connect it to per-project Reader session state. Render only the current 50-row slice; wire existing selectChapter for each row. Synchronize page only on the explicit events described in the UI contract, clamp after list changes, and keep route/default resolution and stale-response guards intact. Preserve themes, typography, Raw peek, bookmark save/resume, and autosave. Replace Raw peek's unconditional w-96 shrink-0 layout with a narrow-screen stacked/sized layout so opening Raw does not consume almost the entire 390px reading viewport; retain the desktop split pane. Handle no project, initial loading, no chapters, and unavailable translation with clear existing-style states.
- **validation:** 0/1/50/51/101-item rosters show correct boundaries and range counts; manual ToC page browsing does not navigate or overwrite a bookmark; sorting preserves current chapter; deep-linked/resumed chapters beyond page 1 appear on the right page; story navigation crosses ToC pages and natural volume boundaries correctly. Desktop and mobile can open/close/select with keyboard or pointer; reading remains usable alongside Raw peek and all three themes.
- **status:** Completed
- **log:** 50-row Contents pagination, independent story navigation, responsive native dialog with focus wrapping, and mobile Raw layout verified.
- **files edited/created:** web/src/components/ReaderView.tsx

### T4: Prepare isolated chapter fixtures

- **id:** T4
- **depends_on:** []
- **location:** `web/e2e/helpers/mockBackend.ts`.
- **description:** Add an optional typed chapter-roster override to mockBackend while preserving all existing default fixtures and counters. Provide a small returned setter or response override for roster/status changes so refresh, pagination shrink, and upload success can be checked. For custom rosters, derive folder responses from that data. Content mocks must resolve the supplied project/folder/number and allow translated/untranslated fixtures, rather than always reporting translated content. Mock/capture POST /api/translate/start payloads and the minimal /api/chapters/upload and /api/scraper/check responses needed to exercise local upload; an upload fixture can expose a predetermined updated roster without reproducing backend ingestion. Supply shuffled multi-volume data with repeated chapter numbers, numbers 1/2/10, title ties, Unicode titles, empty-title fallbacks, and enough chapters for pagination. Keep all API requests mocked and real projects untouched.
- **validation:** Existing default fixtures retain their exact behavior; the override represents an empty roster and boundary sizes and can change between refreshes; custom folders match custom chapter data; captured translation payloads contain the original selection/folder and no display-sort fields; content returned for duplicate numbers belongs to the requested folder; untranslated rows yield untranslated content. Unhandled API calls remain observable and blocked.
- **status:** Completed
- **log:** Typed custom/mutable rosters, translation/status/upload mocks, and payload capture preserve default regression fixtures.
- **files edited/created:** web/e2e/helpers/mockBackend.ts

### T5: Browser checks and focused regression verification

- **id:** T5
- **depends_on:** [T2, T3, T4]
- **location:** `web/e2e/reader-toc-sorting.spec.ts` (new); `web/e2e/studio-chapter-sorting.spec.ts` (new); existing `reader-bookmark.spec.ts`, `routing.spec.ts`, and `desktop-routing.spec.ts`.
- **description:** Add deterministic behavior tests for the acceptance criteria in T1-T3 using T4 fixtures. Scope chapter-row assertions to the ToC/Studio list; distinguish ToC page buttons from chapter-navigation buttons. Verify sort persistence across tab return/reload and isolation across projects/workspaces. Seed corrupt/unsupported sort snapshots. Check route/history and bookmark resumes beyond the first page, delayed older content responses, exact root/volume identity, untranslated/empty states, updated/shrunk rosters, Studio refresh/local upload, unchanged translation payloads, and mobile initial focus/Tab containment/Escape/focus return. Verify mobile reading remains visible with Raw open. Use explicit assertions rather than conditional passes or fixed sleeps.
- **validation:** Run the new suites on desktop-hd and mobile and run Reader bookmark/routing/desktop-routing regressions. Every new test uses mockBackend; assert no unexpected API requests. Pagination tests prove the exact 50-row cap and short last page, including 50-to-51 boundaries. Check all sort modes leave Previous/Next in canonical story order.
- **status:** Completed
- **log:** Final source run: 60 passed, 4 expected viewport-specific skips; final production run: 54 passed, 4 equivalent skips. Bookmarks, history, volume collisions, pagination boundaries, filters, uploads, and keyboard focus verified.
- **files edited/created:** web/e2e/reader-toc-sorting.spec.ts; web/e2e/studio-chapter-sorting.spec.ts

### T6: Documentation, production assets, and delivery

- **id:** T6
- **depends_on:** [T5]
- **location:** `docs/web_desktop_guide.md`; `web/playwright.bundle.config.ts`; `web/dist/`; this plan's completion records.
- **description:** Document ToC usage, fixed 50-chapter pages, the four sorts, and independent story navigation. Include the new feature suites in the existing bundle testMatch and add a mobile project (390 x 844 viewport); the bundle configuration currently contains only desktop-hd. Build frontend assets, run the feature suites and existing routed-navigation checks against the production bundle on desktop and mobile, and visually inspect those states. Update task records with actual verification evidence. Stage the completed task files, create a conventional commit, and push the active tracking branch per repository instructions after checks pass.
- **validation:** Production build passes TypeScript and Vite checks; focused source and bundle browser suites pass; no clipped controls or unreadable states at 390px and desktop widths; shipped dist contains the feature; documentation matches behavior; review the final diff and verify commit/push success. No live LLM or real project calls are made.
- **status:** Completed
- **log:** Guide updated, tracked production bundle regenerated, TypeScript/Vite build and Git whitespace checks passed; desktop/mobile screenshots visually inspected. Conventional commit and push follow verification.
- **files edited/created:** docs/web_desktop_guide.md; web/playwright.bundle.config.ts; web/dist/; reader-toc-chapter-sorting-plan.md

## Parallel execution groups

| Wave | Tasks | Start condition / file ownership |
| --- | --- | --- |
| 1 | T1, T4 | After user approves implementation; separate utility and fixture files |
| 2 | T2, T3 | T1 complete; each agent owns one view file |
| 3 | T5 | T2, T3, T4 complete; one verification owner for both feature suites |
| 4 | T6 | T5 passes; one integration owner builds, documents, and delivers |

Do not edit shared files concurrently. A root/integration agent handles shared fixes and final build artifacts; build only after view changes have settled.

## Testing commands

Run from `web/` using the existing JavaScript tooling; repository Python commands, if needed, use uv. No backend changes require a Python suite for this feature.

```powershell
npx playwright test e2e/reader-toc-sorting.spec.ts e2e/studio-chapter-sorting.spec.ts --project=desktop-hd --project=mobile
npx playwright test e2e/reader-bookmark.spec.ts e2e/routing.spec.ts e2e/desktop-routing.spec.ts --project=desktop-hd --project=mobile
npm run build
npx playwright test --config playwright.bundle.config.ts
```

The production-specific updater configuration currently selects only updater tests; use the bundle configuration to verify this feature's built assets.

## Risks and mitigations

- **Display order accidentally changes story navigation:** distinct derived arrays, verified with title/descending sorts and shuffled input.
- **Volume chapter numbers collide:** exact folder/number selection and stable keys; include root and several volume copies in fixtures.
- **Pagination snaps back while browsing:** reveal active chapter only for chapter identity/sort/open events; do not depend on current page or a fresh roster array reference in an unconditional reveal effect.
- **Invalid restored state or roster shrink:** whitelist sort values, clamp page used for both slicing and controls, and reset transient state on project change.
- **ToC crowds mobile or Raw peek:** bounded desktop panel and dismissible mobile overlay; visual checks include open Raw pane and themes.
- **Client-side limits:** paginate rendered rows, retaining one full-roster fetch. This satisfies the requested navigation scope; avoid fetching chapter contents merely to populate titles.
- **Stale packaged UI:** regenerate tracked dist and test the bundle after implementation.

## Planning verification

This artifact records the user's three decisions and the current source structure. All implementation tasks are complete. The required independent subagent review found the dependency graph sound; its actionable corrections are incorporated: existing Studio filter selection behavior, mutable and complete mocked fixtures, a production mobile project, responsive Raw peek, and accessible mobile modal focus handling. Planning validation checks task dependency completeness, current file references, and Git whitespace; T5-T6 build and browser verification passed (60 source checks and 54 production checks, with four expected viewport-specific skips in each run). The skips are the mobile-only focus test on desktop and three existing project-selector cases on mobile.
