# Settings persistence and resolution

The settings API validates a complete candidate configuration before saving. Project settings live in `.novel/config.yaml`; settings-owned Bible metadata is synchronized into `.novel/bible/bible.yaml`. Global defaults and credentials live in the selected machine dotenv file. Settings responses include saved values, effective values, and origins so a saved override can be distinguished from inheritance.

## Editing through HTTP

GET `/api/settings?project_path=<absolute-project-path>` and GET `/api/environment` return an opaque `revision` in JSON and the same token, quoted, in the `ETag` header. Send that exact ETag as `If-Match` when saving. Project PUT accepts only changed editable fields; `generation_settings`, when provided, replaces the complete role map. `{}` clears that map. The frontend preserves drafts after conflicts and offers an explicit reload.

For example, using a local backend and a URL-encoded project path:

```http
GET /api/settings?project_path=D%3A%5CBooks%5CExample HTTP/1.1
Host: 127.0.0.1:15474
```

The response supplies a real token such as `ETag: "<revision-from-get>"`. A save uses that returned token, not a guessed revision:

```http
PUT /api/settings?project_path=D%3A%5CBooks%5CExample HTTP/1.1
Host: 127.0.0.1:15474
Content-Type: application/json
If-Match: "<revision-from-get>"

{"max_review_loops":2,"chunk_overlap_lines":0}
```

For a global save, GET `/api/environment` first and use its ETag:

```http
PUT /api/environment HTTP/1.1
Host: 127.0.0.1:15474
Content-Type: application/json
If-Match: "<revision-from-environment-get>"

{"values":{"NOVEL_QUALITY_THRESHOLD":"9"},"api_keys":{},"clear_api_keys":[]}
```

Successful saves return a refreshed snapshot and revision. Missing `If-Match` returns `428`; a stale token returns `412`. Invalid types, unknown/read-only fields, and invalid ranges return `422`. Storage failures return `500`; an unavailable settings lock returns `503`. Validation messages omit submitted values and credentials. Existing direct API clients must fetch and send revisions; wildcard overwrite is unsupported.

Project Boolean requests use JSON `true`/`false`, not strings. Global dotenv values accept documented Boolean tokens (`true/false`, `1/0`, `yes/no`, `on/off`). Zero is valid for overlap, temperature, and thinking budget; quotas, chunk sizes, and learning intervals must be positive. Review loops are 1–5, quality threshold 5–10, RAG top-k 1–10, and temperature 0–2. Numbers must be finite.

## Inheritance and job timing

Valid existing concrete project values remain overrides, even when equal to an old default. New nullable settings and explicitly reset values inherit current global defaults. No migration guesses historical intent. Metadata such as the languages of an existing project remains concrete. Omitted creation languages use the current global defaults; explicit creation inputs win.

Where supported, constructor/CLI arguments precede project overrides, then the resolved environment, then built-in defaults. Scraper routing retains its existing exception: a role-specific environment route precedes the project shared route when there is no explicit project scraper route. Per-role generation overrides precede role environment values and shared defaults; the legacy project Interactions override remains supported and is cleared by the UI's model reset action.

Environment resolution creates an immutable snapshot: explicit process environment → project `.env` → selected machine dotenv → applicable normal-discovery fallback → built-ins. `NOUSETSU_ENV_FILE` selects the machine file; project overlays still apply. Application startup and provider factories do not inject dotenv values into the process environment. The legacy `load_env` helper remains available for compatibility but is not the application resolution path.

An explicit process variable remains authoritative after saving the same key in the file. The UI displays the effective origin and warns about external overrides. Clear/change the launcher environment and restart the backend to change those values. A blank default removes its file override. Blank credential input preserves the existing file credential; `clear_api_keys` explicitly removes it. Clearing the file does not remove a credential supplied by the launcher.

Each job captures its environment and controls when its runner is constructed. Settings changes affect subsequent jobs. Current jobs retain captured model routes and generation controls. Automatic language detection only writes its result if the persisted language still matches the job's original Auto setting, protecting a newer user choice.

Procedural learning controls are supported in both global defaults and project overrides. Thinking budget is retained when switching transport, but only supported non-Interactions transport receives it; the Interactions API has no supported budget mapping.

## Workspace roots and volumes

Workspace Directory Paths accepts one source root and one translated output root. Chapters directly in the source root use the output root. Chapter folders at any depth beneath the source root are discovered automatically and retain their structure in the output root: `raw_chapters/Volume_01/0001.txt` produces `translated_chapters/Volume_01/0001.md`. Discovery uses natural volume order, skips hidden folders and the configured output tree, and keeps complete folder paths so repeated chapter numbers and leaf-folder names stay separate.

The settings page lists discovered source/output pairs and chapter counts from the saved configuration. Roots can be project-relative or absolute paths. Save root changes to refresh that list. Existing sibling volume folders retain their language-suffixed output convention; changing roots does not move existing chapter files.

## Failed writes and recovery

Global saves prepare a complete dotenv candidate and replace the file atomically. They preserve comments and unrelated keys. Strict settings writes do not clear read-only protection or fall back to in-place copying.

Project saves use a shared process/thread lock and a transaction journal at `.novel/settings-transaction.json`. Prepared transactions restore verified before-images after interruption. A durable committed marker prevents a completed save from being rolled back. Settings reads recover interrupted transactions before returning data. Memory saves preserve current configuration-owned metadata; explicit Bible metadata edits use the same transaction path.

If recovery finds an unrelated external edit or cannot restore a file, it retains the journal and reports: `Project settings recovery failed; saved files were retained for inspection`. Preserve the journal and both files for investigation; do not delete it to force a project open. Locks coordinate application writers, not arbitrary external editors. Avoid editing files while an application save is in progress. These guarantees cover the audited filesystem/process failures; they are not a universal guarantee against hardware or filesystem corruption.

A corrupt saved configuration is reported rather than replaced with project defaults. Healthy projects and global settings remain accessible. Malformed dotenv syntax must be fixed in the selected file manually: preserve a backup, correct quoting/key syntax or cyclic interpolation, and reload settings. The UI can show safe diagnostics when parsing fails but cannot reliably reconstruct malformed lines through a form save. `${VAR}` and `${VAR:-default}` interpolation uses the assembled snapshot without mutating the process.

## Desktop backend reuse and verification

Version `0.5.3` settings clients and backends use the revision contract together. Desktop startup retains compatible backend reuse and displays the backend mode and storage context. Reusing a compatible source backend means the desktop UI edits that backend's files; it does not prove a frozen sidecar was used. Check the displayed context when comparing modes.

The repair audit uses isolated fixtures and local mock providers. Source spies verify Google/Interactions payload decisions; frozen-sidecar transport uses a local OpenAI-compatible stub. Actual Tauri WebView2 automation verifies native persistence through CDP, without computer-use tools. A per-setting persistence pass does not establish every runtime path or live-provider compatibility. See `audit-results/settings-repair/setting-mode-matrix.csv` for measured scenarios and blocked cases.


## Built-in translation defaults

New projects default to Japanese to Thai, 250,000 TPM / 30 RPM, three review passes and a 9.5 quality threshold. RAG starts disabled. Primary, critic, chronicler and scraper use `gemini-3.5-flash-lite`; fallback, extractor, drafter and polisher use `gemini-3.1-flash-lite`. All roles use high thinking; translation roles use temperature 0.1 and scraper retains 1.0. `.env.example` documents this baseline. Explicit project and machine settings retain precedence.

Terminal settings reject invalid numeric edits rather than reporting success with the previous value. Project saves update the selected project config.yaml; global saves update the machine .env.
