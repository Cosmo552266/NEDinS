# Architecture

## 1. 設計原則

1. **單向 pipeline + 閉環反饋**：每個 agent 只負責一件事，輸入/輸出用 Pydantic schema 規範。Analytics agent 將下游表現寫入 `theme_priors` table，Trend Scout 下次運行讀回去做 weighting，形成閉環。
2. **Artifact-first**：每個 agent 嘅輸出都係檔案 (markdown / json / png / mp4) + 一份 metadata，唔依賴記憶體。任何一步爆，可由 artifact 重新接續落去 (resumable)。
3. **Provider 抽象**：所有外部 API call 透過 `clients/` 嘅薄 wrapper，方便日後 swap (例如 Imagen → Flux)。
4. **Dry-run 必須跑得起**：冇 API key 都要可以行 `--dry-run` 跑通成個 pipeline，產出 mock artifact，方便 CI 同新人 onboarding。

## 2. 一個 "Campaign" 嘅生命週期

一個 **Campaign** = 一個主題對應嘅完整內容包 (故事 + 視覺 + 影片 + POD + 社交文案)。

```
Campaign(id="2026-W21-suspense-haunted-elevator")
├── theme.json           主題 + 來源 (trend keyword / 節日 / prior)
├── story_zh.md          繁中故事
├── story_en.md          英文故事
├── storyboard.json      場景拆分 (8-12 個 scene)
├── images/
│   ├── cover_zh.png     YouTube thumbnail 中
│   ├── cover_en.png     YouTube thumbnail 英
│   ├── scene_01.png ... 場景圖
│   └── pod/             POD 用 hi-res 圖
├── audio/
│   ├── narration_zh.mp3
│   └── narration_en.mp3
├── video/
│   ├── final_zh.mp4
│   └── final_en.mp4
├── marketing/
│   ├── ig_zh.txt        IG caption + hashtag
│   ├── ig_en.txt
│   ├── x_zh.txt
│   └── tiktok_hook.txt
├── pod/
│   └── products.json    Printify product IDs + listing
├── youtube/
│   └── upload.json      YouTube video IDs
└── metrics.json         (M4 才填) 銷售/觀看數據
```

## 3. 每個 Agent 嘅職責

### 3.1 Trend Scout (`agents/trend_scout.py`)

- **輸入**：當前日期、地區 (HK/TW/US)、過往 `theme_priors`
- **動作**：
  1. 攞未來 30 日節日 (萬聖、中元、聖誕、農曆新年、清明、端午 等) → 候選主題
  2. `pytrends` 搵 "ghost story", "urban legend", "haunted ___" 嘅 rising queries
  3. 由 prior table 攞高 ROI 嘅 cluster (例如 "電梯怪談" 過去賣得好就 boost)
  4. 用 Gemini 將候選 keyword 組合成 5 個 story pitch
- **輸出**：`theme.json` (揀咗嘅主題 + 3 個 backup) + 解釋

### 3.2 Story Writer (`agents/story_writer.py`)

- **輸入**：`theme.json`
- **動作**：Gemini 寫成人懸疑短篇 (1500-3000 字)，要求：
  - 雙語：先寫繁中，再 Gemini translate-rewrite 出英文 (唔係直譯，要在地化)
  - 結構：hook → 鋪陳 → 轉折 → 開放式結尾 (留 thumbnail / 商品 design 用)
  - 要 mark 出 3-5 個 "視覺記憶點" (key visual moments)，畀 storyboard agent 用
- **輸出**：`story_zh.md`, `story_en.md` + frontmatter 列明 key visuals

### 3.3 Storyboard (`agents/storyboard.py`)

- **輸入**：story markdown
- **動作**：Gemini 拆 8-12 個場景，每個場景生成：
  - Visual prompt (英文，畀 Imagen 用)
  - Narration line (中/英)
  - Duration 估算
  - POD-friendly flag (呢個場景嘅圖適唔適合做 T-shirt design)
- **輸出**：`storyboard.json`

### 3.4 Image Generator (`agents/image_generator.py`)

- **輸入**：`storyboard.json`
- **動作**：
  - 用 Gemini API 嘅 Imagen 3 生封面 (16:9) + 場景圖 (16:9) + POD 圖 (1:1 4500x5400 hi-res)
  - 統一風格：dark cinematic / film grain / muted palette (config 可改)
  - Cover 加文字 overlay (用 Pillow)
- **輸出**：`images/*.png`

