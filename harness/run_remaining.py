# 🔴 本檔為**去識別化副本**（2026-09-25 產生，供投稿／公開用）。
# 真實病歷識別資料已以 <...-REDACTED> 取代，共 0 處。
# 可執行的正本僅存於作者本機，未隨本倉庫釋出。

"""補跑剩餘的執行 —— B 臂兩次(金鑰修好)＋ C/on.

D/on 排在最後:o3-mini 的 D/off 一次吃掉 US$20.04,原本 OpenAI 僅剩約 $17.90 會中途用罄。
邱醫師 2026-09-25 加值 $10 ⇒ D/on 可用與 D/off 相同的 $20 預算,組內對照對等。
排最後是因為前三次要跑數小時,屆時加值早已到帳。

## 每次開跑前先單發驗證
B/off 曾因金鑰失效而盲跑 240 分鐘、0 產出、0 失敗紀錄
（失敗計數在 summary 裡,而 summary 只在正常結束時才寫,逾時就什麼都沒有）。
⇒ **先用一次 US$0.00005 的呼叫確認通得過,再投入數小時。**
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# 直接用執行本檔的直譯器；不寫死任何人的 venv 路徑。
VP = os.environ.get("HDKPS_PYTHON", sys.executable)
PROGRESS = os.path.join(HERE, "run_remaining_progress.json")
PLAN = [("B", "off"), ("B", "on"), ("C", "on"), ("D", "on")]


def preflight(arm: str) -> bool:
    """單發驗證。不通就跳過該臂,不讓它盲跑。"""
    sys.path.insert(0, HERE)
    import adapters
    try:
        t, i, o = adapters.call(arm, "測試。", "只回覆 OK。", tries=1)
        print(f"  ✅ {arm} 臂可用（成本 US${adapters.cost_usd(arm, i, o):.6f}）", flush=True)
        return True
    except Exception as e:      # noqa: BLE001
        print(f"  🔴 {arm} 臂不可用，跳過：{type(e).__name__}: {e}", flush=True)
        return False


def main() -> int:
    state = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "runs": []}
    checked: dict = {}
    for arm, cond in PLAN:
        if arm not in checked:
            print(f"\n── {arm} 臂開跑前驗證 ──", flush=True)
            checked[arm] = preflight(arm)
        if not checked[arm]:
            state["runs"].append({"arm": arm, "cond": cond, "skipped": "preflight_failed"})
            continue

        t0 = time.time()
        print(f"\n{'='*70}\n▶ 臂 {arm} · uplift={cond}\n{'='*70}", flush=True)
        entry = {"arm": arm, "cond": cond, "started": time.strftime("%H:%M:%S")}
        try:
            p = subprocess.run(
                [VP, os.path.join(HERE, "redteam_runner.py"),
                 "--arm", arm, "--uplift", cond],
                cwd=HERE, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                capture_output=True, text=True, errors="replace", timeout=6000)
            print("\n".join((p.stdout or "").strip().splitlines()[-22:]), flush=True)
            entry["returncode"] = p.returncode
            if p.returncode != 0:
                print(f"🔴 rc={p.returncode}\n{(p.stderr or '')[-500:]}", flush=True)
        except Exception as e:      # noqa: BLE001
            entry["returncode"] = f"{type(e).__name__}: {e}"
            entry["ANOMALY"] = "執行未正常結束，需人工檢視"
            print(f"🔴 {e}", flush=True)

        s_path = os.path.join(HERE, "results", f"{arm}_uplift-{cond}_summary.json")
        if os.path.isfile(s_path):
            s = json.load(open(s_path, encoding="utf-8"))
            entry.update({k: s.get(k) for k in
                          ("calls", "invented_tag_count", "guard_path_touched",
                           "attacks_that_influenced_judgment", "cost_usd",
                           "stopped_by", "failures")})
        stall = os.path.join(HERE, "results", f"{arm}_uplift-{cond}_STALLED.txt")
        if os.path.isfile(stall):
            entry["ANOMALY"] = "看門狗判定停滯（開跑 90 秒內幾乎無產出）"
            print(chr(10) + f"🔴🔴 異狀：{arm}/{cond} 停滯，已中止。後續執行照常，但本次無資料。", flush=True)
        n = 0
        jl = os.path.join(HERE, "results", f"{arm}_uplift-{cond}.jsonl")
        if os.path.isfile(jl):
            n = sum(1 for _ in open(jl, encoding="utf-8"))
        if n < 100:
            entry["ANOMALY"] = entry.get("ANOMALY") or f"產出僅 {n} 筆，遠低於預期"
            print(chr(10) + f"🔴🔴 異狀：{arm}/{cond} 僅產出 {n} 筆 —— 不正常，請檢視。", flush=True)
        entry["minutes"] = round((time.time() - t0) / 60, 1)
        state["runs"].append(entry)
        state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with open(PROGRESS, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)

    print(f"\n{'='*70}\n補跑完成\n{'='*70}", flush=True)
    try:
        r = subprocess.run([VP, os.path.join(HERE, "analyze.py")], cwd=HERE,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                           capture_output=True, text=True, errors="replace", timeout=600)
        print(r.stdout[-5000:], flush=True)
    except Exception as e:      # noqa: BLE001
        print(f"分析失敗（原始資料仍在，可事後重算）：{e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
