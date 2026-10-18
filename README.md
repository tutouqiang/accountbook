# 个人记账本

一个基于 Python + Flask 的个人收支记账 Web 应用。

> 仓库地址：https://github.com/tutouqiang/jizhangben

## 功能

- 用户注册 / 登录 / 退出（密码加密存储）
- 账单的增、删、改、查
- 收入 / 支出分类管理
- 按月份筛选账单
- 收支汇总与分类占比饼图
- 按月统计柱状图

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3 + Flask |
| 数据库 | SQLite 3 |
| 前端 | HTML5 / CSS3 / 原生 JavaScript |
| 图表 | Chart.js |
| 模板 | Jinja2 |

## 项目结构

```
jizhangben/
├── app.py                  # 主程序：所有路由（网页逻辑）
├── db.py                   # 数据库连接与初始化
├── schema.sql              # 数据库表结构定义
├── smoke_test.py           # 冒烟测试（38 项断言）
├── requirements.txt        # 依赖清单
├── templates/              # HTML 模板
│   ├── base.html           #   公共骨架（导航栏 + 消息提示）
│   ├── login.html          #   登录页
│   ├── register.html       #   注册页
│   ├── index.html          #   首页：账单列表 + 概览 + 饼图
│   ├── record_form.html    #   记账 / 编辑表单
│   └── stats.html          #   统计页
└── static/
    └── style.css           # 样式表
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（会自动建数据库）
python app.py

# 3. 浏览器打开
#    http://127.0.0.1:5000
```

## 运行测试

```bash
python smoke_test.py
```

## 数据库设计

三张表，关系如下：

```
users (用户)
  └─1:N─ categories (分类)   user_id 为 NULL 表示系统默认分类
  └─1:N─ records    (记录)   ──N:1── categories
```

| 表 | 作用 | 关键字段 |
|----|------|----------|
| `users` | 存账号 | `username` 唯一，`password_hash` 加密 |
| `categories` | 存分类 | `kind` 区分收入/支出 |
| `records` | 存每笔账 | `amount` / `record_date` / `note` |

## 安全设计

- 密码用 `werkzeug.security` 哈希存储，**不存明文**
- 所有查改删操作都带 `user_id` 条件，**防止越权访问他人数据**
- 删除操作用 POST 而非 GET，**避免被预加载误删**
- 数据库操作全部使用参数化查询，**防止 SQL 注入**
- 模板自动转义，**防止 XSS**