# NEDinS — AI Story-to-Product Pipeline

閉環式 AI 內容生產 + 變現系統。由 Google Trends 出發，AI 寫成人懸疑/節日傳說短篇 → 生圖 → 生影片 → 自動上 YouTube 微電影 → 同步推 Printify POD 商品 → 收集銷售/觀看數據回流落 trend 揀題模型，做到主題可持續迭代。

> Status: **Milestone 0 — Scaffold**。架構同 stub 已就位，每個 agent 仍係 placeholder，要逐個 module 接 API key 同實作。

## 目標

- **目標客戶**：成人讀者/觀眾
- **主題**：懸疑 / 助長思考 / 節日傳說 (萬聖、中元、聖誕 ghost story、農曆新年怪談)
- **題材來源**：Google Trends (HK/TW/US) + 節日日曆 + 過往 ROI 回流
- **輸出語言**：繁體中文 (港台) + 英文 (全球) 雙語
- **發佈渠道**：YouTube (微電影) + Printify POD (T-shirt/poster/mug 等) + 社交宣傳素材 (IG/FB/X/TikTok)

## 技術棧

| Layer | 選型 | 用途 |
|---|---|---|
| Orchestrator | Python 3.11+ | Pipeline / agent 控制 |
| LLM / 圖 / 影片 / TTS | **Gemini** (`google-genai`) | 寫故事、Imagen 3 生圖、Veo 3 生影片、Chirp TTS |
| 趨勢 | `pytrends` + holidays | Google Trends + 節日 |
| POD | Printify REST API | 自動上架 (Etsy/Shopify 由 Printify 連) |
| 影片發佈 | YouTube Data API v3 | 自動上載微電影 |
| 影片合成 | `moviepy` + `Pillow` | 圖/字幕/語音合成 |
| 儲存 | Local FS (Phase 1) → S3/GCS (Phase 2) | Artifact 管理 |
| 數據回流 | DuckDB / SQLite | Theme prior + analytics |

## 閉環架構 (overview)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Trend Scout  │───▶│ Story Writer │───▶│ Storyboard   │
│ (Trends+節日)│    │  (Gemini)    │    │  (拆場景)    │
└──────────────┘    └──────────────┘    └──────┬───────┘
       ▲                                       │
       │ theme priors                          ▼
       │                              ┌──────────────────┐
┌──────┴───────┐                      │ Asset Generator  │
│  Analytics   │                      │ Imagen + Veo +TTS│
│ (ROI 回流)   │                      └────────┬─────────┘
└──────┬───────┘                               │
       │                                       ▼
       │                              ┌──────────────────┐
       │                              │  Video Compose   │
       │                              │   (moviepy)      │
       │                              └────────┬─────────┘
       │                                       │
       │              ┌────────────────────────┼─────────────────────┐
       │              ▼                        ▼                     ▼
       │      ┌──────────────┐         ┌──────────────┐      ┌──────────────┐
       └──────│  YouTube     │         │   Printify   │      │  Marketing   │
              │  Publisher   │         │   Publisher  │      │ Copy (IG/FB) │
              └──────────────┘         └──────────────┘      └──────────────┘
```

## 目錄結構

```
src/nedins/
├── orchestrator.py        主 pipeline runner
├── agents/                每個 agent 一個 module
│   ├── trend_scout.py
│   ├── story_writer.py
│   ├── storyboard.py
│   ├── image_generator.py
│   ├── video_generator.py
│   ├── voiceover.py
│   ├── video_composer.py
│   ├── marketing_copy.py
│   ├── pod_publisher.py
│   ├── youtube_publisher.py
│   └── analytics.py
├── clients/               外部 API 薄 wrapper
│   ├── gemini.py
│   ├── google_trends.py
│   ├── printify.py
│   └── youtube.py
├── models/schemas.py      Pydantic data models
├── storage/artifacts.py   Artifact 路徑管理
└── prompts/               Prompt templates (中/英)
```

## Roadmap

睇 [`docs/ROADMAP.md`](docs/ROADMAP.md) 有分階段細節。簡版：

- **M0 — Scaffold** ✅ 架構、schema、stub
- **M1 — Story MVP**：Trend Scout + Story Writer 行得通，產出雙語 markdown
- **M2 — Visual MVP**：Imagen 生封面 + 場景圖；moviepy 合成 slideshow 影片 + Gemini TTS
- **M3 — Publish MVP**：YouTube 上載 + Printify mock product
- **M4 — Closed Loop**：Analytics agent 回流，影響 trend scout weighting
- **M5 — 微電影**：升級 slideshow → Veo 3 生 cinematic shots

## Quick start

```bash
# Python 3.11+
pip install -e ".[dev]"
cp .env.example .env   # 填 Gemini / Printify / YouTube credentials
python -m nedins.orchestrator --dry-run
```

詳細架構見 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
