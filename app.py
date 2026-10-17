"""
app.py —— 主程序（整个网站的大脑）

Flask 的核心思想：一个"网址"对应一个"函数"。
用户访问 /login，Flask 就执行 login() 这个函数，把返回值当网页发回去。
这种写法叫"路由（route）"。

下面按功能顺序看，会更好懂。
"""

import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, jsonify,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db

app = Flask(__name__)

# session（登录状态）需要一个密钥来签名，防止被伪造。
# 优先读环境变量；没有就用一个开发用的固定值（部署时一定要换成随机值）
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me-in-production")


# ============================================================
# 一、启动时准备
# ============================================================

@app.teardown_appcontext
def _close_db(e=None):
    """每个请求结束后自动关掉数据库连接（detail 由 db.py 处理）"""
    close_db(e)


def ensure_db():
    """确保数据库表和默认分类存在。第一次运行会自动创建。"""
    init_db()   # 执行 schema.sql 建表

    db = get_db()
    # 检查有没有"全局默认分类"（user_id IS NULL 表示系统给所有人的模板）
    count = db.execute("SELECT COUNT(*) AS c FROM categories WHERE user_id IS NULL").fetchone()["c"]
    if count == 0:
        defaults = [
            ("餐饮", "expense"), ("交通", "expense"), ("购物", "expense"),
            ("居住", "expense"), ("娱乐", "expense"), ("医疗", "expense"),
            ("学习", "expense"), ("其他支出", "expense"),
            ("工资", "income"), ("兼职", "income"),
            ("红包", "income"), ("其他收入", "income"),
        ]
        db.executemany(
            "INSERT INTO categories (user_id, name, kind) VALUES (NULL, ?, ?)",
            defaults,
        )
        db.commit()


# ============================================================
# 二、登录校验装饰器
# ============================================================

def login_required(view):
    """
    装饰器：加在需要登录才能看的函数上。

    @login_required
    def index(): ...

    这样一写，没登录的人访问首页会被自动踢到登录页。
    不用在每个函数里重复写 if 判断。
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("请先登录", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_logged_in_user():
    """
    每个请求开始前都跑一遍：把"当前登录用户"查出来放进 g.user。
    这样任何函数里都能直接用 g.user。
    """
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


# ============================================================
# 三、注册 / 登录 / 退出
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        # --- 输入校验（这一步很重要，面试常问"你怎么防错"）---
        error = None
        if not username:
            error = "用户名不能为空"
        elif len(username) < 3:
            error = "用户名至少 3 个字符"
        elif len(password) < 6:
            error = "密码至少 6 位"
        elif password != password2:
            error = "两次输入的密码不一致"

        if error is None:
            db = get_db()
            exists = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                error = "该用户名已被注册"
            else:
                # 密码绝不存明文，用 generate_password_hash 加密
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
                flash("注册成功，请登录", "success")
                return redirect(url_for("login"))

        flash(error, "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            # 故意不区分"用户不存在"和"密码错误"，防止别人猜出哪些用户名存在
            flash("用户名或密码错误", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash("登录成功", "success")
            return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "success")
    return redirect(url_for("login"))


# ============================================================
# 四、首页：账单列表 + 收支概览
# ============================================================

@app.route("/")
@login_required
def index():
    db = get_db()

    # --- 取筛选条件（用户可能只想看某个月）---
    month = request.args.get("month", "").strip()   # 形如 2026-10

    where = "WHERE r.user_id = ?"
    params = [g.user["id"]]
    if month:
        where += " AND strftime('%Y-%m', r.record_date) = ?"
        params.append(month)

    # --- 查记录：JOIN 把分类名一起查出来 ---
    records = db.execute(
        f"""
        SELECT r.*, c.name AS category_name
        FROM records r
        JOIN categories c ON c.id = r.category_id
        {where}
        ORDER BY r.record_date DESC, r.id DESC
        """,
        params,
    ).fetchall()

    # --- 算总收入和总支出 ---
    total_income = sum(r["amount"] for r in records if r["kind"] == "income")
    total_expense = sum(r["amount"] for r in records if r["kind"] == "expense")

    # --- 统计每个分类花了多少（给饼图用）---
    by_category = {}
    for r in records:
        if r["kind"] == "expense":
            by_category[r["category_name"]] = by_category.get(r["category_name"], 0) + r["amount"]

    return render_template(
        "index.html",
        records=records,
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        balance=total_income - total_expense,
        chart_labels=list(by_category.keys()),
        chart_values=[round(v, 2) for v in by_category.values()],
    )


# ============================================================
# 五、记一笔账（新增）
# ============================================================

@app.route("/record/add", methods=["GET", "POST"])
@login_required
def add_record():
    db = get_db()

    if request.method == "POST":
        # 从表单里取数据
        amount = request.form.get("amount", "").strip()
        kind = request.form.get("kind", "expense")
        category_id = request.form.get("category_id", "")
        note = request.form.get("note", "").strip()
        record_date = request.form.get("record_date", "").strip()

        # --- 校验 ---
        error = None
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                raise ValueError
        except ValueError:
            error = "金额必须是大于 0 的数字"
            amount_val = 0

        if not category_id:
            error = "请选择分类"
        if not record_date:
            error = "请选择日期"

        if error is None:
            db.execute(
                """INSERT INTO records (user_id, category_id, amount, kind, note, record_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (g.user["id"], category_id, amount_val, kind, note, record_date),
            )
            db.commit()
            flash("记账成功", "success")
            return redirect(url_for("index"))

        flash(error, "error")

    # 分类下拉框的数据：系统默认分类(NULL) + 用户自己建的
    categories = db.execute(
        "SELECT * FROM categories WHERE user_id IS NULL OR user_id = ? ORDER BY kind DESC, id",
        (g.user["id"],),
    ).fetchall()

    return render_template(
        "record_form.html",
        categories=categories,
        today=date.today().isoformat(),   # 表单里的日期默认今天
        record=None,
    )


