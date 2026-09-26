#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py —— 05 DreamMoods → dream_subjects / dream_scenes

一条一条，慢但准：抽取(deepseek-v4.1-flash) → 后处理 → 校验(glm-5.3) → 写入
- temperature=0（可复现）
- 多 worker 并发（默认 4）
- dream_scenes.csv 列 == 表结构（不含 terms）；terms 另存 scene_terms.csv
- id / subject_id 由 finalize 步骤统一分配（见 finalize.py）

用法: python3 extract.py --letter a --all --write --workers 4
"""
import json, re, os, time, urllib.request, argparse, csv, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = '/home/admin/.openclaw/workspace'
SRC  = os.path.join(ROOT, '新版素材/05_dreammoods')
DB   = os.path.join(ROOT, 'scene-master/db/data')
URL  = 'https://matrixllm.alipay.com/v1/chat/completions'
KEY  = 'PLACEHOLDER'
M_EXTRACT = 'deepseek-v4.1-flash'
M_CHECK   = 'glm-5.3'

FIELDS = ['main_object','action','target','color','location','size_modifier','other_modifier','context']
LOCK = threading.RLock()   # 可重入，避免 with LOCK 内再调 append_csv 死锁

SYS_EXTRACT = """你是一个梦境场景抽取助手。严格按下面规则工作，不要发挥。

【硬性规则】
1. 一个具体场景 = 一个独立结果。能拆就拆。
2. 有修饰差异、动作差异、对象差异、地点差异 → 必须分成多行。
3. 禁止合并成宽泛页面。
4. 只输出场景身份，禁止输出任何解梦解释、吉凶、心理分析。
5. 字段说明：
   - H1：**搜索导向的自然语义英文标题**。先看懂原文是哪个独立梦境，再用用户真会搜的自然英文写。
     **禁止套模板（如一律 Dream About X），也禁止套死句式。** 去掉 "To dream that" / "Dream of" 前缀。
     主体词是搜索核心词，自然允许时尽量靠前，但不强制。
   - Subject：小写英文、单数，= 梦里真正的主角名词。
     **禁止用 you / person / someone / something / others / thing / object 当 subject。**
     身体部位/从属物归主体；独立物体才独立；角色/身份类归主体。
   - 以下 8 个搜索字段，**填不出就写 null**（不要编）：
     main_object（梦见的东西，**必须与 Subject 完全一致**）、action（做了什么，动词原形）、
     target（对谁；**只要梦里有"你"参与，就必须填 you**）、color（颜色）、
     location（地点/身体部位）、size_modifier（大小形态）、other_modifier（其它限定）、
     context（情境，如 sleeping）。
   - **h1 里出现的动作词必须落到 action**：
     如 h1 写 "Seeing X in a Dream" → action=see；"Eating X in a Dream" → action=eat；"Wearing X" → action=wear。
   - 所有字段一律：小写、单数、动词原形（bite 不写 bites/biting；dog 不写 dogs）；
     复合修饰不拆（two-headed）；**字段里不能有空格**（多词用连字符，如 in ruins → in-ruins）。

【示例】
原文：To see an aardvark in your dream indicates that you are being very secretive.
输出：
H1: Dream About Aardvark
Subject: aardvark
Main Object: aardvark
Action: null
Target: null
Color: null
Location: null
Size Modifier: null
Other Modifier: null
Context: null

原文：To dream that you are using an abacus indicates that you are working hard on a problem.
输出：
H1: Using an Abacus in a Dream
Subject: abacus
Main Object: abacus
Action: use
Target: you
Color: null
Location: null
Size Modifier: null
Other Modifier: null
Context: null

原文：To dream that a dog bites you on the leg suggests that you have lost your balance. If the dog is black, it means a friend's dark side.
输出：
H1: Dog Bites You in a Dream
Subject: dog
Main Object: dog
Action: bite
Target: you
Color: null
Location: leg
Size Modifier: null
Other Modifier: null
Context: null

