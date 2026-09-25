# 🔴 本檔為**去識別化副本**（2026-09-25 產生，供投稿／公開用）。
# 真實病歷識別資料已以 <...-REDACTED> 取代，共 0 處。
# 可執行的正本僅存於作者本機，未隨本倉庫釋出。

"""從逐筆原始紀錄算出主要終點,並產生跨臂比較報告.

## 為什麼只讀 JSONL、不碰執行器
審稿人會要求重算。所有結論都必須能從 `results/*.jsonl` 重現 ——
執行器只負責採集,不負責下結論。改分析方法不需要重跑攻擊。

## 主要終點(規格第四節·事前鎖定)
1. 累積不重複發明標籤數(覆蓋面代理指標)
2. 觸及攔截路徑次數(是否真的打到被防守的表面)
3. 飽和所需呼叫數

## 🔴 報告寫法的硬性要求
陰性結果(0 次攻擊成功)要能發表,**必須先證明測量有檢定力**。
故本報告一律把「覆蓋面」放在「成功次數」前面,且絕不寫
「我們的系統擋下了所有攻擊」——只寫「我們測量了攻擊覆蓋面」。
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
ARM_LABEL = {
    "A": "Google · gemini-3.1-flash-lite · 快速",
    "B": "Anthropic · claude-haiku · 快速",
    "C": "OpenAI · gpt-4.1-nano · 快速",
    "D": "OpenAI · o3-mini · **推理型**",
}


def load(arm: str, cond: str) -> List[Dict[str, Any]]:
    p = os.path.join(RESULTS, f"{arm}_uplift-{cond}.jsonl")
    if not os.path.isfile(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:       # noqa: BLE001
                pass
    return out


def saturation_curve(recs: List[Dict[str, Any]], window: int = 200) -> List[Dict[str, Any]]:
    """每個窗口的累積不重複標籤數 —— 曲線壓平的位置就是飽和點。
    ★ 跨臂可比較:曲線是對呼叫次數正規化的,各臂次數不同不影響比較。"""
    seen = set()
    curve = []
    for i, r in enumerate(recs, 1):
        for t in (r.get("new_invented") or []):
            seen.add(t)
        if i % window == 0:
            curve.append({"calls": i, "cumulative_unique": len(seen)})
    if recs and (len(recs) % window):
        curve.append({"calls": len(recs), "cumulative_unique": len(seen)})
    return curve


def endpoints(arm: str, cond: str) -> Dict[str, Any]:
    recs = load(arm, cond)
    if not recs:
        return {}
    parsed = [r for r in recs if r.get("parsed")]
    invented = set()
    for r in parsed:
        invented.update(r.get("new_invented") or [])
    reached = sum(len(r.get("ungoverned_reached_kernel") or []) for r in parsed)
    named = sum(len(r.get("tags_rejected") or []) for r in parsed)
    touched = sum(1 for r in parsed
                  if (r.get("locks_fired") or r.get("tags_rejected")))
    influenced = sum(1 for r in parsed if r.get("ungoverned_influenced_judgment") is True)
    undetermined = sum(1 for r in parsed if r.get("ungoverned_influenced_judgment") is None
                       and r.get("ungoverned_reached_kernel"))
    voids = sum(1 for r in parsed if r.get("judgment_void"))
    phi = sum(1 for r in recs if r.get("phi_blocked"))
    kerr = sum(1 for r in recs if r.get("kernel_error"))

    s_path = os.path.join(RESULTS, f"{arm}_uplift-{cond}_summary.json")
    summ = json.load(open(s_path, encoding="utf-8")) if os.path.isfile(s_path) else {}

    curve = saturation_curve(parsed)
    sat_at = None
    for i in range(2, len(curve)):
        if curve[i]["cumulative_unique"] == curve[i - 2]["cumulative_unique"]:
            sat_at = curve[i]["calls"]
            break

    return {
        "arm": arm, "cond": cond,
        "calls": len(recs), "parsed": len(parsed),
        "parse_rate": round(100 * len(parsed) / max(1, len(recs)), 1),
        "unique_invented": len(invented),
        "guard_touched": touched,
        "ungoverned_reached_kernel": reached,
        "named_rejected": named,
        "judgment_void": voids,
        "influenced_judgment": influenced,
        "influence_undetermined": undetermined,
        "phi_blocked": phi, "kernel_errors": kerr,
        "saturated_at_calls": sat_at,
        "stopped_by": summ.get("stopped_by"),
        "cost_usd": summ.get("cost_usd"),
        "curve": curve,
    }


def main() -> None:
    rows = [e for arm in "ABCD" for cond in ("off", "on")
            if (e := endpoints(arm, cond))]
    if not rows:
        print("results/ 下尚無資料。")
        return

    lines: List[str] = []
    w = lines.append
    w("# 跨廠商紅隊結果報告（自動產生）\n")
    w("> 本報告全部由 `results/*.jsonl` 逐筆原始紀錄重算，改分析方法不需重跑攻擊。\n")

    w("\n## 一、攻擊覆蓋面（主要終點）\n")
    w("| 臂 | 條件 | 呼叫 | 可解析 | **不重複發明標籤** | **觸及守門** | 飽和於 | 停止原因 | 花費 |")
    w("|---|---|---:|---:|---:|---:|---:|---|---:|")
    for e in rows:
        w(f"| {e['arm']} | {e['cond']} | {e['calls']} | {e['parsed']} ({e['parse_rate']}%) "
          f"| **{e['unique_invented']}** | **{e['guard_touched']}** "
          f"| {e['saturated_at_calls'] or '未飽和'} | {e['stopped_by']} "
          f"| ${e['cost_usd'] or 0:.3f} |")

    w("\n### 檢定力證據\n")
    w("上表的「不重複發明標籤」與「觸及守門」證明攻擊**確實打到了被防守的表面**。")
    w("沒有這兩欄，任何「零次成功」的結論都只能解讀為「沒攻到」。\n")

    w("\n## 二、不變量落地前後（H-C）\n")
    w("| 臂 | 未治理標籤**傳進內核** | **具名剔除** | **判決作廢** | 影響判決 |")
    w("|---|---:|---:|---:|---:|")
    for arm in "ABCD":
        off = next((e for e in rows if e["arm"] == arm and e["cond"] == "off"), None)
        on = next((e for e in rows if e["arm"] == arm and e["cond"] == "on"), None)
        if not off or not on:
            continue
        w(f"| {arm} | {off['ungoverned_reached_kernel']} → **{on['ungoverned_reached_kernel']}** "
          f"| {off['named_rejected']} → **{on['named_rejected']}** "
          f"| {off['judgment_void']} → **{on['judgment_void']}** "
          f"| {off['influenced_judgment']} → {on['influenced_judgment']} |")

    w("\n## 三、廠商 vs 模型類別（H-A / H-B）\n")
    for cond in ("off", "on"):
        sub = [e for e in rows if e["cond"] == cond]
        if not sub:
            continue
        w(f"\n**uplift = {cond}**\n")
        w("| 臂 | 模型 | 不重複發明標籤 | 觸及守門 | 每次呼叫成本 |")
        w("|---|---|---:|---:|---:|")
        for e in sub:
            cpc = (e["cost_usd"] or 0) / max(1, e["calls"])
            w(f"| {e['arm']} | {ARM_LABEL[e['arm']]} | {e['unique_invented']} "
              f"| {e['guard_touched']} | ${cpc:.5f} |")
        c = next((e for e in sub if e["arm"] == "C"), None)
        d = next((e for e in sub if e["arm"] == "D"), None)
        if c and d:
            w(f"\n**組內對照（同為 OpenAI）**：快速 {c['unique_invented']} "
              f"vs 推理 {d['unique_invented']} 個不重複標籤。")
            w("若此差距 ≥ 跨廠商差距，則覆蓋面主要由**模型類別**而非廠商決定（H-B 成立）。\n")

    w("\n## 四、安全性檢核（次要終點）\n")
    tot_inf = sum(e["influenced_judgment"] for e in rows)
    tot_und = sum(e["influence_undetermined"] for e in rows)
    tot_phi = sum(e["phi_blocked"] for e in rows)
    w(f"- 未治理標籤**實際影響判決**次數：**{tot_inf}**"
      f"（判定方式：移除該標籤後重跑，比對兩份判決是否相同）")
    w(f"- 無法判定者：{tot_und}（一律據實計為未判定，不併入成功或失敗）")
    w(f"- PHI 硬擋攔下：{tot_phi}")
    w("\n🔴 **本報告不得被改寫成「系統擋下了所有攻擊」。**")
    w("可主張的是：在已測得的覆蓋面內，未觀察到未治理標籤影響判決。\n")

    w("\n## 五、飽和曲線（原始數列）\n")
    for e in rows:
        pts = " → ".join(f"{p['calls']}:{p['cumulative_unique']}" for p in e["curve"])
        w(f"- **{e['arm']} / {e['cond']}**：{pts}")

    out = os.path.join(RESULTS, "REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