### 3.5 Voiceover (`agents/voiceover.py`)

- **輸入**：storyboard 嘅 narration lines
- **動作**：Gemini TTS (Chirp 3 HD) 生中/英旁白，按 scene 切 chunk，留淡入淡出空間
- **輸出**：`audio/scene_NN_{zh,en}.mp3` + master `narration_{zh,en}.mp3`

### 3.6 Video Composer (`agents/video_composer.py`)

- **Phase 1**：`moviepy` 將圖 + 旁白 + 字幕 + BGM 合成 slideshow MP4 (Ken Burns 推拉效果)
- **Phase 2 (M5)**：每個 scene 改用 Veo 3 出 5-8 秒 cinematic clip，再拼埋
- **輸出**：`video/final_zh.mp4`, `video/final_en.mp4`

### 3.7 Marketing Copy (`agents/marketing_copy.py`)

- **輸入**：story + cover image
- **動作**：Gemini 生 IG caption / X thread / TikTok hook / FB post，雙語，加合適 hashtag
- **輸出**：`marketing/*.txt`

### 3.8 POD Publisher (`agents/pod_publisher.py`)

- **輸入**：hi-res POD 圖 + storyboard metadata
- **動作**：
  1. Upload 圖去 Printify (`POST /uploads/images.json`)
  2. 為每個 blueprint (T-shirt / poster / mug / sticker) 建 product
  3. 設 listing title + description (Gemini 寫 SEO copy)
  4. Publish 去連住嘅 Etsy / Shopify shop
- **輸出**：`pod/products.json` (product IDs + URLs)

### 3.9 YouTube Publisher (`agents/youtube_publisher.py`)

- **輸入**：`video/final_*.mp4` + marketing copy
- **動作**：YouTube Data API v3 `videos.insert`，set title / description / tags / thumbnail / playlist
- **輸出**：`youtube/upload.json` (video IDs)

### 3.10 Analytics (`agents/analytics.py`) — M4

- **輸入**：YouTube Analytics API + Printify orders API
- **動作**：每 N 日跑一次，將每個 campaign 嘅:
  - YouTube views / watch-time / CTR
  - POD sales / revenue
  - 主題 keyword cluster
  寫入 DuckDB `theme_priors` table。下次 Trend Scout 用。
- **輸出**：`analytics/snapshot_YYYY-MM-DD.parquet`

## 4. Orchestrator

`orchestrator.py` 跑 DAG (用簡單 sequential，唔需要 Airflow)：

```python
campaign = Campaign.create()
theme    = TrendScout().run(campaign)
story    = StoryWriter().run(campaign, theme)
board    = Storyboard().run(campaign, story)
images   = ImageGenerator().run(campaign, board)
audio    = Voiceover().run(campaign, board)
video    = VideoComposer().run(campaign, board, images, audio)
copy     = MarketingCopy().run(campaign, story, images)
pod      = PodPublisher().run(campaign, images, copy)   # 可以 disable
yt       = YouTubePublisher().run(campaign, video, copy) # 可以 disable
```

每步前 check artifact 存唔存在 → 已存在就 skip (resumable)。

CLI：

```bash
python -m nedins.orchestrator                    # 全跑
python -m nedins.orchestrator --skip pod,youtube # 只生內容
python -m nedins.orchestrator --resume CAMPAIGN_ID
python -m nedins.orchestrator --dry-run          # mock 所有 API
```

## 5. 風險 / 待決定

- **YouTube 自動上載受限**：YouTube Data API quota 預設好低 (10,000/日，一次 upload 1,600)，要申請 quota extension。Cold-start 建議手動上載，pipeline 只產出 ready-to-upload bundle。
- **Printify content policy**：成人懸疑 OK，但血腥/裸露會被 reject。要喺 prompt 加 safety guard。
- **Gemini 內容過濾**：成人主題容易撞 safety filter，要試 `safety_settings` block threshold + system prompt 寫法。
- **版權音樂**：BGM 要用 royalty-free (YouTube Audio Library / Epidemic Sound)。M2 暫時用無 BGM 版本。
- **持續成本估算** (一個 campaign)：
  - Gemini text + storyboard: ~$0.5
  - Imagen 12 張: ~$0.5
  - TTS 雙語 ~5 分鐘: ~$0.3
  - Veo (M5) 12 段 × $0.5: ~$6
  - Printify / YouTube API: 免費
  - **M2 一支 ~$1.5；M5 一支 ~$7.5**
