#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
finalize.py —— 给 CSV 分配 id / subject_id，让它们能直接导入数据库

- dream_subjects.csv: id = 1..N（按首次出现顺序）；topic_id = slug 首字母对应字母 id
- dream_scenes.csv:   id = 1..M；subject_id = 对应 subject 的 id；topic_id = 同上
用法: python3 finalize.py
"""
import csv, os

DB = '/home/admin/.openclaw/workspace/scene-master/db/data'
LID = {chr(96+i):i for i in range(1,27)}

def load(p):
    with open(os.path.join(DB,p),encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def save(p, header, rows):
    with open(os.path.join(DB,p),'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

# ---- subjects ----
subs=load('dream_subjects.csv')
sub_id={}; sub_rows=[]
for i,r in enumerate(subs,1):
    slug=r['slug']
    if slug in sub_id: continue          # 去重
    sub_id[slug]=i
    tid=LID.get(slug[:1].lower())
    sub_rows.append([i, tid, r['name'], slug, r['title'] or r['name'].title(), r.get('description',''), r.get('status') or 1])
save('dream_subjects.csv', ['id','topic_id','name','slug','title','description','status'], sub_rows)

# ---- scenes ----
scs=load('dream_scenes.csv')
sc_rows=[]; n=0
for r in scs:
    sslug=(r['full_path'].strip('/').split('/')[0]) if r['full_path'] else ''
    sid=sub_id.get(sslug)
    if sid is None:                      # subject 没有对应行 → 补一个
        sid=len(sub_rows)+1; sub_id[sslug]=sid
        sub_rows.append([sid, LID.get(sslug[:1].lower()), sslug, sslug, sslug.title(), '', 1])
    n+=1
    sc_rows.append([n, sid, LID.get(sslug[:1].lower())] + [r[c] for c in
        ['title','slug','full_path','main_object','action','target','color','location',
         'size_modifier','other_modifier','context','status']])
save('dream_scenes.csv', ['id','subject_id','topic_id','title','slug','full_path','main_object','action',
    'target','color','location','size_modifier','other_modifier','context','status'], sc_rows)
save('dream_subjects.csv', ['id','topic_id','name','slug','title','description','status'], sub_rows)

print(f"subjects: {len(sub_rows)} 行（id 1..{len(sub_rows)}）")
print(f"scenes  : {len(sc_rows)} 行（id 1..{len(sc_rows)}）")
# 校验 FK
bad=[r for r in sc_rows if r[1] not in {s[0] for s in sub_rows}]
print("FK 校验:", "全部连得上 ✅" if not bad else f"❌ {len(bad)} 条连不上")