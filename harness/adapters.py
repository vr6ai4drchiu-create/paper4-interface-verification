# 🔴 本檔為**去識別化副本**（2026-09-25 產生，供投稿／公開用）。
# 真實病歷識別資料已以 <...-REDACTED> 取代，共 0 處。
# 可執行的正本僅存於作者本機，未隨本倉庫釋出。

"""三家廠商的最小介面層 —— 廠商差異全部收斂在這裡,執行器不需要知道是誰在攻擊.

每個 adapter 只做一件事:給它一段提示,回 `(文字, 輸入token, 輸出token)`。
飽和判準、預算上限、PHI 硬擋、結果評分**全部不在這裡** ——
那些跨廠商必須完全一致,放進 adapter 就會有三份實作、三種行為。

## 單價(每百萬 token·2026-09 公開費率)
**這些是估計值。** 執行器一律記錄實際 token 數,
故日後費率有變,成本可用原始紀錄重算,不必重跑。
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, Tuple

_KEYS = {
    # 金鑰放在自己的家目錄，路徑不寫死（也不洩漏使用者名稱）。
    "google": os.path.expanduser("~/.hdkps_gemini_key.txt"),
    "anthropic": os.path.expanduser("~/.hdkps_anthropic_key.txt"),
    "openai": os.path.expanduser("~/.hdkps_openai_key.txt"),
}

# (輸入, 輸出) 美元/百萬 token
PRICING: Dict[str, Tuple[float, float]] = {
    "gemini-3.1-flash-lite": (0.10, 0.40),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3-mini": (1.10, 4.40),
}

ARMS = {
    "A": {"vendor": "google", "model": "gemini-3.1-flash-lite", "class": "fast"},
    "B": {"vendor": "anthropic", "model": "claude-haiku-4-5-20251001", "class": "fast"},
    "C": {"vendor": "openai", "model": "gpt-4.1-nano", "class": "fast"},
    "D": {"vendor": "openai", "model": "o3-mini", "class": "reasoning"},
}

_key_cache: Dict[str, str] = {}


def _key(vendor: str) -> str:
    """讀金鑰。**絕不印出、絕不寫進任何輸出檔。**"""
    if vendor not in _key_cache:
        p = _KEYS[vendor]
        if not os.path.isfile(p):
            raise RuntimeError(f"{vendor} 金鑰不存在:{os.path.basename(p)}")
        _key_cache[vendor] = open(p, encoding="utf-8").read().strip()
    return _key_cache[vendor]


def _post(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def call(arm: str, system: str, user: str, tries: int = 4) -> Tuple[str, int, int]:
    """回 (文字, 輸入token, 輸出token)。失敗重試後仍失敗則拋出。"""
    spec = ARMS[arm]
    vendor, model = spec["vendor"], spec["model"]
    last: Exception | None = None

    for attempt in range(tries):
        try:
            if vendor == "google":
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                       f"{model}:generateContent?key={_key('google')}")
                resp = _post(url, {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"temperature": 1.0, "maxOutputTokens": 2048},
                }, {"Content-Type": "application/json"})
                txt = "".join(p.get("text", "") for p in
                              resp["candidates"][0]["content"]["parts"]).strip()
                u = resp.get("usageMetadata", {})
                return txt, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)

            if vendor == "anthropic":
                resp = _post("https://api.anthropic.com/v1/messages", {
                    "model": model, "max_tokens": 2048, "temperature": 1.0,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                }, {"Content-Type": "application/json",
                    "x-api-key": _key("anthropic"),
                    "anthropic-version": "2023-06-01"})
                txt = "".join(b.get("text", "") for b in resp.get("content", [])).strip()
                u = resp.get("usage", {})
                return txt, u.get("input_tokens", 0), u.get("output_tokens", 0)

            # openai —— 推理型模型不吃 temperature,且用 max_completion_tokens
            body = {"model": model,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}]}
            if spec["class"] == "reasoning":
                body["max_completion_tokens"] = 4096
            else:
                body["max_tokens"] = 2048
                body["temperature"] = 1.0
            resp = _post("https://api.openai.com/v1/chat/completions", body,
                         {"Content-Type": "application/json",
                          "Authorization": f"Bearer {_key('openai')}"})
            txt = (resp["choices"][0]["message"].get("content") or "").strip()
            u = resp.get("usage", {})
            return txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

        except urllib.error.HTTPError as e:
            last = e
            # 429 = rate limit(不計費)。指數退避;CircuitBreaker 由執行器管,這裡只退避。
            if e.code == 429 and attempt < tries - 1:
                time.sleep(min(60, 4 * (2 ** attempt)))
                continue
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
        except Exception as e:      # noqa: BLE001
            last = e
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise last if last else RuntimeError("unreachable")


def cost_usd(arm: str, tin: int, tout: int) -> float:
    pin, pout = PRICING[ARMS[arm]["model"]]
    return tin / 1e6 * pin + tout / 1e6 * pout
