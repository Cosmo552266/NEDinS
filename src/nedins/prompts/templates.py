"""Centralised prompt templates. Tweak here without touching agent logic."""
from __future__ import annotations

# ---------- Trend Scout ------------------------------------------------------

TREND_SCOUT_SYSTEM = (
    "你係一位成人懸疑內容嘅 producer，識得睇市場熱度同節日氣氛揀題。"
    "你嘅 story idea 要適合 8 至 12 分鐘短片 + POD 周邊（T-shirt / poster / mug）。"
    "避免血腥獵奇，重氛圍同心理。"
)

TREND_SCOUT_USER = """\
今日：{today}
未來 30 日節日：{holidays}
Google Trends rising (EN): {rising_en}
Google Trends rising (ZH): {rising_zh}
過往高 ROI 主題群（如有）：{priors}
主題範疇：{topics}

請揀一個最有商業潛力嘅成人懸疑故事主題，配合節日或熱搜為佳。
輸出 JSON：
{{
  "title": "繁中標題（吸睛）",
  "pitch": "1-2 句故事鈎子",
  "source": "google_trends|holiday|prior|manual",
  "source_detail": "來源解釋",
  "keywords": ["關鍵字", ...4-6 個],
  "holiday": "節日名 or null",
  "backup_pitches": ["備胎 1", "備胎 2", "備胎 3"]
}}
"""

# ---------- Story Writer -----------------------------------------------------

STORY_WRITER_SYSTEM = (
    "你係一位專寫成人懸疑短篇嘅小說家。"
    "文字含蓄克制，重氣氛多於血腥，多用感官同細節而非直白嘅恐怖描寫。"
    "結構：強 hook → 鋪陳 → 中段轉折 → 開放式結尾（留畀讀者諗象）。"
    "適合改編做 8-12 分鐘旁白短片。"
)

STORY_WRITER_ZH = """\
主題：{title}
推介語：{pitch}
關鍵字：{keywords}
節日（如有）：{holiday}

請寫一篇 {word_count} 字（±15%）嘅繁體中文成人懸疑短篇。
- 第一行用 `# 標題` 寫出標題（可以同主題唔同）
- 段落唔好太長，方便配旁白
- 中段必須有一個明顯反轉
- 結尾開放式，留 1-2 個 visual hook（適合做 thumbnail / poster）
- 唔好寫露骨性愛或極端暴力，重心理同氛圍

直接出小說，唔好加任何 meta 說明。
"""

STORY_WRITER_EN_LOCALIZE = """\
Translate-and-localize the following Traditional Chinese suspense short story into English
for a Western adult audience. This is a rewrite, not a literal translation:
- Adapt cultural references (e.g. Hong Kong "唐樓" → "walk-up tenement")
- Preserve tension, pacing, and the open ending
- Keep `# Title` on the first line (you may localize the title)
- Match the original word count within ±15%
- Same content guardrails: no explicit sex, no extreme gore

Output only the story, no commentary.

---
{zh_story}
---
"""

KEY_VISUALS_PROMPT = """\
以下故事：

{story}

請抽出 {count} 個「視覺記憶點」(key visuals)，每個包含：
- label: 5-10 字短標籤
- description: 1-2 句場景描述（鏡頭、構圖、光線）
- pod_friendly: boolean，呢個畫面適唔適合直接印成 T-shirt 或 poster
  （標準：構圖簡潔、有 iconic 元素、唔需要太多上下文先 readable）

輸出 JSON list（{count} 個 element），唔好加任何其他文字。
"""

# ---------- Storyboard -------------------------------------------------------

STORYBOARD_PROMPT = """\
故事（繁中）：
{story_zh}

故事（English）：
{story_en}

請拆成 {scenes_min}–{scenes_max} 個場景，做成短片 storyboard。輸出 JSON：

{{
  "cover_prompt": "封面英文 prompt for Imagen, 16:9, 包含 title concept",
  "scenes": [
    {{
      "index": 1,
      "narration_zh": "繁中旁白 1-2 句（口語自然，啱讀出嚟）",
      "narration_en": "EN narration 1-2 sentences (natural spoken)",
      "visual_prompt": "Imagen 英文 prompt，必須以以下風格 prefix 開頭：'{style}'",
      "duration_sec": 6.0-12.0,
      "pod_friendly": false
    }}, ...
  ]
}}

要求：
- 每個 scene 旁白同視覺要對齊
- 第一個 scene 係 hook，最後一個 scene 留開放式
- 至少 1-2 個 scene 標 pod_friendly: true（iconic / 構圖簡潔）
- visual_prompt 描述要具體：鏡頭（close-up / wide）、光線、色調

只輸出 JSON。
"""

# ---------- Marketing --------------------------------------------------------

MARKETING_PROMPT = """\
故事標題（中）：{title_zh}
故事標題（EN）：{title_en}
主題：{theme}
關鍵字：{keywords}
故事 hook（繁中）：{pitch}

請為以下平台寫宣傳文案（繁中 + 英文）：{platforms}

每篇 caption 要求：
- IG: 2-3 句 + emoji（適度），結尾留懸念
- X: 1-2 句，可以 thread 起手
- TikTok hook: 一句話 hook，3 秒內讀完
- Facebook: 3-4 句，比 IG 略長

整體共用一份 {hashtag_count} 個 hashtag list（中英混合 OK）。

輸出 JSON：
{{
  "instagram_zh": str, "instagram_en": str,
  "x_zh": str, "x_en": str,
  "tiktok_hook_zh": str, "tiktok_hook_en": str,
  "facebook_zh": str, "facebook_en": str,
  "hashtags": [str, ...]
}}
"""
