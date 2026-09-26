#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedupe.py —— 清理重复 & 路径不一致（跑完一批后收尾用）
1. full_path 重复 → 只留第一条
2. full_path 与 main_object/slug 不符 → 就地修正
3. 重建 scene_terms 对齐
用法: python3 dedupe.py
"""
import csv, os, re, collections

DB='/home/admin/.openclaw/workspace/scene-master/db/data'
F=['main_object','action','target','color','location','size_modifier','other_modifier','context']

def load(p):
    with open(os.path.join(DB,p),encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def save(p,hdr,rows):
    with open(os.path.join(DB,p),'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f); w.writerow(hdr); w.writerows(rows)

sc=load('dream_scenes.csv')
n0=len(sc)
# 1) 去重（full_path 相同只留第一条）
seen=set(); keep=[]
for r in sc:
    if r['full_path'] in seen: continue
    seen.add(r['full_path']); keep.append(r)
dups=n0-len(keep)

# 2) 路径修正
fixed=0
for r in keep:
    seg=r['full_path'].strip('/').split('/')[0]
    if seg!=r['main_object']:
        r['main_object']=seg; fixed+=1

save('dream_scenes.csv',['id','subject_id','topic_id','title','slug','full_path']+F+['status'],
     [[r['id'],r['subject_id'],r['topic_id'],r['title'],r['slug'],r['full_path']]+[r[f] for f in F]+[r['status']] for r in keep])

# 3) 重建 terms
def terms(r):
    out=[]
    for f in F:
        v=r[f]
        if v and v not in out: out.append(v)
    return ','.join(out)
save('scene_terms.csv',['full_path','terms'],[[r['full_path'],terms(r)] for r in keep])

# 4) 清掉没有 scene 的孤立 subject
paths={r['full_path'].strip('/').split('/')[0] for r in keep}
subs=load('dream_subjects.csv')
keep_subs=[s for s in subs if s['slug'] in paths]
save('dream_subjects.csv',['id','topic_id','name','slug','title','description','status'],
     [[s['id'],s['topic_id'],s['name'],s['slug'],s['title'],s.get('description',''),s['status']] for s in keep_subs])

print(f"scene: {n0} → {len(keep)}（去掉重复 {dups}）")
print(f"路径修正: {fixed}")
print(f"subject: {len(subs)} → {len(keep_subs)}（清掉无 scene 的 {len(subs)-len(keep_subs)}）")
