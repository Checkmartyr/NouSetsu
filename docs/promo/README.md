# 🎬 NouSetsu Social Media Promotional Kit & Video Hub

Welcome to the **NouSetsu Promotional Media Hub**! Everything you need to showcase, promote, and launch NouSetsu across YouTube, X (Twitter), TikTok, Reddit, and Discord is organized here.

---

## 📦 What's Inside This Kit

| Asset | File | Description |
| :--- | :--- | :--- |
| 🖼️ **Promotional Banner** | [`promo_banner.jpg`](file:///D:/Code/novel_translation_Agent/docs/promo/promo_banner.jpg) | Cinematic anime tech banner (16:9, 8K cyber aesthetic) for video thumbnails & social cards. |
| 🌐 **Interactive Video Presentation** | [`presentation.html`](file:///D:/Code/novel_translation_Agent/docs/promo/presentation.html) | Playable 16:9 web presentation reel with auto-play, voiceover TTS, glowing cyber UI, and animated progress. |
| 📝 **Full Video Scripts & Storyboard** | [`VIDEO_SCRIPT.md`](file:///D:/Code/novel_translation_Agent/docs/promo/VIDEO_SCRIPT.md) | 60-Second Viral Short (9:16) and 2-Minute Feature Showcase (16:9) scripts with scene cues and VO. |
| 📱 **Social Media Copy Kit** | [`SOCIAL_MEDIA_KIT.md`](file:///D:/Code/novel_translation_Agent/docs/promo/SOCIAL_MEDIA_KIT.md) | Ready-to-copy X/Twitter launch thread, Reddit posts (`r/LocalLLaMA`), YouTube descriptions, and hashtags. |
| 💻 **Terminal Video Demo** | [`demo_terminal_video.py`](file:///D:/Code/novel_translation_Agent/docs/promo/demo_terminal_video.py) | Automated, animated Rich terminal demo recording script showing scanner, LangGraph pipeline, and 3-tier memory. |

---

## 🎥 How to Create Your Promo Video in 3 Easy Steps

### Option A: Record the Web Presentation Reel (Fastest!)
1. Open [`presentation.html`](file:///D:/Code/novel_translation_Agent/docs/promo/presentation.html) in Chrome or Edge:
   ```bash
   # On Windows
   start docs/promo/presentation.html
   ```
2. Press **`⛶ Fullscreen`** and click **`🔊 Toggle Voiceover (TTS)`** if you want the browser's neural voice to narrate automatically!
3. Click **`▶ Play Presentation`** and record your screen with **OBS Studio**, **Windows Game Bar (Win+G)**, or **Clipchamp**.
4. You now have an instant 60-second video ready for YouTube Shorts, X, or TikTok!

### Option B: Record the Animated Terminal Demo
1. Open your favorite terminal (Windows Terminal, iTerm2, WezTerm).
2. Set terminal font size to ~16-18pt and window size to 1280x720 (or 1080x1920 for vertical reels).
3. Run the automated recording script:
   ```bash
   python docs/promo/demo_terminal_video.py
   ```
4. Record with OBS or [asciinema](https://asciinema.org/) to create high-framerate terminal eye-candy!

---

## 📱 Publishing Checklist
- [ ] Post X (Twitter) launch thread from [`SOCIAL_MEDIA_KIT.md`](file:///D:/Code/novel_translation_Agent/docs/promo/SOCIAL_MEDIA_KIT.md) with `promo_banner.jpg` or video.
- [ ] Post announcement on `r/LocalLLaMA` and `r/LightNovels`.
- [ ] Upload 60s Short on YouTube Shorts & TikTok with hashtags `#LightNovel #AI #LangGraph`.
- [ ] Add `promo_banner.jpg` as social preview image in GitHub repository settings.
