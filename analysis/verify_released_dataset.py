# -*- coding: utf-8 -*-
"""用**釋出用（已代碼化）**資料重算論文全部數字，並與稿件所載逐項比對。

代碼化若動到任何一個數字，這支會 exit 1。不讓錯的資料流出去。
本支只讀 02_Results_Released/ 與 governed_tokens.json——**不碰真實治理集**，
因此它同時證明了：外部讀者拿到的東西確實足以重算。
"""
from __future__ import annotations

import json
import os
import re
import sys
import collections

# 以本檔為基準定位，倉庫可在任何位置解開
REL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')

TOKEN_RE  = re.compile(r'^<GOV-\d{2}(?:~v\d+)?>$')      # 第①類：可直接解析
TOKEN_WS  = re.compile(r'^<GOV-\d{2}~ws\d+>$')          # 第②類：需去內部空白
PCOS_NORM = 'PCOS'


def norm_min(s: str) -> str:
    """釋出版的最小正規化：零寬剝除、NFKC、大小寫折疊、去頭尾空白。
    不含簡繁層（那需要治理詞彙，已withheld）。"""
    import unicodedata
    s = ''.join(c for c in s if c not in '\u200b\u200c\u200d\ufeff')
    return unicodedata.normalize('NFKC', s).strip().upper()


# 稿件所載（§4.1／§4.2／§4.3／§5.2）
EXPECT = {
    ('A', 'off'): dict(recs=19911, parsed=19752, inv=5515, guard=14967, reach=20259,
                       rej=0, void=0, alt=104),
    ('A', 'on'):  dict(recs=20000, parsed=19857, inv=5572, guard=15263, reach=0,
                       rej=16686, void=11375, alt=0),
    ('B', 'off'): dict(recs=4763, parsed=4660, inv=3221, guard=3977, reach=9085,
                       rej=0, void=0, alt=1),
    ('B', 'on'):  dict(recs=4742, parsed=4633, inv=3334, guard=4272, reach=0,
                       rej=7508, void=1261, alt=0),
    ('C', 'off'): dict(recs=20000, parsed=19309, inv=3619, guard=16591, reach=8484,
                       rej=0, void=0, alt=7),
    ('C', 'on'):  dict(recs=19999, parsed=19357, inv=3691, guard=16915, reach=0,
                       rej=7791, void=9692, alt=0),
    ('D', 'off'): dict(recs=2323, parsed=2304, inv=548, guard=2125, reach=1362,
                       rej=0, void=0, alt=2),
    ('D', 'on'):  dict(recs=2298, parsed=2274, inv=494, guard=2116, reach=0,
                       rej=1016, void=1244, alt=0),
}
EXPECT_UNION = 21123
EXPECT_GUARD = 76226
EXPECT_REACH_OFF = 39190
EXPECT_ALT = 114
EXPECT_CLASS = {'instances': 359, '1': 346, '2': 2, '3': 11}


def txt(t):
    return t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)


def main():
    fails = []
    union = set()
    guard_total = 0
    reach_off = 0
    alt_total = 0
    cls = collections.Counter()
    cls_inst = 0

    for arm in 'ABCD':
        for cond in ('off', 'on'):
            recs = parsed = guard = reach = rej = void = alt = 0
            inv = set()
            path = os.path.join(REL, f'{arm}_uplift-{cond}.jsonl')
            for line in open(path, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                recs += 1
                if d.get('parsed'):
                    parsed += 1
                for t in (d.get('new_invented') or []):
                    s = txt(t)
                    inv.add(s)
                    union.add(s)
                urk = d.get('ungoverned_reached_kernel') or []
                reach += len(urk)
                tr = d.get('tags_rejected') or []
                rej += len(tr)
                lf = d.get('locks_fired') or []
                if lf or tr:
                    guard += 1
                if d.get('judgment_void'):
                    void += 1
                if d.get('ungoverned_influenced_judgment') is True:
                    alt += 1
                    if cond == 'off':
                        for t in urk:
                            s = txt(t)
                            cls_inst += 1
                            if TOKEN_RE.match(s) or norm_min(s) == PCOS_NORM:
                                cls['1'] += 1
                            elif (TOKEN_WS.match(s)
                                  or norm_min(re.sub(r'\s+', '', s)) == PCOS_NORM):
                                cls['2'] += 1
                            else:
                                cls['3'] += 1
            guard_total += guard
            if cond == 'off':
                reach_off += reach
            alt_total += alt
            e = EXPECT[(arm, cond)]
            got = dict(recs=recs, parsed=parsed, inv=len(inv), guard=guard,
                       reach=reach, rej=rej, void=void, alt=alt)
            for k, v in e.items():
                if got[k] != v:
                    fails.append(f'{arm}/{cond} {k}: 稿件 {v} · 釋出資料重算 {got[k]}')
            print(f'{arm}/{cond:3s} recs={recs:6d} parsed={parsed:6d} inv={len(inv):5d} '
                  f'guard={guard:6d} reach={reach:6d} rej={rej:6d} void={void:6d} alt={alt:4d}')

    print()
    for label, got, want in [('聯集不重複標籤', len(union), EXPECT_UNION),
                             ('守衛接觸', guard_total, EXPECT_GUARD),
                             ('未界定到達內核', reach_off, EXPECT_REACH_OFF),
                             ('改變判決', alt_total, EXPECT_ALT),
                             ('§5 標籤實例', cls_inst, EXPECT_CLASS['instances']),
                             ('§5 第①類', cls['1'], EXPECT_CLASS['1']),
                             ('§5 第②類', cls['2'], EXPECT_CLASS['2']),
                             ('§5 第③類', cls['3'], EXPECT_CLASS['3'])]:
        ok = got == want
        print(f'{"OK " if ok else "🔴 "}{label}: 稿件 {want} · 重算 {got}')
        if not ok:
            fails.append(f'{label}: 稿件 {want} · 重算 {got}')

    print()
    if fails:
        print('🔴 釋出資料重算與稿件不符：')
        for f in fails:
            print('   ', f)
        sys.exit(1)
    print('>>> ✅ 釋出（代碼化）資料可完整重算稿件全部數字')


if __name__ == '__main__':
    main()