H1: Black Dog in a Dream
Subject: dog
Main Object: dog
Action: null
Target: null
Color: black
Location: null
Size Modifier: null
Other Modifier: null
Context: null

【输出格式】每个场景一块，不要多余文字：
H1: ...
Subject: ...
Main Object: ...
Action: ...
Target: ...
Color: ...
Location: ...
Size Modifier: ...
Other Modifier: ...
Context: ...

【任务】从下面原文中提取所有可成为独立长尾页面的具体梦境场景，并填好字段。
原文：
\"\"\"
{raw_text}
\"\"\"
"""

SYS_CHECK = """你是数据校验员，只做判定，不改写。按规则找错，找不到错就判 ok，不要自己造错。
规则：
1. subject 必须是梦里真正的主角名词（小写、无复数）。只有 subject 禁止用 you/person/someone/something/others/thing/object 这类占位词。
2. h1 必须是「搜索导向的自然语义标题」：自然、准确、像用户会搜的英文。
   - 若所有 h1 都用同一模板（如全是 Dream About X）→ 判错。
   - 若 h1 与原文描述的不是同一个梦境 → 判错。
   - 注意：主体词不在最前面不算错。
3. 8 个搜索字段必须与 h1 一致：h1 里出现的关键信息（动作/颜色/地点/对象）必须落到对应字段。
   - 例：h1 "Eating Abalone in a Dream" → action 必须是 eat，不能是 null。
   - **只要梦里有"你"参与，target 应为 you；纯"看见/状态"类 target 可为 null。**
   - 字段里不能有空格；词形归一（无复数、无 -ing/-ed）。
