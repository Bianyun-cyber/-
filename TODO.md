# TODO · 待统一处理（跑完 05 后）

> 2026-09-26 记录。**05 全量跑完后统一处理，不要在跑的过程中动手。**

## 1. 打回清单（`db/data/rejected.csv`，53 条）
glm-5.3 判不合规、自动修复也没救回来的。**05 跑完后跑一轮定向修复。**

原因分布（一条可能犯多项）：

| 条数 | 原因 | 例子 |
|---|---|---|
| 37 | subject 用了占位词（something / individual / objects…） | 词条 `Ascend` → subject=`something` |
| 11 | target 填错（纯观察类该 null 却填 you） | `Something Ascending` 未参与却填 you |
| 9 | 字段混入解梦解释 / 吉凶 / 心理分析 | `Begin` → context 塞了"你拖延浪费时间，要振作" |
| 5 | h1 有动作但 action 空 | `Seeing X` 没填 `see` |
| 4 | 词形没归一（复数） | subject=`objects` |
| 2 | subject 与 h1 不一致 | h1 "Bathing Someone" vs subject `individual` |

**重点**：第 1 类（占位词 subject，37 条）最大头 —— 定向修这一批。

## 2. 待重跑（自动，无需人工）
- **✖ 失败 421 条**：全是 HTTP 502（网关抽风），未标记完成 → 下一轮自动重跑。
- **⚠ 抽空 55 条**：模型把 token 烧在思考上、正文为空 → 未标记完成 → 自动重跑（token 已提到 10W）。

## 3. 字段留空待补
- `context`：允许为空，**不为填字段硬抽**；以后搜索/页面生成确实需要再补一轮。
- `western_content` / `chinese_content` / `quick_meaning` / `meta_*`：Page Content 层，**未写**。
- `dream_scene_aliases`：只能人工确认后加，**禁止自动写**。
- `search_terms`（中文别名）：以后用户会用中文搜，需单独一轮。

## 4. 流程待办
- **07 AuntyFlo**：待跑，**按内容语义合并去重**（不是只比名字）；命中记 `merge_log.csv`。
- 05 跑完后：`finalize.py`（分配 id）→ `dedupe.py`（清重复）→ `qa.py`（全量质检）。
- 日志已按天归档到 `logs/archive/`（避免再被覆盖）。
