
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- 创建 users 表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 创建会话表
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(16) PRIMARY KEY,
    session_name VARCHAR(255) NOT NULL,  
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at  ON sessions(created_at);

-- 创建 messages 表
CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(16) NOT NULL,
    user_question TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    documents  TEXT,  -- 修改为 jsonb 类型
    recommended_questions TEXT,  
    think TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- 创建知识库表
CREATE TABLE IF NOT EXISTS knowledgebases (
    id SERIAL PRIMARY KEY,  -- 主键，自增
    user_id VARCHAR(255) NOT NULL,       -- 用户 ID
    file_name VARCHAR(255) NOT NULL,     -- 文件名称
    title VARCHAR(500),                  -- 论文标题；兼容旧数据，暂时允许为空
    authors JSONB NOT NULL DEFAULT '[]'::jsonb,       -- 有序作者列表
    year INTEGER CHECK (year IS NULL OR (year >= 1000 AND year <= 9999)),
    venue VARCHAR(255),                  -- 期刊、会议或出版机构
    doi VARCHAR(255),                    -- 规范化 DOI，不包含 https://doi.org/ 前缀
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,      -- 论文原始关键词
    abstract TEXT,                       -- 论文摘要
    research_topic VARCHAR(255),         -- 用户归纳的研究主题
    read_status VARCHAR(32) NOT NULL DEFAULT 'unread'
        CHECK (read_status IN ('unread', 'reading', 'read', 'archived')),
    personal_tags JSONB NOT NULL DEFAULT '[]'::jsonb, -- 用户个人标签
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_knowledgebases_user_id ON knowledgebases(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledgebases_created_at ON knowledgebases(created_at);
CREATE INDEX IF NOT EXISTS idx_knowledgebases_read_status ON knowledgebases(read_status);
CREATE INDEX IF NOT EXISTS idx_knowledgebases_year ON knowledgebases(year);
CREATE INDEX IF NOT EXISTS idx_knowledgebases_doi ON knowledgebases(doi);
