# Roadmap

每個 milestone 都應該 ship 到一個跑得通嘅 demo。

## M0 — Scaffold (current)

- [x] 目錄結構 + Pydantic schemas
- [x] 每個 agent 嘅 stub (`run()` 回 mock data)
- [x] Orchestrator skeleton + `--dry-run`
- [x] `pyproject.toml` + `.env.example`
- [ ] CI: lint + type check

**Exit criteria**: `python -m nedins.orchestrator --dry-run` 跑得通，產出 mock campaign folder。

## M1 — Story MVP (1 週)

- [ ] `clients/gemini.py` 包好 `google-genai` SDK
- [ ] Trend Scout: pytrends + holidays 接好；Gemini 揀題
- [ ] Story Writer: 真係寫到 1500-3000 字雙語故事 + key visuals
- [ ] Storyboard: 拆 8-12 場景，每個有 Imagen-ready prompt
- [ ] 出 3 個 sample campaign 畀人試讀

**Exit criteria**: 一個 cron 啟動之後 5 分鐘內，有 markdown + json 可以畀人睇。

## M2 — Visual MVP (2 週)

- [ ] Image Generator: Imagen 3 接好，cover + 場景圖 + POD 1:1 hi-res
- [ ] Voiceover: Gemini TTS 雙語
- [ ] Video Composer: moviepy slideshow + Ken Burns + 字幕 + 旁白
- [ ] 出第一支可以播放嘅 5 分鐘短片

**Exit criteria**: 一個 campaign run 完，有 `final_zh.mp4` 可以喺 player 播。

## M3 — Publish MVP (2 週)

- [ ] Printify client: upload image + create T-shirt / poster / mug products
- [ ] YouTube client: OAuth + `videos.insert`
- [ ] Marketing Copy: IG / X / TikTok / FB 雙語文案
- [ ] CLI flag 揀 publish 邊個平台

**Exit criteria**: 一鍵跑完，YouTube 有 unlisted 片 + Printify shop 有 draft product。

## M4 — Closed Loop (2 週)

- [ ] Analytics agent: 拉 YouTube Analytics + Printify orders
- [ ] DuckDB `theme_priors` schema + ETL
- [ ] Trend Scout 讀 prior 做 Bayesian weighting
- [ ] Dashboard (Streamlit) 睇每個 campaign ROI

**Exit criteria**: 跑 4 週後，trend scout 揀題明顯 bias 向高 ROI cluster。

## M5 — 微電影 (4 週)

- [ ] Veo 3 client，scene-by-scene 生 cinematic clips
- [ ] 對白用 character voice (Gemini TTS multi-speaker)
- [ ] 鏡頭語言 prompt template (廣角、低角度、跟拍 etc.)
- [ ] 出第一支 10 分鐘微電影

**Exit criteria**: 微電影質素過得了 YouTube 主流懸疑頻道嘅基準線。

## Backlog / Nice-to-have

- [ ] Multi-character dialogue voice acting
- [ ] 自動生 Spotify podcast 版本 (story as audio drama)
- [ ] A/B test thumbnail (Gemini 出 3 個，YouTube experiment API)
- [ ] 自動回覆 YouTube comment (用 community guideline-safe Gemini)
- [ ] 中文配音用本地化 voice (港式廣東話)
- [ ] 翻譯擴張：日文 / 韓文 / 西班牙文
