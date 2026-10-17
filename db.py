"""
db.py —— 数据库工具模块

作用：专门负责"打开数据库"和"建表"。
其他文件需要读写数据库时，import 这里的 get_db() 就行。

为什么单独一个文件？
→ 这叫"关注点分离"。数据库的事归 db.py，网页的事归 app.py。
  以后数据库要换配置，只改这一个文件。
"""

import os
import sqlite3

from flask import g

# 数据库文件就放在项目根目录，名字叫 jizhangben.db
# （第一次运行时会自动生成，不用你手动创建）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "jizhangben.db")


def get_db():
    """
    获取数据库连接。

    g 是 Flask 提供的"当前请求专属储物柜"：
    - 同一个网页请求里，不管调用多少次 get_db()，都只开一个连接（省资源）
    - 请求一结束，连接自动关闭（不会泄漏）
    """
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        # row_factory 让查询结果能像字典一样取值：row["username"]
        # 不加这行就只能用下标 row[1]，代码可读性差
        g.db.row_factory = sqlite3.Row
        # SQLite 默认不开外键约束，手动打开（保证关联数据不会乱）
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """关闭数据库连接。由 app.py 里的 teardown 钩子自动调用，你不用管。"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """
    建表。读取 schema.sql 并执行。
    因为 schema.sql 里写的是 CREATE TABLE IF NOT EXISTS，
    所以重复运行也不会报错、不会清空数据。
    """
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(sql)   # executescript = 一次执行文件里所有 SQL
    conn.commit()
    conn.close()