# ============================================================
# 六、修改一条记录
# ============================================================

@app.route("/record/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit_record(record_id):
    db = get_db()

    # 关键安全检查：只能改自己的记录（user_id 必须匹配）
    record = db.execute(
        "SELECT * FROM records WHERE id = ? AND user_id = ?",
        (record_id, g.user["id"]),
    ).fetchone()
    if record is None:
        flash("记录不存在或无权操作", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        kind = request.form.get("kind", "expense")
        category_id = request.form.get("category_id", "")
        note = request.form.get("note", "").strip()
        record_date = request.form.get("record_date", "").strip()

        error = None
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                raise ValueError
        except ValueError:
            error = "金额必须是大于 0 的数字"
            amount_val = 0

        if error is None:
            db.execute(
                """UPDATE records
                   SET category_id = ?, amount = ?, kind = ?, note = ?, record_date = ?
                   WHERE id = ? AND user_id = ?""",
                (category_id, amount_val, kind, note, record_date,
                 record_id, g.user["id"]),
            )
            db.commit()
            flash("修改成功", "success")
            return redirect(url_for("index"))

        flash(error, "error")

    categories = db.execute(
        "SELECT * FROM categories WHERE user_id IS NULL OR user_id = ? ORDER BY kind DESC, id",
        (g.user["id"],),
    ).fetchall()

    return render_template(
        "record_form.html",
        categories=categories,
        today=date.today().isoformat(),
        record=record,      # 传过去用于回填表单
    )


# ============================================================
# 七、删除一条记录
# ============================================================

@app.route("/record/<int:record_id>/delete", methods=["POST"])
@login_required
def delete_record(record_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM records WHERE id = ? AND user_id = ?",
        (record_id, g.user["id"]),
    )
    db.commit()

    # rowcount = 实际删掉了几行
    # 如果等于 0，说明这条记录不存在，或者不是当前用户的
    if cur.rowcount == 0:
        flash("记录不存在或无权操作", "error")
    else:
        flash("已删除", "success")
    return redirect(url_for("index"))


# ============================================================
# 八、统计页（按月汇总）
# ============================================================

@app.route("/stats")
@login_required
def stats():
    db = get_db()

    # 按月分组，算出每月的收入 / 支出
    rows = db.execute(
        """
        SELECT strftime('%Y-%m', record_date) AS month,
               SUM(CASE WHEN kind = 'income'  THEN amount ELSE 0 END) AS income,
               SUM(CASE WHEN kind = 'expense' THEN amount ELSE 0 END) AS expense
        FROM records
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month DESC
        """,
        (g.user["id"],),
    ).fetchall()

    monthly = []
    for r in rows:
        monthly.append({
            "month": r["month"],
            "income": round(r["income"] or 0, 2),
            "expense": round(r["expense"] or 0, 2),
            "balance": round((r["income"] or 0) - (r["expense"] or 0), 2),
        })

    return render_template("stats.html", monthly=monthly)


# ============================================================
# 九、启动
# ============================================================

if __name__ == "__main__":
    with app.app_context():
        ensure_db()          # 第一次跑的时候自动建库建表
    print("记账本已启动：http://127.0.0.1:5000")
    app.run(debug=True, port=5000)