4. subject 与 h1 必须一致：若 h1 说的是 A、subject 却是别的词，判错。
5. 禁止解梦解释/吉凶/心理分析混进任何字段。
只输出 JSON：{"ok": true 或 false, "errors": ["..."]}"""

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
    # ① 先试 JSON（模型有时回 JSON）
    for a,b in (('[',']'),('{','}')):
        i=t.find(a); j=t.rfind(b)
        if i!=-1 and j>i:
            try:
                o=json.loads(t[i:j+1])
                objs=o if isinstance(o,list) else [o]
                rs=[x for x in (_rec_from_dict(y) for y in objs if isinstance(y,dict)) if x]
                if rs: return rs
            except Exception: pass
    # ② 行格式 H1:/Subject:/...
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
        r['main_object']=subn   # 强制与 subject 一致
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
        new = not os.path.exists(path)
        with open(path,'a',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f)
            if new: w.writerow(header)
            w.writerows(rows)

def verify(row):
    """返回 (是否通过, 错误文本)"""
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

def build_row(s, eterm):
    sub=s['subject']; sslug=slugify(sub); ss=slugify(s['h1'])
    row=dict(s); row['subject_slug']=sslug; row['letter']=sub[:1].upper()
    row['slug']=ss; row['full_path']=f"/{sslug}/{ss}"; row['terms']=derive_terms(s)
    return row

def process_entry(e, stats):
    raw="\n".join(p['text'] for p in e['paras'])
    out=call(M_EXTRACT,SYS_EXTRACT,raw,max_tokens=100000)
    scenes=parse_blocks(out)
    # 抽空（模型把 token 烧在思考上 / 返回空）→ 不标记完成，稍后重跑
    if not scenes:
        with LOCK:
            print(f"   ⚠ 抽空(模型无输出) 不标记完成: {e['term']}", flush=True)
            stats['empty']+=1
        return e['term'], [], False
    # 结构规则（机械，不是判断）：字母本身的词条 → subject = 该字母（用户 2026-09-25 冻结）
    is_letter = bool(re.fullmatch(r'[A-Za-z]', e['term'].strip()))
    if is_letter:
        L=e['term'].strip().lower()
        for s in scenes:
            s['subject']=L; s['main_object']=L
    good=[]
    for s in scenes:
        row=build_row(s, e['term'])
        passed, msg = verify(row)
        # 未过 → 把错误喂回模型，让它改（最多再试 1 次）
        for _ in range(1):
            if passed is not False: break
            try:
                fix=call(M_EXTRACT,REPAIR_SYS,
                    f"被拒结果：\n{json.dumps(row,ensure_ascii=False)}\n\n拒绝原因：\n{msg}\n\n原文：\n{raw}",
                    max_tokens=100000)
                fx=parse_blocks(fix)
            except Exception:
                fx=[]
            if not fx: break
            s2=fx[0]
            if is_letter: s2['subject']=s['subject']; s2['main_object']=s['subject']
            elif not s2.get('subject'): s2['subject']=s['subject']; s2['main_object']=s['subject']
            row=build_row(s2, e['term'])
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
                    [[ '05 DreamMoods', e['term'], row['h1'], row['full_path'], str(msg)[:400] ]])
            continue
        with LOCK: print(f"   ✓ {row['slug']}", flush=True)
        good.append(row)
    return e['term'], good, True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--letter',required=True); ap.add_argument('--limit',type=int,default=3)
    ap.add_argument('--start',type=int,default=0); ap.add_argument('--write',action='store_true')
    ap.add_argument('--all',action='store_true'); ap.add_argument('--workers',type=int,default=4)
    a=ap.parse_args()
    data=json.load(open(os.path.join(SRC,f"{a.letter.lower()}.json")))
    entries=[e for e in data if e.get('paras')]
    sel=entries if a.all else entries[a.start:a.start+a.limit]
    prog_path=os.path.join(DB,f"_progress_{a.letter.lower()}.json")
    done=set(json.load(open(prog_path))) if os.path.exists(prog_path) else set()
    sel=[e for e in sel if e['term'] not in done]
    seen=set(); sp=os.path.join(DB,'dream_subjects.csv')
    if os.path.exists(sp):
        with open(sp,encoding='utf-8-sig') as f:
            for r in list(csv.reader(f))[1:]:
                if len(r)>3: seen.add(r[3])
    seen_paths=set()
    scp=os.path.join(DB,'dream_scenes.csv')
    if os.path.exists(scp):
        with open(scp,encoding='utf-8-sig') as f:
            for r in csv.DictReader(f): seen_paths.add(r['full_path'])
    stats={'entries':0,'scenes':0,'rejected':0,'failed':0,'empty':0}
    print(f"待处理 {len(sel)} 词条，{a.workers} 并发", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs={ex.submit(process_entry,e,stats):e for e in sel}
        for fu in as_completed(futs):
            e=futs[fu]
            try: term, good, ok = fu.result()
            except Exception as ex2:
                print(f"   ✖ 词条失败 {e['term']}: {ex2}", flush=True); stats['failed']+=1; continue
            if a.write:
                for row in good:
                    if row['full_path'] in seen_paths:
                        print(f"   ↺ 已存在，跳过 {row['full_path']}", flush=True); continue
                    seen_paths.add(row['full_path'])
                    sslug=row['subject_slug']
                    if sslug not in seen:
                        seen.add(sslug)
                        append_csv(sp,['id','topic_id','name','slug','title','description','status'],
                            [[ '', None, row['subject'], sslug, row['subject'].title(), '', 1 ]])
                    append_csv(os.path.join(DB,'dream_scenes.csv'),
                        ['id','subject_id','topic_id','title','slug','full_path']+FIELDS+['status'],
                        [[ '', '', None, row['h1'], row['slug'], row['full_path']]
                         + [row[f] or '' for f in FIELDS] + [0]])
                    append_csv(os.path.join(DB,'scene_terms.csv'),
                        ['full_path','terms'], [[ row['full_path'], row['terms'] ]])
            if ok:
                done.add(term); stats['entries']+=1
                stats['scenes']+=len(good)
                if a.write: json.dump(sorted(done),open(prog_path,'w'),ensure_ascii=False)
            print(f"   └ [{stats['entries']}/{len(sel)}] {term}  (scenes={stats['scenes']})", flush=True)
    print("="*70); print("完成:",stats, flush=True)

if __name__=='__main__': main()