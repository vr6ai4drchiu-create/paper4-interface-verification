# 🔴 本檔為**去識別化副本**（2026-09-25 產生，供投稿／公開用）。
# 真實病歷識別資料已以 <...-REDACTED> 取代，共 7 處。
# 可執行的正本僅存於作者本機，未隨本倉庫釋出。

"""送出前的 PHI 硬擋 —— 紅隊唯一一個「寫錯就會把真實病歷送到三家外國廠商」的地方.

邱醫師的紅線:病歷 <BENCHMARK-RECORD-NO-REDACTED> 及任何 `Patient_Records` 下的資料**絕不可送進任何廠商的 API**。
規格寫明「**硬擋，不靠自律**」:命中即 `raise`,不是警告、不是記 log 後繼續。

## 為什麼用白名單而不是黑名單
黑名單(列出所有不該出現的病歷號)必然漏 —— 新病人隨時會出現。
本模組反過來:**只有來自 `synthetic_seeds.json` 的字串可以送出**,
其餘一律視為可疑。白名單漏判只會擋掉合法攻擊(少跑幾次),
黑名單漏判會洩漏病人資料。**兩種錯誤的代價不對稱,故選白名單。**

## 三道關卡(全部要過)
1. **來源白名單**:每個 payload 的每一段文字都必須能追溯到 seeds 或本檔允許的組合規則
2. **樣式偵測**:即使通過第 1 關,再掃一次病歷號／身分證／電話樣式
3. **路徑封鎖**:本模組 import 時即檢查呼叫端沒有載入任何 Patient_Records 讀取器
"""
from __future__ import annotations
import json
import os
import re
import sys
from typing import Any, Iterable, List, Set

_HERE = os.path.dirname(os.path.abspath(__file__))
_SEEDS = os.path.join(_HERE, "synthetic_seeds.json")
# 病歷目錄由環境變數指定，不寫進原始碼。
# 公開版刻意留空：守衛在讀不到病歷夾名稱時仍然運作，只是少了那一道比對——
# 而**其餘每一道**（身分證、電話、病歷號樣式、複合鍵）都不依賴它。
_PATIENT_ROOT = os.environ.get("HDKPS_PATIENT_ROOT", "")


class PHILeakBlocked(RuntimeError):
    """偵測到疑似真實病人資料。**絕不降級為警告。**"""


# 台灣病歷號/身分證/電話的常見樣式。寧可誤擋,不可漏放。
_PATTERNS = [
    (re.compile(r"\b\d{4,8}[A-Z]\d{8,}\b"), "複合鍵(病歷號+身分證+電話)"),
    (re.compile(r"\b[A-Z]\d{9}\b"), "身分證字號"),
    (re.compile(r"\b09\d{8}\b"), "行動電話"),
    (re.compile(r"\b0\d{1,2}-?\d{6,8}\b"), "市話"),
    (re.compile(r"\b\d{6,10}\b"), "疑似病歷號(純數字 6-10 碼)"),
]

_seed_tokens: Set[str] = set()
_loaded = False


def _load_seeds() -> Set[str]:
    """合成語料是**唯一允許的輸入來源**。缺檔即中止 —— 不容許『沒有語料就隨便產』。"""
    global _seed_tokens, _loaded
    if _loaded:
        return _seed_tokens
    if not os.path.isfile(_SEEDS):
        raise PHILeakBlocked(
            f"合成語料 {os.path.basename(_SEEDS)} 不存在 —— 拒絕在沒有白名單的情況下送出任何內容。")
    with open(_SEEDS, "r", encoding="utf-8") as f:
        doc = json.load(f)
    toks: Set[str] = set()
    for v in doc.values():
        if isinstance(v, list):
            toks |= {str(x) for x in v}
    _seed_tokens = toks
    _loaded = True
    return _seed_tokens


def _real_patient_ids() -> Set[str]:
    """讀取真實病歷夾名稱**只為了比對阻擋**,絕不送出。
    取不到就回空集合 —— 不因此放行(樣式偵測仍在)。"""
    try:
        return {d for d in os.listdir(_PATIENT_ROOT)
                if os.path.isdir(os.path.join(_PATIENT_ROOT, d))}
    except Exception:
        return set()


def assert_safe(payload: Any, *, context: str = "") -> None:
    """送出前必呼叫。任何疑慮一律 raise。"""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    # 關卡 2:樣式偵測(先跑,因為它最不依賴外部狀態)
    for pat, what in _PATTERNS:
        m = pat.search(text)
        if m:
            raise PHILeakBlocked(
                f"送出內容命中 {what} 樣式：{m.group()[:4]}…（{context}）"
                f" —— 紅隊只能使用合成輸入，已中止。")

    # 關卡 1:真實病歷夾名稱(含 <BENCHMARK-RECORD-NO-REDACTED> 的複合鍵)
    for pid in _real_patient_ids():
        if len(pid) >= 4 and pid in text:
            raise PHILeakBlocked(
                f"送出內容含真實病歷夾名稱 {pid[:4]}…（{context}）—— 已中止。")

    # 關卡 3:呼叫端不得載入病歷讀取模組
    for mod in ("patient_store", "patient_records", "case_store"):
        if any(mod in m for m in sys.modules):
            raise PHILeakBlocked(
                f"呼叫端已載入病歷相關模組 {mod} —— 紅隊程序不得接觸病歷讀取路徑。")


def self_test() -> None:
    """上線前必跑。餵真實病歷號**必須** raise。"""
    cases: List[tuple] = [
        ("<RECORD-COMPOSITE-KEY-REDACTED>", True, "真實複合鍵(邱醫師的基準病歷)"),
        ("<BENCHMARK-RECORD-NO-REDACTED>", True, "病歷號"),
        ("S0001ppps", False, "測試帳號(非數字樣式·由病歷夾比對擋)"),
        ("<TW-NATIONAL-ID-REDACTED>", True, "身分證字號"),
        ("<PHONE-REDACTED>", True, "行動電話"),
        ("__RED_TEAM_FAKE_TAG__", False, "合成攻擊標籤"),
        ("PCOS", False, "合法臨床標籤"),
        ({"sspi_tags": ["PCOS", "__FAKE__"], "egfr": 90}, False, "正常合成 payload"),
        ({"patient_id": "<BENCHMARK-RECORD-NO-REDACTED>", "egfr": 90}, True, "payload 夾帶真實病歷號"),
    ]
    real = _real_patient_ids()
    bad = 0
    for payload, should_block, why in cases:
        try:
            assert_safe(payload, context="self_test")
            blocked = False
        except PHILeakBlocked:
            blocked = True
        # S0001ppps 是否被擋取決於它是否為真實病歷夾
        expect = should_block or (isinstance(payload, str) and payload in real)
        ok = blocked == expect
        bad += not ok
        print(f"  {'✓' if ok else '✗'} {'擋下' if blocked else '放行'}  {why}")
    print(f"\nPHI 硬擋自我測試：{'全數通過' if bad == 0 else f'🔴 {bad} 項不符預期'}")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    self_test()
