#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py —— 05 DreamMoods → Scene Master → dream_subjects / dream_scenes
一条一条，慢但准：抽取(deepseek-v4.1-flash) → 后处理 → 校验(glm-5.3) → 写入

口径依据：SPEC/SCENE_MASTER_v1.1_补充规则.md（补充 C：H1 语义生成，禁止模板）
用法: python3 extract.py --letter a --limit 3 [--start 0] [--write]
"""
import json, re, os, time, urllib.request, argparse, csv

ROOT = '/home/admin/.openclaw/workspace'
SRC  = os.path.join(ROOT, '新版素材/05_dreammoods')
DB   = os.path.join(ROOT, 'scene-master/db/data')
URL  = 'https://matrixllm.alipay.com/v1/chat/completions'
KEY  = 'PLACEHOLDER'
M_EXTRACT = 'deepseek-v4.1-flash'
M_CHECK   = 'glm-5.3'

SYS_EXTRACT = """你是一个梦境场景抽取助手。严格按下面规则工作，不要发挥。

【硬性规则】
1. 一个具体场景 = 一个独立结果。能拆就拆。
2. 有修饰差异、动作差异、对象差异、地点差异 → 必须分成多行。
3. 禁止合并成宽泛页面。
4. 只输出场景身份，禁止输出任何解梦解释、吉凶、心理分析。
5. 三个字段：
   - h1：**搜索导向的自然语义英文标题**。
     先看懂原文到底是哪个独立梦境，再用用户真会搜的自然英文写出来。
     **禁止套模板（如一律 Dream About X），也禁止套死句式。**
     主体词是搜索核心词，自然允许时尽量靠前，但不强制。
     去掉 "To dream that" / "Dream of" 等前缀。
   - subject：小写英文、单数，= 梦里真正的主角名词。
     **禁止用 you / person / someone / something / others / thing 当 subject。**
     身体部位/从属物归主体；独立物体才独立；角色/身份类归主体。
   - terms：小写英文，逗号分隔，**绝对不能有空格**。必须包含 subject。
     人物关系用 you；对象是别人：泛指复数写 people，明确第三人写具体名词（child），不确定才用 someone。
     词形已归一（bite 不写 bites/biting；dog 不写 dogs）。复合修饰不拆（two-headed）。虚词/介词默认不进。

【示例】
原文：To see an aardvark in your dream indicates that you are being very secretive.
输出：
H1: Dream About Aardvark
Subject: aardvark
Terms: aardvark

原文：To dream that you are using an abacus indicates that you are working hard on a problem.
输出：
H1: Using an Abacus in a Dream
Subject: abacus
Terms: abacus,use,you

原文：To dream that a dog bites you on the leg suggests that you have lost your balance.
输出：
H1: Dog Bites You in a Dream
Subject: dog
Terms: dog,bite,you,leg

【输出格式】每个场景一块，不要多余文字：
H1: ...
Subject: ...
Terms: ...

【任务】从下面原文中提取所有可成为独立长尾页面的具体梦境场景。
原文：
\"\"\"
{raw_text}
\"\"\"
"""

SYS_CHECK = """你是数据校验员，只做判定，不改写。按规则找错，找不到错就判 ok，不要自己造错。
规则：
1. subject 必须是梦里真正的主角名词（小写、无复数）。**只有 subject** 禁止用 you/person/someone/something/others/thing 这类占位词。
2. h1 必须是「搜索导向的自然语义标题」：自然、准确、像用户会搜的英文。
   - 若所有 h1 都用同一模板（如全是 Dream About X）→ 判错。
   - 若 h1 与原文描述的不是同一个梦境 → 判错。
   - 注意：**主体词不在最前面不算错**（主语优先只是倾向）。
3. terms 必须含 subject；不能有空格；词形归一（无复数、无 -ing/-ed）。
   **terms 里出现 you / people / child / someone 是允许的（人物关系），绝对不算错。**
