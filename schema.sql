-- 记账本数据库结构
-- 这个文件定义"数据长什么样"，一共 3 张表

-- 表1：用户表。存登录账号
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- 用户编号，自动增长
    username      TEXT    NOT NULL UNIQUE,            -- 用户名，不能重复
    password_hash TEXT    NOT NULL,                   -- 密码（加密后的，不存明文）
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 表2：分类表。存"吃饭""交通""工资"这类分类
CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    -- user_id 允许为空：NULL 表示"系统默认分类"，所有用户共用
    -- 有值表示"这个用户自己建的分类"
    user_id INTEGER,
    name    TEXT    NOT NULL,                         -- 分类名，比如"餐饮"
    kind    TEXT    NOT NULL,                         -- 类型：expense=支出 / income=收入
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 表3：记账记录表。核心业务表
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,                     -- 属于哪个用户
    category_id INTEGER NOT NULL,                     -- 属于哪个分类
    amount      REAL    NOT NULL,                     -- 金额
    kind        TEXT    NOT NULL,                     -- expense=支出 / income=收入
    note        TEXT,                                 -- 备注，可以为空
    record_date TEXT    NOT NULL,                     -- 记账日期，格式 2026-10-18
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- 建索引：以后记录多了，按用户+日期查会快很多
CREATE INDEX IF NOT EXISTS idx_records_user_date
    ON records (user_id, record_date);