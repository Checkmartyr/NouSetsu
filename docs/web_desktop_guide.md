# Web Studio & Desktop App Guide

NouSetsu offers the same React Web Studio in two local forms: a browser app served by the Python CLI, and a Windows desktop app packaged with Tauri. Both connect to a local NouSetsu backend; neither is a hosted cloud service.

## Choose how to run NouSetsu

| | Browser Web Studio | Windows desktop app |
|:---|:---|:---|
| Start | Run `uv run nousetsu web`, then open `http://127.0.0.1:5173`. | Install and launch NouSetsu from the [GitHub Releases](https://github.com/Checkmartyr/NouSetsu/releases/latest) page. |
| Requirements | Python 3.13+ and the project dependencies. `--dev` also requires Node.js and the web dependencies. | The installer includes the Python backend; a separate Python installation is not required. |
| Updates | Update the source checkout using Git and `uv`. | Check for signed updates from **Settings → App Updates**. |

The browser server binds to the local machine by default. Keep it on localhost when configuring API keys; machine-wide environment settings are restricted to local browser origins and the desktop app.

## Start Web Studio from a checkout

From the NouSetsu repository:

```bash
uv sync
uv run nousetsu web
```

NouSetsu opens the default local address, `http://127.0.0.1:5173`. To use another port, pass `--port`, for example `uv run nousetsu web --port 5180`. For live frontend development, install the web dependencies with `npm ci --prefix web` and start `uv run nousetsu web --dev`. Run `uv run nousetsu web --help` to see the other supported options.

## Install and launch the Windows desktop app

Download the Windows installer from [NouSetsu Releases](https://github.com/Checkmartyr/NouSetsu/releases/latest), run it, and launch **NouSetsu** from the Start menu. The desktop app starts or connects to its local backend and opens the Web Studio in its Tauri window.

On first launch, NouSetsu copies the bundled `.env.example` into its application-data directory as `.env` if a local `.env` does not already exist. Later launches and updates preserve the existing file. The desktop app shows its `.env` location in **Settings → Environment & API Keys**.

> [!NOTE]
> The updater signature verifies that an installer is authentic for NouSetsu, but is separate from Windows Authenticode publisher signing. Windows SmartScreen can still show an unknown-publisher warning; see the [Windows code-signing guide](./windows-code-signing.md).

## Configure model providers and API keys

Open **Settings → Environment & API Keys**. This is the machine-wide settings area shared by projects on that installation. Add the API key for the provider you use, then click **Save Global Settings**. Supported providers include Gemini/Google, OpenAI, OpenRouter, and OpenAI-compatible custom endpoints.

Keys are saved locally in the application’s `.env` file. The UI masks key entry and reports whether a key is configured; it does not display the saved value. Leave a key field blank to keep its saved value, or choose **Clear saved key** to remove it. Protect the `.env` file like any other file containing credentials.

### Use a custom OpenAI-compatible provider

1. In **Environment & API Keys**, enter the provider’s API root in **Custom OpenAI-compatible base URL**, for example `https://provider.example/v1`.
2. Enter the provider key in **Custom provider API key**.
3. Under **Global model routes**, select **Custom OpenAI-compatible** and load the model catalog. If the provider does not expose the compatible `/models` endpoint, enter its model ID manually.
4. Click **Save Global Settings**.
5. To use a different model for one novel, open that project’s **Settings → Model Routing**, choose **Custom OpenAI-compatible**, enter the model ID, and click **Save Settings**. Project settings override the machine-wide route for that project.

The custom endpoint must support the OpenAI-compatible chat completions API. When entered through the provider selector, the UI records the route as `custom:<model-id>`; you do not need to type that prefix yourself.

## Create or open a novel project

Use the project selector in the top bar to switch between registered projects. Select **New** to create one. Enter a title, choose the source and target languages and genre, and review the displayed project folder before creating it. The new project becomes active.

You can start with existing chapters or import them during project creation:

- **Local files:** In **Studio**, select **Upload**, add `.txt`, `.md`, or `.text` chapters, and choose a destination folder. Existing files are skipped unless overwrite is enabled.
- **Web novel URL:** Choose the URL import option, enter the novel or table-of-contents URL, select **Inspect TOC**, and choose all chapters, a range, or individual chapters before importing. This requires the Novel-Scraper integration to be available.
- **EPUB or PDF:** Select the eBook option, inspect the detected chapters, choose which chapters to import, and optionally extract embedded illustrations into the project’s `assets/` folder.

For details on supported sites and scraper setup, see the [Novel Scraper Guide](./novel_scraper.md).

## Translate chapters

1. Select the active project and, if needed, a volume folder in **Studio**.
2. Select a chapter to preview its source and current translation. Use the chapter scope and limit controls to choose what to translate; use **Force** only when you intend to replace completed output.
3. Choose the chapter’s **Run** action for one chapter or **Translate Batch** to process the selected scope. The chapter queue shows progress and status, and the **Pipeline Event Stream** displays live activity.
4. Select **Stop Translation** to request a graceful stop. NouSetsu saves a resumable checkpoint for work in progress.

Only one translation job can run at a time. Keep the intended project selected while a batch is running.

## Read and review translations

- **Reader** provides chapter navigation, font-size controls, dark/sepia/light themes, and a raw-source peek.
- **Traces** shows recorded model interactions. In **Chapter Traces**, select a chapter, filter by pipeline stage or status, and inspect outputs, prompts, and token/latency details. Switch to **Project Analytics** for project-wide recorded token totals and breakdowns by stage, model, volume folder, and chapter; select a folder to narrow the report. Metadata-only usage snapshots are shown separately from trace history, and incomplete history is clearly marked. These recorded metrics are not a billing ledger and missing usage is not estimated.
- **Diff Comparison** compares the drafting trace with the polishing trace. It is not a comparison between the original source file and the final translation; it is available after both traces exist.
- **Novel Bible** provides character profiles, a relationship visualizer, glossary terms, narrative memory, and raw YAML editing.

## Export a book

From **Studio**, select **Export eBook**. Choose a translated folder, output format (EPUB3, PDF, or HTML), and publication options. Preview the contents and adjust typography before downloading the file.

## Update the desktop app

In the Tauri desktop app, open **Settings → App Updates → Check for Updates**. If a signed update is available, choose **Install Update**; NouSetsu downloads and verifies the installer, stops its managed backend, installs the update, and relaunches. Web Studio in a browser can show release information, but it cannot install desktop updates.

If the signed check cannot complete, Settings may show a GitHub release link so you can download and run the installer manually. For the signing model, local testing, and troubleshooting, see [Desktop Auto-Updates](./desktop-auto-updates.md).

## Troubleshooting

- **No chapters appear:** Confirm the correct project and folder are selected, then upload chapters into the project’s raw-chapter folder.
- **A provider catalog does not load:** Verify the provider key and, for custom providers, the base URL. You can enter a model ID manually if `/models` discovery is unavailable.
- **Settings says a key is configured but does not show it:** This is expected; saved key values are never returned to the UI. Enter a replacement or use **Clear saved key**.
- **App Updates is unavailable in a browser:** Install updates from the Tauri desktop app or download the installer from [GitHub Releases](https://github.com/Checkmartyr/NouSetsu/releases/latest).
- **An update cannot replace a backend file:** Close other NouSetsu processes or terminals that may be using the backend, then restart the desktop app and retry.