4. 禁止解梦解释/吉凶/心理分析混进 h1 或 terms。
只输出 JSON：{"ok": true 或 false, "errors": ["..."]}"""

def call(model, sys_msg, user_msg, max_tokens=4000):
    body = json.dumps({"model":model,"messages":[{"role":"system","content":sys_msg},
        {"role":"user","content":user_msg}],"max_tokens":max_tokens}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type":"application/json","Authorization":"Bearer "+KEY})
    last=None
    for i in range(3):
        try:
            d=json.load(urllib.request.urlopen(req,timeout=200))
            return d['choices'][0]['message'].get('content','').strip()
        except Exception as e:
            last=e; time.sleep(3)
    raise last

DROP={'a','an','the'}
def slugify(s):
    s=(s or '').lower().replace("'","").strip()
    s=re.sub(r"[^a-z0-9]+","-",s).strip('-')
    parts=s.split('-'); out=[]
    for i,p in enumerate(parts):
        if p in DROP and i!=len(parts)-1: continue   # 末尾的 a 可能是字母 A，不删
        out.append(p)
    return '-'.join(out) or s

def norm_terms(t):
    t=(t or '').lower()
    t=re.sub(r"\s+","-",t)
    t=re.sub(r"-+","-",t)
    return ','.join(x.strip('-') for x in t.split(',') if x.strip('-'))

def parse_blocks(text):
    out=[]
    for blk in re.split(r'\n\s*\n', text):
        h1=sub=ter=None
        for line in blk.splitlines():
            m=re.match(r'\s*H1\s*[:：]\s*(.+)',line,re.I)
            if m: h1=m.group(1).strip()
            m=re.match(r'\s*Subject\s*[:：]\s*(.+)',line,re.I)
            if m: sub=m.group(1).strip().lower()
            m=re.match(r'\s*Terms\s*[:：]\s*(.+)',line,re.I)
            if m: ter=m.group(1).strip()
        if h1 and sub and ter: out.append({"h1":h1,"subject":sub,"terms":ter})
    return out

def append_csv(path, header, rows):
    new = not os.path.exists(path)
    with open(path,'a',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f)
        if new: w.writerow(header)
        w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--letter',required=True); ap.add_argument('--limit',type=int,default=3)
    ap.add_argument('--start',type=int,default=0); ap.add_argument('--write',action='store_true')
    a=ap.parse_args()
    data=json.load(open(os.path.join(SRC,f"{a.letter.lower()}.json")))
    entries=[e for e in data if e.get('paras')][a.start:a.start+a.limit]
    LID={chr(96+i):i for i in range(1,27)}
    seen_subjects=set()
    for e in entries:
        raw="\n".join(p['text'] for p in e['paras'])
        print("="*70); print("【词条】", e['term'])
        scenes=parse_blocks(call(M_EXTRACT,SYS_EXTRACT,raw))
        for s in scenes:
            sub=s['subject']; sslug=slugify(sub)
            ss=slugify(s['h1']); terms=norm_terms(s['terms'])
            row={"subject":sub,"subject_slug":sslug,"letter":sub[:1].upper(),
                 "topic_id":LID.get(sub[:1].lower()),"h1":s['h1'],"slug":ss,
                 "full_path":f"/{sslug}/{ss}","terms":terms}
            print(json.dumps(row,ensure_ascii=False))
            chk=call(M_CHECK,SYS_CHECK,json.dumps(row,ensure_ascii=False),max_tokens=8000)
            if '"ok"' not in chk.replace(' ','').lower():
                chk=call(M_CHECK,SYS_CHECK,json.dumps(row,ensure_ascii=False),max_tokens=12000)
            print("   校验:",chk.replace("\n"," ")[:300])
            if '"ok":true' not in chk.replace(' ','').lower():
                print("   ⛔ 校验未过，跳过写入"); continue
            if a.write:
                if sslug not in seen_subjects:
                    seen_subjects.add(sslug)
                    append_csv(os.path.join(DB,'dream_subjects.csv'),
                        ['id','topic_id','name','slug','title','description','status'],
                        [[ '', row['topic_id'], sub, sslug, sub.title(), '', 1 ]])
                append_csv(os.path.join(DB,'dream_scenes.csv'),
                    ['id','subject_id','topic_id','title','slug','full_path','main_object','action','target',
                     'color','location','size_modifier','other_modifier','context','status'],
                    [[ '', '', row['topic_id'], s['h1'], ss, row['full_path'], sub, '', '', '', '', '', '', '', 0 ]])

if __name__=='__main__': main()
