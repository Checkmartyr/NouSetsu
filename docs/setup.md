# First-install setup

NouSetsu guides you through five steps: Welcome, Connect AI, Translation, Storage, and Finish. Choose **English** or **ไทย** independently from your novel’s translation languages.

## Open setup

The desktop app includes Python and opens setup on a fresh installation. Existing installations receive an optional invitation; **Settings → Open guided setup** reopens it at any time.

For an installed Python package:

```bash
nousetsu setup
```

This serves the bundled UI on localhost and opens your browser. Node.js is not needed to run a released package. Without a browser, use:

```bash
nousetsu setup --terminal
```

Source checkout users run `uv run nousetsu setup`. Building a distribution from the checkout requires Node.js and frontend dependencies (`npm ci --prefix web`). The source distribution already includes the built frontend.

## Connect an AI service

Choose Google Gemini, OpenAI, OpenRouter, or a custom OpenAI-compatible service. Paste its connection key. Custom services additionally need their API address, such as `https://provider.example/v1`.

Select **Load available models**, then choose a model. If discovery is unavailable, enter the provider’s model ID manually. The provider selector adds routing prefixes automatically.

**Test connection** is optional. It sends a fixed short Japanese sample and checks an English structured response through the selected drafting model’s transport. Your provider may charge for this request. Discovery and saved credentials alone do not verify generation access. Additional models selected in Advanced are not individually tested.

On a new installation the chosen model handles translation stages, scraper requests, reranking, procedural refinement, and fallback. A fallback using the same model does not supply a separate quota. Existing routes are preserved until you change services or choose **Use this model for all translation tasks**.

Choose **Set up AI later** to create projects, import files, read existing translations, or export them. Translation redirects you to connect AI and returns you to your chapter afterward. Production models without credentials never generate mock translations. Keyword lore search works without Google credentials; semantic retrieval requires a Google key. Website import also depends on scraper availability and its provider configuration; local file import remains available.

## Languages, quality, and storage

Original language defaults to automatic detection. The initial output language is Thai when setup uses Thai, otherwise English. Existing language choices are preserved.

Recommended quality settings use up to three review passes and the existing 8.5 quality threshold. Advanced installation settings expose model routes, generation controls, quotas, memory settings, retrieval models, procedural learning and external scraper paths. Settings that belong to a specific novel, including chunking and safety controls, are available after creating that project. Local pacing limits do not change your provider’s account quotas.

Fresh installations suggest **Documents/NouSetsu**, including Windows redirected Documents folders. Existing paths are preserved. Choose a folder or paste its path; setup checks writability. Changing the default folder does not move existing novels.

Review your choices and select **Finish setup**. Then create your first novel, open an existing NouSetsu project folder, or explore Studio. The existing project flow supports chapter-file, eBook and URL imports according to available features.

## Saved settings and recovery

Keys stay in the selected local `.env`, never in browser storage. Empty key inputs retain saved credentials. A refresh restores nonsecret drafts but requires you to re-enter unsaved keys. The completion record stores only setup version, language and a fingerprint of a tested connection.

Desktop settings use application data. Fresh Python installations use per-user storage outside `site-packages`; Windows defaults to `%APPDATA%/com.nousetsu.app`. Explicit `NOUSETSU_ENV_FILE` selections and existing source-checkout/CWD `.env` files take precedence. Desktop and Python share the Windows location when neither has a separate selected configuration.

If another window changes settings, your draft remains and setup offers an explicit reload before retrying. If settings save but completion recording fails, retry **Finish setup**. Launcher environment variables remain authoritative; setup warns when they override edits. Settings changes affect subsequent jobs.

## เริ่มใช้งานภาษาไทย

เปิดแอปครั้งแรก หรือเรียก `nousetsu setup` แล้วเลือก **ไทย** ขั้นตอนแนะนำจะช่วยเลือกบริการ AI ภาษาสำหรับแปล และโฟลเดอร์เก็บนิยาย ไม่ต้องแก้ไฟล์การตั้งค่าเอง

หากยังไม่มีคีย์ เลือก **ตั้งค่า AI ภายหลัง** เพื่อนำเข้าและอ่านนิยายได้ก่อน เมื่อพร้อมแปล แอปจะให้เชื่อมต่อ AI คีย์เก็บในเครื่องนี้ การทดสอบส่งตัวอย่างสั้น ๆ และอาจมีค่าบริการจากผู้ให้บริการ

เลือก **บันทึกการตั้งค่า** แล้วสร้างนิยายเรื่องแรก หรือเปิดโครงการที่มีอยู่ เปลี่ยนค่าได้ภายหลังที่หน้าการตั้งค่า สำหรับเครื่องที่ไม่มีเบราว์เซอร์ ใช้ `nousetsu setup --terminal`
