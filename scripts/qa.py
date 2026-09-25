#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa.py —— 质量保险：跑完一批后，全量体检（不只看一条）

用法: python3 qa.py --letter a
检查项：
  ① 完整性：词条是否都处理过（没处理的列出来 → 要补跑）
  ② 重复：full_path / 同主体内 slug / h1
  ③ 必填：title / slug / full_path / main_object 是否为空
  ④ 一致性：full_path 是否 = /主体slug/场景slug；topic_id 是否 = 主体首字母
  ⑤ 外键：scene.subject_id 是否都能连上 subject
  ⑥ 覆盖：每条 scene 是否有 terms
  ⑦ 日志里的打回/失败
"""
import csv, json, os, re, argparse, collections

ROOT='/home/admin/.openclaw/workspace'
SRC=os.path.join(ROOT,'新版素材/05_dreammoods')
DB=os.path.join(ROOT,'scene-master/db/data')
LOG=os.path.join(ROOT,'scene-master/logs')

ap=argparse.ArgumentParser(); ap.add_argument('--letter',required=True); a=ap.parse_args()
L=a.letter.lower()
def load(p):
    fp=os.path.join(DB,p)
    if not os.path.exists(fp): return []
    with open(fp,encoding='utf-8-sig') as f: return list(csv.DictReader(f))
S=load('dream_subjects.csv'); C=load('dream_scenes.csv'); T=load('scene_terms.csv')
entries=[e for e in json.load(open(os.path.join(SRC,f"{L}.json"))) if e.get('paras')]
prog=set(json.load(open(os.path.join(DB,f"_progress_{L}.json")))) if os.path.exists(os.path.join(DB,f"_progress_{L}.json")) else set()

def head(t): print("\n"+"="*66+f"\n{t}\n"+"="*66)
def rep(t,items,n=15):
    print(f"[{t}] {len(items)}")
    for x in items[:n]: print("   -",x)

head(f"05 字母 {L.upper()} · 质量体检")
print(f"词条总数 {len(entries)} | 已处理 {len(prog)} | subjects {len(S)} | scenes {len(C)} | terms {len(T)}")

rep("① 没处理的词条（要补跑）", [e['term'] for e in entries if e['term'] not in prog])
rep("②a full_path 重复", [k for k,v in collections.Counter(x['full_path'] for x in C).items() if v>1])
rep("②b 同一主体内 slug 重复", [k for k,v in collections.Counter((x['main_object'],x['slug']) for x in C).items() if v>1])
rep("②c h1 重复", [k for k,v in collections.Counter(x['title'] for x in C).items() if v>1])
rep("③ 必填为空", [f"{x['full_path'] or '(no path)'} :: " + ",".join(f for f in ['title','slug','full_path','main_object'] if not x[f]) for x in C if not all(x[f] for f in ['title','slug','full_path','main_object'])])
def exp_path(x):
    ss=re.sub(r'[^a-z0-9]+','-',x['main_object'].lower()).strip('-')
    return f"/{ss}/{x['slug']}"
rep("④a full_path 与 主体slug/slug 不符", [f"{x['full_path']} 应为 {exp_path(x)}" for x in C if x['full_path']!=exp_path(x)])
LID={chr(96+i):i for i in range(1,27)}
rep("④b topic_id 与主体首字母不符", [f"{x['main_object']}->{x['topic_id']}" for x in C if x['topic_id'] and x['main_object'][:1].lower()!=chr(96+int(x['topic_id']))])
sids={x['id'] for x in S}
rep("⑤ scene.subject_id 连不上 subject", [x['full_path'] for x in C if x['subject_id'] and x['subject_id'] not in sids])
paths={x['full_path'] for x in C}; tpaths={x['full_path'] for x in T}
rep("⑥ scene 没有对应 terms", sorted(paths-tpaths)[:10])
rep("⑥b 孤立 terms（没有对应 scene）", sorted(tpaths-paths)[:10])
# ⑦ 日志
lf=os.path.join(LOG,f"extract_{L}.log")
if os.path.exists(lf):
    txt=open(lf,encoding='utf-8',errors='ignore').read()
    rej=[l.strip() for l in txt.splitlines() if '⛔' in l]
    fail=[l.strip() for l in txt.splitlines() if '✖' in l]
    rep("⑦ 被 glm-5.3 打回（需人工看）", rej, 20)
    rep("⑦b 抽取/校验失败（502 等，要补跑）", fail, 20)
