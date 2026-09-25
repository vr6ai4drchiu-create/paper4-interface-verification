# 🔴 本檔為**去識別化副本**（2026-09-25 產生，供投稿／公開用）。
# 真實病歷識別資料已以 <...-REDACTED> 取代，共 0 處。
# 可執行的正本僅存於作者本機，未隨本倉庫釋出。

"""依序跑完 8 次正式執行(4 臂 × 2 條件),每次結束即寫進度檔.

依序而非平行:同一廠商的兩個條件若平行,會共用同一個 rate limit,
量到的差異會混進節流效應。**寧可慢,不可讓測量被污染。**

進度寫在 run_all_progress.json,中途看得到跑到哪裡。
任一次失敗不中止其餘 —— 失敗本身也是要記錄的結果。
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
PROGRESS = os.path.join(HERE, "run_all_progress.json")

# 先跑 off 再跑 on:若時間不夠,至少前測是完整的一組
PLAN = [(arm, cond) for cond in ("off", "on") for arm in ("A", "B", "C", "D")]


def main() -> int:
    state = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "runs": []}
    for arm, cond in PLAN:
        t0 = time.time()
        entry = {"arm": arm, "cond": cond, "started": time.strftime("%H:%M:%S")}
        print(f"\n{'='*70}\n▶ 臂 {arm} · uplift={cond}\n{'='*70}", flush=True)
        try:
            p = subprocess.run(
                [VP, os.path.join(HERE, "redteam_runner.py"),
                 "--arm", arm, "--uplift", cond],
                cwd=HERE, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                capture_output=True, text=True, errors="replace", timeout=14400)
            tail = "\n".join((p.stdout or "").strip().splitlines()[-24:])
            print(tail, flush=True)
            if p.returncode != 0:
                print(f"🔴 returncode={p.returncode}\n{(p.stderr or '')[-600:]}", flush=True)
            entry["returncode"] = p.returncode
        except subprocess.TimeoutExpired:
            entry["returncode"] = "timeout_4h"
            print("🔴 逾時 4 小時,跳過此次", flush=True)
        except Exception as e:      # noqa: BLE001
            entry["returncode"] = f"{type(e).__name__}: {e}"
            print(f"🔴 {e}", flush=True)

        s_path = os.path.join(HERE, "results", f"{arm}_uplift-{cond}_summary.json")
        if os.path.isfile(s_path):
            try:
                s = json.load(open(s_path, encoding="utf-8"))
                entry.update({k: s.get(k) for k in
                              ("calls", "invented_tag_count", "guard_path_touched",
                               "attacks_that_influenced_judgment", "cost_usd",
                               "stopped_by", "failures")})
            except Exception:       # noqa: BLE001
                pass
        entry["minutes"] = round((time.time() - t0) / 60, 1)
        state["runs"].append(entry)
        state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        state["total_cost_usd"] = round(
            sum(r.get("cost_usd") or 0 for r in state["runs"]), 4)
        with open(PROGRESS, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)

    print(f"\n{'='*70}\n全部完成 · 總花費 US${state['total_cost_usd']:.3f}\n{'='*70}", flush=True)

    # 跑完直接產報告
    try:
        r = subprocess.run([VP, os.path.join(HERE, "analyze.py")], cwd=HERE,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                           capture_output=True, text=True, errors="replace", timeout=600)
        print(r.stdout[-4000:], flush=True)
    except Exception as e:      # noqa: BLE001
        print(f"分析失敗(原始資料仍在,可事後重算): {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
