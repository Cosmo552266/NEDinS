# Sample Campaign Artifacts

呢個 folder 入面係由 `scripts/generate_samples.py --dry-run` 跑出嚟嘅範例 campaign 嘅 **text artifact**（無 image / audio / video 二進位）。目的係畀人睇到每個 agent 嘅輸出 shape，唔使裝 dependencies。

要再生：
```bash
PYTHONPATH=src python scripts/generate_samples.py --count 3 --dry-run
# artifacts 會寫去 data/campaigns/，dry-run 內容係 mock。
```

要跑真 API：
```bash
cp .env.example .env  # 填 GEMINI_API_KEY
PYTHONPATH=src python -m nedins.orchestrator
```

## 樣本內容

`2026-W21-elevator-14/` — dry-run mock 主題「十四樓的訪客」。

| 檔案 | 出自邊個 agent |
|---|---|
| `theme.json` | TrendScout |
| `story_zh.md` / `story_en.md` | StoryWriter |
| `key_visuals.json` | StoryWriter |
| `storyboard.json` | Storyboard |
| `marketing.json` | MarketingCopyAgent |
| `pod/products.json` | PodPublisher (mock IDs) |
| `youtube/upload.json` | YouTubePublisher (mock IDs) |
| `campaign.json` | Orchestrator final summary |

注意：dry-run 嘅文字內容係 hand-crafted mock（喺 `clients/gemini.py` 嘅 `_mock_text`），唔係 Gemini 真實 output。連 API key 跑就會見到真實寫嘅故事。
