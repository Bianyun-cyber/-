#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract07.py —— 07 AuntyFlo → dream_subjects / dream_scenes

和 05 的差别：**必须按内容合并去重**（用户 2026-09-25 明确）
  候选场景 → 先和"已有梦境（含 05 与本次 07 新增）"做**语义**比对
  → 同一个梦（主体/动作/对象/关键修饰都一致）→ 不建新页，记 merge_log
  → 不是同一个梦 → 正常建
注意：**不按名字去重**，由模型看内容语义判断。

用法: python3 extract07.py --letter a --all --write --workers 8
"""
import json, re, os, time, urllib.request, argparse, csv, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = '/home/admin/.openclaw/workspace'
SRC  = os.path.join(ROOT, '新版素材/07_auntyflo')
DB   = os.path.join(ROOT, 'scene-master/db/data')
URL  = 'https://matrixllm.alipay.com/v1/chat/completions'
KEY  = 'PLACEHOLDER'
M_EXTRACT = 'deepseek-v4.1-flash'
M_CHECK   = 'glm-5.3'
M_DEDUP   = 'glm-5.3'

FIELDS = ['main_object','action','target','color','location','size_modifier','other_modifier','context']
LOCK = threading.RLock()   # 可重入，避免 with LOCK 内再调 append_csv 死锁

SYS_EXTRACT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'extract.py'),encoding='utf-8').read().split('SYS_EXTRACT = """')[1].split('"""')[0]
SYS_CHECK   = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'extract.py'),encoding='utf-8').read().split('SYS_CHECK = """')[1].split('"""')[0]

SYS_DEDUP = """你是梦境去重员。判断【候选梦境】是否与【已有梦境】中的某一条，是**同一个梦**。

判"同一个梦"只看**内容语义**，不看名字、不看措辞：
- 主体、动作、对象、以及关键的颜色/地点/形态 都一致 → 同一个梦。
- 只是同主题但画面不同（"狗咬你" vs "狗追你"；"黑狗" vs "白狗"）→ 不是同一个。
- 措辞/语言不同但形容同一个画面 → 是同一个。

