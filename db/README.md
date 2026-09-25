# db · 数据库

依据：锁定版数据库结构（2026-09-25）+ 2026-09-25 增补（`dream_subjects`）。

| 文件 | 内容 |
|---|---|
| `schema.sql` | 建库语句（8 张表 + 索引 + `pg_trgm`） |
| `data/dream_topics.csv` | 一级目录 A–Z（26 行） |

## 信息架构（IA，已冻结）

```
A–Z  →  Subject  →  Scene
/a       /apple      /apple/eat-apple
```

## 8 张表

| # | 表 | 层 | 说明 |
|---|---|---|---|
| 1 | `dream_topics` | 一级 | A–Z，共 26 行 |
| 2 | `dream_subjects` | 二级 | 主体（aardvark / apple / dog…）★新增 |
| 3 | `dream_scenes` | 三级 | 具体梦境页面（最核心） |
| 4 | `dream_scene_aliases` | — | 搜索别名（只人工确认后加） |
| 5 | `search_terms` | — | 搜索词归一库 |
| 6 | `dream_nearby` | — | 相关梦境关系 |
| 7 | `search_logs` | — | 搜索日志 |
| 8 | `dream_submissions` | — | 用户提交的梦境 |

## 核心原则

- 页面是提前写好的成品，数据库只帮用户找到页面
- 结构化字段只用于搜索匹配/排序，不是知识库
- 正常搜索不调 AI
- 归一化不丢颜色/动作/地点/状态
- Alias 禁止自动写入

## 抽取模型通道（实测可用）

```
POST https://matrixllm.alipay.com/v1/chat/completions
Authorization: Bearer PLACEHOLDER      ← 沙箱代理自动注入真凭证
model: deepseek-v4.1-flash
```
