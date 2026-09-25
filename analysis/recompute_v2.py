"""Paper-4 tables, recomputed from results/*.jsonl with field semantics separated.

new_invented              = label strings the attacking model produced that are not in the
                            governed set  -> the COVERAGE endpoint (§3.7 primary 1)
ungoverned_reached_kernel = of those, the ones actually passed into kernel construction
                            -> the BOUND endpoint (§4.2)
"""
import sys
import os
import glob, json, sys, collections

# 受測內核未隨資料集釋出；路徑由環境變數指定。
# 釋出版的重算請改用 verify_released_dataset.py —— 它**完全不需要**內核。
for _v in ('HDKPS_KERNEL_PATH', 'HDKPS_BACKEND_PATH'):
    _p = os.environ.get(_v)
    if _p:
        sys.path.insert(0, _p)
from analytics.admissibility import _load_sspi_library
gov = set(_load_sspi_library())


def txt(t):
    return t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)


rows = []
union_inv = set()
for arm in 'ABCD':
    for cond in ('off', 'on'):
        inv = set()
        inv_inst = 0
        reach_inst = 0
        rej_inst = 0
        rej_trials = 0
        void = 0
        altered = 0
        parsed = 0
        recs = 0
        for L in open(f'results/{arm}_uplift-{cond}.jsonl', encoding='utf-8'):
            L = L.strip()
            if not L:
                continue
            d = json.loads(L)
            recs += 1
            if d.get('parsed'):
                parsed += 1
            for t in (d.get('new_invented') or []):
                s = txt(t)
                inv.add(s)
                union_inv.add(s)
                inv_inst += 1
            reach_inst += len(d.get('ungoverned_reached_kernel') or [])
            tr = d.get('tags_rejected') or []
            rej_inst += len(tr)
            if tr:
                rej_trials += 1
            if d.get('judgment_void'):
                void += 1
            if d.get('ungoverned_influenced_judgment') is True:
                altered += 1
        rows.append(dict(arm=arm, cond=cond, recs=recs, parsed=parsed,
                         pct=100.0 * parsed / recs, inv=len(inv), inv_inst=inv_inst,
                         rate=1000.0 * len(inv) / parsed, reach=reach_inst,
                         rej_inst=rej_inst, rej_trials=rej_trials, void=void,
                         altered=altered))

h = ('arm cond  recs  parsed  parse%  invDistinct  per1k  invInst  reachInst  rejInst '
     'rejTrials   void  altered')
print(h)
print('-' * len(h))
for r in rows:
    print(f"{r['arm']}   {r['cond']:<4}{r['recs']:6d}{r['parsed']:8d}{r['pct']:8.1f}"
          f"{r['inv']:13d}{r['rate']:7.1f}{r['inv_inst']:9d}{r['reach']:11d}"
          f"{r['rej_inst']:9d}{r['rej_trials']:10d}{r['void']:7d}{r['altered']:9d}")
print()
print(f'UNION distinct invented labels (all 8 runs) = {len(union_inv)}')
off = {r['arm']: r for r in rows if r['cond'] == 'off'}
on = {r['arm']: r for r in rows if r['cond'] == 'on'}
print()
print('coverage rate per 1,000 parsed trials (invented labels):')
for a in 'ABCD':
    print(f'   {a}: off {off[a]["rate"]:.1f}   on {on[a]["rate"]:.1f}')
fast = [off[a]['rate'] for a in 'ABC']
print(f'between-vendor (fast, off) spread = {max(fast)/min(fast):.2f}x  '
      f'({max(fast):.1f} / {min(fast):.1f})')
print(f'within-vendor  (C vs D, off)      = '
      f'{max(off["C"]["rate"], off["D"]["rate"])/min(off["C"]["rate"], off["D"]["rate"]):.2f}x')
fast_on = [on[a]['rate'] for a in 'ABC']
print(f'between-vendor (fast, on)  spread = {max(fast_on)/min(fast_on):.2f}x')
print(f'within-vendor  (C vs D, on)       = '
      f'{max(on["C"]["rate"], on["D"]["rate"])/min(on["C"]["rate"], on["D"]["rate"]):.2f}x')
print()
print(f'ratio between/within (off) = '
      f'{(max(fast)/min(fast)) / (max(off["C"]["rate"], off["D"]["rate"])/min(off["C"]["rate"], off["D"]["rate"])):.2f}')
