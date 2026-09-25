# Scene Master v1.1 · 补充规则（冻结）

> 生效：2026-09-25（含 20:57 修订）
> 作用：在 v1.1 主规范（9 列不变）之上，补执行细则。**字段/列数一律不动。**

---

## 补充 A｜三层 IA 与"主体页"（★2026-09-25 修订）

结构：**A–Z（一级）→ Subject（二级）→ Scene（三级）**

```
/a                         ← A 字母总入口（只列 A 开头的 subject）
/aardvark                  ← Aardvark 主体入口页  ┐
/abacus                    ← Abacus 主体入口页    ├ 与 /a 平级（兄弟）
/abalone                   ← Abalone 主体入口页   ┘
/aardvark/dream-about-aardvark   ← 具体梦境（在主体下面）
```

- `/a` 与 `/aardvark` 是**兄弟**，不是父子。`/a` 只负责列 A 开头的 subject。
- `/aardvark`（主体页）对应数据库 **`dream_subjects`**，**不是 `dream_scenes` 的一行**。
- **原文只要有实际解释内容，就要产出独立 scene。**（旧规则"H1 == 主体词就不建 scene"**已作废**。）

## 补充 B｜subject 判定

- **subject = 用户梦里真正的主角名词。**
- 禁止用 `you / person / someone / something / others / thing` 这类**占位词**当 subject。
- 例：
  - 主角是狗 → `dog`；主角是狗粮 → `dog-food`；主角是狗窝 → `dog-house`；主角是山茱萸 → `dogwood`
  - 身体部位 / 从属物 → 归主体（`Snake Skin` → `snake`）
  - 角色 / 身份类 → 归主体（`Snake Charmer` → `snake`）

## 补充 C｜H1 命名（★2026-09-25 改版，最高优先级）

> **H1 采用搜索导向的自然语义生成。主体词属于搜索核心词，应在自然表达允许的情况下优先靠前，但"主语优先"不是固定句式，也不是硬性 H1 格式要求。禁止使用统一模板批量生成 H1。**

- Agent 顺序：**原文 → 这条到底描述哪个独立梦境 → 定 subject → 定 scene 核心语义 → 自然英文 H1 → slug → terms**
- 禁止两个极端：
  - ❌ 模板机器：一律 `Dream About X`
  - ❌ 句式机器：一律 `Subject + Action + Object`
- 示例：

| 原文 | H1（可以这样） |
|---|---|
| `To see an aardvark…` | `Dream About Aardvark` |
| `To dream that you are using an abacus…` | `Using an Abacus in a Dream` |
| `To dream that a dog bites you…` | `Dog Bites You in a Dream` / `Dog Bites You` |

## 补充 D｜terms 细则

- 人物关系：是「你」→ 统一 `you`；对象是别人 → 泛指复数写 `people`，明确第三人写具体名词（`child`），实在不确定才用 `someone`。
- 复合修饰：优先保留为一个词（`two-headed`，**不拆**成 `two,head`）。
- 动词：一律原形（`bathe` 不写 `bath` / `bathing`）；**词形已归一**（`dog` 不写 `dogs`）。
- 虚词/介词（`away`、`over`、`in` 等）默认**不进 terms**，除非是区分场景的关键语义。
- `terms` 必须包含 `subject`；**不能有空格**。

## 补充 E｜slug 细则

- **禁止撇号**；所有格 `'s` → `s`（`dog's` → `dogs`）。
- 只删 `a / an / the`，其余保留；**末尾的 `a`（可能是字母 A）不删**。

## 补充 F｜提示词与后处理

- 模型只输出：`H1` / `Subject` / `Terms`。
- `letter`、`slug`、`status`、`source` **全部后处理机械生成**，不交给模型。
  - `letter` = subject 首字母大写
  - `slug` = h1 转小写 → 空格变 `-` → 去撇号 → 只删 a/an/the
  - `status` = 新建默认 `0`（草稿）
  - `source` = 程序按来源填

## 补充 G｜判定总原则 + 边界案例

### G0. 总原则
> **这个词 / 这一拆，会不会影响用户认出「这就是我的梦」？** 会 → 收/拆；不会 → 别硬塞。

### G1. 主体页不是模型抽的
- 主体页（`/aardvark`）来自 `dream_subjects`；模型只抽 scene。
- 原文没有"看见 X"这种泛化句时，不必硬造；但仍要按原文实际内容产出 scene。

### G2–G4. （同前）
- 身体部位/从属物归主体；独立物体才独立；角色归主体。
- 泛指复数用 `people`；明确第三人用具体名词；`someone` 仅兜底。
- 不同画面拆两条；地点/状态等关键区分修饰收进 terms。

## 补充 H｜源站独立词条 ≠ 独立 subject
- 一律以我们的规则（G2）为准。例：源站有 `Haunted House` 独立词条，仍归 subject = `house`。
- 跨主体场景 → subject 归**词条主体 / 梦的核心对象**。
- 短语动词归一：`broken into` → `break`。

## 补充 I｜中文源专用（周公解梦等）
1. **判词劈两半**：中文判词 = 「梦境，主吉凶」。**只收前半**；后半（`主…`/`大吉`/`凶`）是解释，禁止入表。
2. **按场景身份去重**：多本古籍常重复收录同一场景 → 按**场景身份**去重，不按原文条数。
3. **主语**：动宾类补 `you`；看见/状态类按自然表达。
4. **标准词**：田地→`field`；耕=`plow`、种=`plant`、买=`buy`、卖=`sell`、置=`acquire`、修平=`level`、破败=`ruin`。
5. 主角是梦中人物的 → 归词条主体。

## 补充 J｜中文源·去重与拆分
1. **一条判词 ≠ 一个场景**：判词里常用 `梦X` / `梦用X` 一口气写 3–5 个梦 → **再拆**。
2. **去重键 = 场景身份**（subject + 动作 + 对象 + 修饰），同书跨书都要去。
3. **碎片检测**：断句残片（过短 / 以标点开头 / 缺主语）先扫一遍。
4. **h1 风格**：动作主体是你 → 可用 `You …`；主体是物 → 可 `X + 动词`（**但都不是硬模板**，见补充 C）。

---

## 补充 K｜"主语优先"的定位（★2026-09-25）

- **主语优先 = 搜索优化原则，不是 H1 句式规定。**
- 保留动机：用户常按「主体词 + 动作」搜（`dog bite dream`、`black dog dream`、`dog chase me`），主体词靠前利于命中。
- 强度：**倾向** —— 自然表达允许时靠前，不强制。
- **搜索能力不全压在 H1 上**：H1 负责自然、准确、可点击的标题；`terms` 负责把各种用户说法映射到页面。
- 呼应已冻结的搜索机制：**主体定栏 + 其他词命中一加一 + 同分并列 + 不替用户选择**。

---

## 附：抽取提示词（模型只出 3 字段）

```text
你是一个梦境场景抽取助手。严格按下面规则工作，不要发挥。

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
     禁止用 you / person / someone / something / others / thing 当 subject。
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
"""
{raw_text}
"""
```