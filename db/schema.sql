-- ============================================================
-- 解梦知识库 · 建库语句（锁定版 2026-09-25 + 09-25/09-26 增补）
-- 共 9 张表：dream_topics / dream_subjects / dream_scenes / dream_scene_terms /
--            dream_scene_aliases / search_terms / dream_nearby / search_logs / dream_submissions
-- 依据：inbox/数据库等_锁定版20260925.txt
-- 增补：新增 dream_subjects（IA 第二层：A–Z → Subject → Scene）
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. dream_topics（一级目录：A–Z，共 26 行）
CREATE TABLE dream_topics (
    id          BIGSERIAL     PRIMARY KEY,
    name        VARCHAR(80)   NOT NULL,      -- A
    slug        VARCHAR(100)  NOT NULL UNIQUE, -- a
    title       VARCHAR(150)  NOT NULL,
    description TEXT,
    status      SMALLINT      NOT NULL DEFAULT 1,
    created_at  TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dream_topics_name_lower ON dream_topics (LOWER(name));
CREATE INDEX idx_dream_topics_status     ON dream_topics (status);

-- 2. dream_subjects（二级：主体，如 aardvark / apple / dog）★新增
CREATE TABLE dream_subjects (
    id          BIGSERIAL     PRIMARY KEY,
    topic_id    BIGINT        NOT NULL REFERENCES dream_topics(id),
    name        VARCHAR(80)   NOT NULL,      -- aardvark
    slug        VARCHAR(100)  NOT NULL UNIQUE, -- aardvark  →  URL /aardvark
    title       VARCHAR(150)  NOT NULL,
    description TEXT,
    status      SMALLINT      NOT NULL DEFAULT 1,
    created_at  TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dream_subjects_topic_id   ON dream_subjects (topic_id);
CREATE INDEX idx_dream_subjects_name_lower ON dream_subjects (LOWER(name));
CREATE INDEX idx_dream_subjects_status     ON dream_subjects (status);

-- 3. dream_scenes（三级：具体梦境页面，最核心）
CREATE TABLE dream_scenes (
    id              BIGSERIAL     PRIMARY KEY,
    subject_id      BIGINT        NOT NULL REFERENCES dream_subjects(id),  -- ★新增：所属主体
    topic_id        BIGINT        NOT NULL REFERENCES dream_topics(id),    -- 冗余（可由 subject 推出），保留兼容
    title           VARCHAR(180)  NOT NULL,
    slug            VARCHAR(220)  NOT NULL,                                -- 如 eat-apple
    full_path       VARCHAR(300)  NOT NULL UNIQUE,                         -- 如 /apple/eat-apple
    main_object     VARCHAR(80)   NOT NULL,
    action          VARCHAR(80),
    target          VARCHAR(50),
    color           VARCHAR(50),
    location        VARCHAR(80),
    size_modifier   VARCHAR(80),
    other_modifier  VARCHAR(150),
    context         VARCHAR(80),
    quick_meaning   TEXT,
    western_content TEXT,
    chinese_content TEXT,
    extra_sections  JSONB,
    meta_title      VARCHAR(200),
    meta_description VARCHAR(320),
    status          SMALLINT      NOT NULL DEFAULT 0,
    view_count      INTEGER       NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_dream_scenes_subject_id      ON dream_scenes (subject_id);
CREATE INDEX idx_dream_scenes_topic_id        ON dream_scenes (topic_id);
CREATE INDEX idx_dream_scenes_main_object     ON dream_scenes (main_object);
CREATE INDEX idx_dream_scenes_action          ON dream_scenes (action);
CREATE INDEX idx_dream_scenes_obj_action      ON dream_scenes (main_object, action);
CREATE INDEX idx_dream_scenes_color_object    ON dream_scenes (color, main_object);
CREATE INDEX idx_dream_scenes_location        ON dream_scenes (location);
CREATE INDEX idx_dream_scenes_context         ON dream_scenes (context);
CREATE INDEX idx_dream_scenes_title_trgm      ON dream_scenes USING GIN (LOWER(title) gin_trgm_ops);

-- 4. dream_scene_terms（场景自身的标准身份词）★新增 2026-09-26
--    定位：把已冻结的搜索规则（词命中 +1）真正落地的那一环。
--    纯派生数据：可由 scene_terms.csv 全量 TRUNCATE + 重建。永远只放英文标准词。
CREATE TABLE dream_scene_terms (
    scene_id BIGINT       NOT NULL REFERENCES dream_scenes(id) ON DELETE CASCADE,
    term     VARCHAR(60)  NOT NULL,
    PRIMARY KEY (scene_id, term)
);
-- 关键：反向查询（给一个词 → 找所有含此词的 scene）必须有这个索引，否则全表扫描
CREATE INDEX idx_scene_terms_term ON dream_scene_terms (term, scene_id);

-- 5. dream_scene_aliases（搜索别名表）
CREATE TABLE dream_scene_aliases (
    id               BIGSERIAL   PRIMARY KEY,
    scene_id         BIGINT      NOT NULL REFERENCES dream_scenes(id) ON DELETE CASCADE,
    alias_text       TEXT        NOT NULL,
    alias_normalized TEXT        NOT NULL,
    weight           REAL        NOT NULL DEFAULT 1.0,
    source           VARCHAR(30) NOT NULL DEFAULT 'manual',
    status           SMALLINT    NOT NULL DEFAULT 1,
    created_at       TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_alias_scene_id      ON dream_scene_aliases (scene_id);
CREATE INDEX idx_alias_normalized    ON dream_scene_aliases (alias_normalized);
CREATE INDEX idx_alias_status        ON dream_scene_aliases (status);
CREATE INDEX idx_alias_norm_trgm     ON dream_scene_aliases USING GIN (alias_normalized gin_trgm_ops);

-- 6. search_terms（搜索词归一库）
CREATE TABLE search_terms (
    id              BIGSERIAL   PRIMARY KEY,
    variant_text    TEXT        NOT NULL,
    normalized_text TEXT        NOT NULL,
    field_type      VARCHAR(30) NOT NULL,
    canonical_value TEXT        NOT NULL,
    weight          REAL        NOT NULL DEFAULT 1.0,
    lang            VARCHAR(10) NOT NULL DEFAULT 'en',
    status          SMALLINT    NOT NULL DEFAULT 1,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_search_terms_normalized ON search_terms (normalized_text);
CREATE INDEX idx_search_terms_field_val  ON search_terms (field_type, canonical_value);

-- 7. dream_nearby（相关梦境关系）
CREATE TABLE dream_nearby (
    id              BIGSERIAL PRIMARY KEY,
    scene_id        BIGINT    NOT NULL REFERENCES dream_scenes(id) ON DELETE CASCADE,
    nearby_scene_id BIGINT    NOT NULL REFERENCES dream_scenes(id) ON DELETE CASCADE,
    sort_order      SMALLINT  NOT NULL DEFAULT 0,
    UNIQUE (scene_id, nearby_scene_id)
);
CREATE INDEX idx_dream_nearby_scene_id ON dream_nearby (scene_id);

-- 8. search_logs（搜索日志）
CREATE TABLE search_logs (
    id                 BIGSERIAL   PRIMARY KEY,
    query_text         TEXT        NOT NULL,
    normalized_query   TEXT,
    intent_type        VARCHAR(30),
    candidate_page_ids BIGINT[],
    clicked_page_id    BIGINT,
    top_score          REAL,
    second_score       REAL,
    result_type        VARCHAR(30),
    created_at         TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_search_logs_created    ON search_logs (created_at);
CREATE INDEX idx_search_logs_clicked    ON search_logs (clicked_page_id);
CREATE INDEX idx_search_logs_intent     ON search_logs (intent_type);

-- 9. dream_submissions（用户提交梦境）
CREATE TABLE dream_submissions (
    id                 BIGSERIAL    PRIMARY KEY,
    dream_text         TEXT         NOT NULL,
    email              VARCHAR(150) NOT NULL,
    status             SMALLINT     NOT NULL DEFAULT 0,
    ai_draft           TEXT,
    final_reply        TEXT,
    converted_scene_id BIGINT       REFERENCES dream_scenes(id),
    created_at         TIMESTAMP    NOT NULL DEFAULT NOW(),
    replied_at         TIMESTAMP
);
CREATE INDEX idx_submissions_status  ON dream_submissions (status);
CREATE INDEX idx_submissions_created ON dream_submissions (created_at);
