# Settings persistence and Tech defaults

Approved 2026-10-23.

- T1 depends_on []: Reproduce saves using isolated projects and fresh disk reads.
- T2 depends_on [T1]: Fix confirmed persistence and validation defects.
- T3 depends_on []: Align code defaults and .env.example with Tech.
- T4 depends_on [T2]: Verify API, terminal and frontend saves.
- T5 depends_on [T3]: Verify defaults and precedence.
- T6 depends_on [T4,T5]: Full tests, frontend build and settings documentation.

Preserve active .env, saved overrides, project identities, paths and timestamps. Retain nullable inheritance and existing API/transaction contracts.

## Implemented baseline

Japanese to Thai; primary/critic/chronicler/scraper `gemini-3.5-flash-lite`; fallback/extractor/drafter/polisher `gemini-3.1-flash-lite`. Translation temperature 0.1, scraper 1.0, thinking high, no fixed thinking budget. Rate limits 250000 TPM and 30 RPM; 3 review loops and quality 9.5; RAG disabled.

## Findings

The shared API/storage save path persists changes in isolated two-project tests and both source/built browser checks. The terminal dialog silently discarded invalid numeric edits or clamped review loops, then displayed success. Numeric edits are now validated and failures retain the dialog and draft. New-project model inputs start blank to inherit machine and per-role routes.

## Verification

Source and built browser save/reset checks: 2 passed. Frontend settings draft tests: 6 passed. Production TypeScript/Vite build succeeded. Full Python suite: 775 passed (one existing deprecation warning), after updating obsolete baseline fixtures and installing already-declared optional desktop dependencies.