只输出 JSON（不要解释）：{"same": true 或 false, "match": <已有梦境编号 或 null>}
"""

def call(model, sys_msg, user_msg, max_tokens=4000, temperature=0.0):
    body = json.dumps({"model":model,"temperature":temperature,
        "messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],
        "max_tokens":max_tokens}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type":"application/json","Authorization":"Bearer "+KEY})
    last=None
    for i in range(3):
        try:
            d=json.load(urllib.request.urlopen(req,timeout=240))
            return d['choices'][0]['message'].get('content','').strip()
        except Exception as e:
            last=e; time.sleep(4)
    raise last

DROP={'a','an','the'}
def slugify(s):
    s=(s or '').lower().replace("'","").strip()
    s=re.sub(r"[^a-z0-9]+","-",s).strip('-')
    parts=s.split('-'); out=[]
    for i,p in enumerate(parts):
        if p in DROP and i!=len(parts)-1: continue
        out.append(p)
    return '-'.join(out) or s

def norm_val(v):
    if v is None: return None
    v=str(v).strip().lower()
    if v in ('','null','none','n/a','-'): return None
    v=re.sub(r"\s+","-",v); v=re.sub(r"-+","-",v).strip('-')
    return v or None

def _rec_from_dict(d):
    def g(*ks):
        for k in ks:
            if k in d: return d[k]
        return None
    h1=g('h1','H1','title'); sub=g('subject','Subject')
    if not h1 or not sub: return None
    subn=norm_val(sub) or str(sub).strip().lower()
    r={'h1':str(h1).strip(),'subject':subn}
    for f in FIELDS:
        r[f]=norm_val(g(f, f.replace('_',' '), f.title()))
    r['main_object']=subn
    return r

def parse_blocks(text):
    t=(text or '').strip()
    for a,b in (('[',']'),('{','}')):
        i=t.find(a); j=t.rfind(b)
        if i!=-1 and j>i:
            try:
                o=json.loads(t[i:j+1])
                objs=o if isinstance(o,list) else [o]
                rs=[x for x in (_rec_from_dict(y) for y in objs if isinstance(y,dict)) if x]
                if rs: return rs
            except Exception: pass
    out=[]
    for blk in re.split(r'\n\s*\n', t):
        rec={}
        for line in blk.splitlines():
            m=re.match(r'\s*([A-Za-z0-9 ]+?)\s*[:：]\s*(.*)', line)
            if not m: continue
            rec[m.group(1).strip().lower().replace(' ','_')]=m.group(2).strip()
        h1=rec.get('h1'); sub=rec.get('subject')
        if not h1 or not sub: continue
        subn=norm_val(sub) or sub.strip().lower()
        r={'h1':h1,'subject':subn}
        for f in FIELDS: r[f]=norm_val(rec.get(f))
        r['main_object']=subn
        out.append(r)
    return out

def derive_terms(r):
    seen=[]
    for f in ['main_object','action','target','color','location','size_modifier','other_modifier','context']:
        v=r.get(f)
        if v and v not in seen: seen.append(v)
    if r['subject'] not in seen: seen.insert(0,r['subject'])
    return ','.join(seen)

def append_csv(path, header, rows):
    with LOCK:
        new=not os.path.exists(path)
        with open(path,'a',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f)
            if new: w.writerow(header)
            w.writerows(rows)

def desc(r):
    parts=[r.get('h1','')]
    fs=[f"{f}={r[f]}" for f in FIELDS if r.get(f)]
    return parts[0]+"  ["+", ".join(fs)+"]"

def verify(row):
    msg=json.dumps(row,ensure_ascii=False)
    try:
        chk=call(M_CHECK,SYS_CHECK,msg,max_tokens=100000)
        if '"ok"' not in chk.replace(' ','').lower():
            chk=call(M_CHECK,SYS_CHECK,msg,max_tokens=100000)
    except Exception as ex:
        return None, str(ex)
    return ('"ok":true' in chk.replace(' ','').lower()), chk

REPAIR_SYS = """你是梦境场景修正员。下面一条抽取结果被校验员拒了。
请**只重出这一条**（同样格式），修正指出的问题。不要增加或减少场景。
格式：H1 / Subject / Main Object / Action / Target / Color / Location / Size Modifier / Other Modifier / Context（填不出写 null）。
只输出这一条的字段，不要多余文字。"""

def build_row(s):
    sub=s['subject']; sslug=slugify(sub); ss=slugify(s['h1'])
    row=dict(s); row['subject_slug']=sslug; row['slug']=ss
    row['full_path']=f"/{sslug}/{ss}"; row['terms']=derive_terms(s)
    return row

def process_entry(e, stats):
    raw="\n".join(p['text'] for p in e['paras'])
    out=call(M_EXTRACT,SYS_EXTRACT,raw,max_tokens=100000)
    scenes=parse_blocks(out)
    if not scenes:
        with LOCK: print(f"   ⚠ 抽空(模型无输出) 不标记完成: {e['term']}", flush=True); stats['empty']+=1
        return e['term'], [], False
    is_letter=bool(re.fullmatch(r'[A-Za-z]', e['term'].strip()))
    if is_letter:
        L=e['term'].strip().lower()
        for s in scenes: s['subject']=L; s['main_object']=L
    good=[]
    for s in scenes:
        row=build_row(s)
        passed, msg = verify(row)
        for _ in range(1):
            if passed is not False: break
            try:
                fix=call(M_EXTRACT,REPAIR_SYS,
                    f"被拒结果：\n{json.dumps(row,ensure_ascii=False)}\n\n拒绝原因：\n{msg}\n\n原文：\n{raw}",
                    max_tokens=100000)
                fx=parse_blocks(fix)
            except Exception: fx=[]
            if not fx: break
            s2=fx[0]
            if is_letter or not s2.get('subject'): s2['subject']=s['subject']; s2['main_object']=s['subject']
            row=build_row(s2)
            passed, msg = verify(row)
            if passed:
                with LOCK: print(f"   🔧 修复成功 {row['slug']}", flush=True)
                break
        if passed is None:
            with LOCK: print(f"   ✖ 校验失败 {row['slug']}: {msg}", flush=True); stats['failed']+=1
            continue
        if not passed:
            with LOCK:
                print(f"   ⛔ 未过 {row['slug']}:",str(msg).replace(chr(10),' ')[:200], flush=True)
                stats['rejected']+=1
                append_csv(os.path.join(DB,'rejected.csv'),
                    ['source','term','h1','full_path','reason'],
                    [[ '07 AuntyFlo', e['term'], row['h1'], row['full_path'], str(msg)[:400] ]])
            continue
        good.append(row)
    return e['term'], good, True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--letter',required=True); ap.add_argument('--limit',type=int,default=3)
    ap.add_argument('--start',type=int,default=0); ap.add_argument('--write',action='store_true')
    ap.add_argument('--all',action='store_true'); ap.add_argument('--workers',type=int,default=8)
    a=ap.parse_args(); L=a.letter.lower()
    data=json.load(open(os.path.join(SRC,f"{L}.json")))
    entries=[e for e in data if e.get('paras')]
    sel=entries if a.all else entries[a.start:a.start+a.limit]
    prog_path=os.path.join(DB,f"_progress07_{L}.json")
    done=set(json.load(open(prog_path))) if os.path.exists(prog_path) else set()
    sel=[e for e in sel if e['term'] not in done]
    # 已有梦境索引（按 main_object 分组）
    idx={}
    sp=os.path.join(DB,'dream_scenes.csv')
    if os.path.exists(sp):
        with open(sp,encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                idx.setdefault(r['main_object'],[]).append({'full_path':r['full_path'],'h1':r['title'],
                    **{k:r[k] for k in FIELDS}})
    seen=set()
    with open(os.path.join(DB,'dream_subjects.csv'),encoding='utf-8-sig') as f:
        for r in list(csv.reader(f))[1:]:
            if len(r)>3: seen.add(r[3])
    seen_paths=set()
    scp=os.path.join(DB,'dream_scenes.csv')
    if os.path.exists(scp):
        with open(scp,encoding='utf-8-sig') as f:
            for r in csv.DictReader(f): seen_paths.add(r['full_path'])
    stats={'entries':0,'scenes':0,'merged':0,'rejected':0,'failed':0,'empty':0}
    print(f"07 字母{L.upper()}：待处理 {len(sel)} 词条，{a.workers} 并发；已有梦境 {sum(len(v) for v in idx.values())} 条", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs={ex.submit(process_entry,e,stats):e for e in sel}
        for fu in as_completed(futs):
            e=futs[fu]
            try: term, good, ok = fu.result()
            except Exception as ex2:
                print(f"   ✖ 词条失败 {e['term']}: {ex2}", flush=True); stats['failed']+=1; continue
            for row in good:
                # ==== 按内容合并去重（不按名字）====
                cands=idx.get(row['main_object'],[])
                merged=False
                if cands:
                    lines="\n".join(f"{i}. {desc(c)}" for i,c in enumerate(cands,1))
                    msg=f"【候选梦境】\n{desc(row)}\n\n【已有梦境】\n{lines}\n\n候选是否与已有中的某一条是同一个梦？"
                    try:
                        d=call(M_DEDUP,SYS_DEDUP,msg,max_tokens=100000)
                        j=json.loads(d[d.find('{'):d.rfind('}')+1])
                    except Exception: j={"same":False,"match":None}
                    if j.get('same') and j.get('match'):
                        m=cands[int(j['match'])-1]
                        append_csv(os.path.join(DB,'merge_log.csv'),
                            ['source','candidate_h1','candidate_path','merged_into'],
                            [['07 AuntyFlo',row['h1'],row['full_path'],m['full_path']]])
                        print(f"   ⇄ 合并 [{row['slug']}] -> {m['full_path']}", flush=True)
                        merged=True; stats['merged']+=1
                if merged: continue
                if row['full_path'] in seen_paths:
                    print(f"   ↺ 已存在，跳过 {row['full_path']}", flush=True); continue
                seen_paths.add(row['full_path'])
                sslug=row['subject_slug']
                if a.write:
                    if sslug not in seen:
                        seen.add(sslug)
                        append_csv(os.path.join(DB,'dream_subjects.csv'),
                            ['id','topic_id','name','slug','title','description','status'],
                            [[ '', None, row['subject'], sslug, row['subject'].title(), '', 1 ]])
                    append_csv(os.path.join(DB,'dream_scenes.csv'),
                        ['id','subject_id','topic_id','title','slug','full_path']+FIELDS+['status'],
                        [[ '', '', None, row['h1'], row['slug'], row['full_path']]
                         + [row[f] or '' for f in FIELDS] + [0]])
                    append_csv(os.path.join(DB,'scene_terms.csv'),
                        ['full_path','terms'], [[ row['full_path'], row['terms'] ]])
                    idx.setdefault(row['main_object'],[]).append({'full_path':row['full_path'],
                        'h1':row['h1'], **{k:row[k] for k in FIELDS}})
                print(f"   ✓ {row['slug']}", flush=True); stats['scenes']+=1
            if ok:
                done.add(term); stats['entries']+=1
                if a.write: json.dump(sorted(done),open(prog_path,'w'),ensure_ascii=False)
    print("="*70); print("完成:",stats, flush=True)

if __name__=='__main__': main()