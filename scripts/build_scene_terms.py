#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_scene_terms.py —— scene_terms.csv → dream_scene_terms（可导入形状）

严格按 2026-09-26 冻结规则：
- 用 **full_path** 对接 dream_scenes（不是 scene_id，因为 id 由 finalize 按顺序重排）
- **全量重建**：产出完整的 dream_scene_terms.csv，供 TRUNCATE + INSERT（不做增量 upsert）
- 只放**英文标准词**（一个 term 一行）
- 派生数据：可随时删除重建

用法: python3 build_scene_terms.py
"""
import csv, os, collections

DB='/home/admin/.openclaw/workspace/scene-master/db/data'
def load(p):
    fp=os.path.join(DB,p)
    if not os.path.exists(fp): return []
    with open(fp,encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def save(p,hdr,rows):
    with open(os.path.join(DB,p),'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(hdr); w.writerows(rows)

scenes=load('dream_scenes.csv')
st=load('scene_terms.csv')
path2id={r['full_path']: r['id'] for r in scenes}
subject={r['full_path']: r['main_object'] for r in scenes}

rows=[]; miss=[]; noseq=0
for r in st:
    fp=r['full_path']; sid=path2id.get(fp)
    if not sid: miss.append(fp); continue
    seen=set()
    for t in (r.get('terms') or '').split(','):
        t=t.strip()
        if not t or t in seen: continue
        seen.add(t); rows.append([sid,t])

# 去重 (scene_id,term)（主键约束）
uniq={}
for sid,t in rows: uniq[(sid,t)]=1
rows=[[sid,t] for (sid,t) in uniq]

save('dream_scene_terms.csv',['scene_id','term'],rows)

# 校验
dups=len([k for k,v in collections.Counter((r[0],r[1]) for r in rows).items() if v>1])
no_term=[fp for fp in path2id if fp not in {r['full_path'] for r in st}]
# 每条 scene 是否含自己的 subject
by_scene=collections.defaultdict(set)
for sid,t in rows: by_scene[sid].add(t)
missing_subject=0
for r in scenes:
    sid=r['id']; terms=by_scene.get(sid,set())
    if terms and r['main_object'] not in terms: missing_subject+=1
print(f"scene: {len(scenes)} | terms 行: {len(rows)}")
print(f"未对上的 full_path（scene_terms 里有、scenes 里无）: {len(miss)}")
print(f"scene 没有 terms 行: {len(no_term)}")
print(f"scene 有 terms 但不含自身 subject: {missing_subject}")
print(f"(scene_id,term) 重复: {dups}")
print("均值每 scene 词数: %.2f" % (len(rows)/max(len(scenes),1)))