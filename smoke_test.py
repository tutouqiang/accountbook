"""
smoke_test.py —— 冒烟测试

作用：不打开浏览器，直接用代码把所有功能走一遍。
"冒烟测试"这个名字来自硬件行业：通电后先看冒不冒烟，冒烟就是坏了。
开发时先跑这个，能快速发现低级错误。

运行方式：python smoke_test.py
"""

import os
import tempfile

# 测试时用临时数据库，不污染你的真实数据
fd, tmp_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["SECRET_KEY"] = "test-key"

import db as db_module
db_module.DB_PATH = tmp_db

import app as app_module
app_module.app.config["TESTING"] = True

from app import app, ensure_db

passed = 0
failed = 0


def check(name, condition, extra=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [OK]   {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {extra}")


with app.app_context():
    ensure_db()

client = app.test_client()

print("=" * 56)
print("1. 未登录时应该被拦截")
print("=" * 56)
r = client.get("/", follow_redirects=False)
check("访问首页跳转到登录页", r.status_code == 302 and "/login" in r.headers.get("Location", ""),
      f"status={r.status_code}")

print()
print("=" * 56)
print("2. 注册")
print("=" * 56)
r = client.post("/register", data={"username": "tester", "password": "123456",
                                   "password2": "123456"}, follow_redirects=True)
check("注册成功", "注册成功" in r.get_data(as_text=True))

r = client.post("/register", data={"username": "tester", "password": "123456",
                                   "password2": "123456"}, follow_redirects=True)
check("重复用户名被拒绝", "已被注册" in r.get_data(as_text=True))

r = client.post("/register", data={"username": "ab", "password": "123456",
                                   "password2": "123456"}, follow_redirects=True)
check("用户名太短被拒绝", "至少 3 个字符" in r.get_data(as_text=True))

r = client.post("/register", data={"username": "newuser", "password": "123456",
                                   "password2": "654321"}, follow_redirects=True)
check("两次密码不一致被拒绝", "不一致" in r.get_data(as_text=True))

r = client.post("/register", data={"username": "newuser", "password": "123",
                                   "password2": "123"}, follow_redirects=True)
check("密码太短被拒绝", "至少 6 位" in r.get_data(as_text=True))

print()
print("=" * 56)
print("3. 登录")
print("=" * 56)
r = client.post("/login", data={"username": "tester", "password": "wrong"},
                follow_redirects=True)
check("密码错误被拒绝", "用户名或密码错误" in r.get_data(as_text=True))

r = client.post("/login", data={"username": "nobody", "password": "123456"},
                follow_redirects=True)
check("用户不存在被拒绝", "用户名或密码错误" in r.get_data(as_text=True))

r = client.post("/login", data={"username": "tester", "password": "123456"},
                follow_redirects=True)
body = r.get_data(as_text=True)
check("正确密码登录成功", "登录成功" in body)
check("登录后能看到用户名", "tester" in body)

print()
print("=" * 56)
print("4. 记一笔账（新增）")
print("=" * 56)
r = client.get("/record/add")
check("记账页能打开", r.status_code == 200 and "记一笔" in r.get_data(as_text=True))

# 找几个分类 id
with app.app_context():
    conn = db_module.get_db() if False else None
import sqlite3
conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
cats = conn.execute("SELECT * FROM categories WHERE user_id IS NULL").fetchall()
food = [c for c in cats if c["name"] == "餐饮"][0]
salary = [c for c in cats if c["name"] == "工资"][0]
conn.close()

r = client.post("/record/add", data={"amount": "35.50", "kind": "expense",
                                     "category_id": food["id"],
                                     "note": "午饭", "record_date": "2026-10-18"},
                follow_redirects=True)
body = r.get_data(as_text=True)
check("记一笔支出成功", "记账成功" in body)
check("列表显示金额 35.50", "35.50" in body)
check("列表显示分类'餐饮'", "餐饮" in body)
check("列表显示备注'午饭'", "午饭" in body)

r = client.post("/record/add", data={"amount": "8000", "kind": "income",
                                     "category_id": salary["id"],
                                     "note": "10月工资", "record_date": "2026-10-01"},
                follow_redirects=True)
body = r.get_data(as_text=True)
check("记一笔收入成功", "记账成功" in body)
check("显示收入 8000.00", "8000.00" in body)

r = client.post("/record/add", data={"amount": "-5", "kind": "expense",
                                     "category_id": food["id"],
                                     "note": "", "record_date": "2026-10-18"},
                follow_redirects=True)
check("负数金额被拒绝", "大于 0" in r.get_data(as_text=True))

r = client.post("/record/add", data={"amount": "abc", "kind": "expense",
                                     "category_id": food["id"],
                                     "note": "", "record_date": "2026-10-18"},
                follow_redirects=True)
check("非数字金额被拒绝", "大于 0" in r.get_data(as_text=True))

print()
print("=" * 56)
print("5. 收支汇总计算")
print("=" * 56)
r = client.get("/")
body = r.get_data(as_text=True)
check("总收入 8000.00", "8000.00" in body)
check("总支出 35.50", "35.50" in body)

print()
print("=" * 56)
print("6. 修改记录")
print("=" * 56)
conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
rec = conn.execute("SELECT * FROM records WHERE kind='expense'").fetchone()
rec_id = rec["id"]
conn.close()

r = client.get(f"/record/{rec_id}/edit")
check("编辑页能打开", r.status_code == 200)
check("编辑页回填了原金额", "35.5" in r.get_data(as_text=True))

r = client.post(f"/record/{rec_id}/edit",
                data={"amount": "42.00", "kind": "expense", "category_id": food["id"],
                      "note": "午饭改成42", "record_date": "2026-10-18"},
                follow_redirects=True)
body = r.get_data(as_text=True)
check("修改成功", "修改成功" in body)
check("新金额 42.00 生效", "42.00" in body)
check("新备注生效", "午饭改成42" in body)

print()
print("=" * 56)
print("7. 月份筛选")
print("=" * 56)
r = client.get("/?month=2026-10")
body = r.get_data(as_text=True)
check("筛选 2026-10 能看到记录", "42.00" in body)

r = client.get("/?month=2020-01")
body = r.get_data(as_text=True)
check("筛选空月份显示空状态", "还没有记账记录" in body)

print()
print("=" * 56)
print("8. 统计页")
print("=" * 56)
r = client.get("/stats")
body = r.get_data(as_text=True)
check("统计页能打开", r.status_code == 200)
check("统计显示月份 2026-10", "2026-10" in body)
check("统计显示收入 8000.00", "8000.00" in body)

print()
print("=" * 56)
print("9. 删除记录")
print("=" * 56)
r = client.post(f"/record/{rec_id}/delete", follow_redirects=True)
body = r.get_data(as_text=True)
check("删除成功", "已删除" in body)
check("删除后列表看不到 42.00", "42.00" not in body)

print()
print("=" * 56)
print("10. 越权访问（安全测试）")
print("=" * 56)
# 换个用户，尝试改别人的记录
client2 = app.test_client()
client2.post("/register", data={"username": "hacker", "password": "123456",
                                "password2": "123456"})
client2.post("/login", data={"username": "hacker", "password": "123456"})

conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
others = conn.execute("SELECT * FROM records").fetchall()
other_id = others[0]["id"]
conn.close()

r = client2.get(f"/record/{other_id}/edit", follow_redirects=True)
check("不能编辑别人的记录", "无权操作" in r.get_data(as_text=True))

r = client2.post(f"/record/{other_id}/delete", follow_redirects=True)
check("不能删除别人的记录", "无权操作" in r.get_data(as_text=True))

conn = sqlite3.connect(tmp_db)
still = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
conn.close()
check("别人的记录还在（没被删掉）", still == 1, f"count={still}")

print()
print("=" * 56)
print("11. 退出登录")
print("=" * 56)
r = client.get("/logout", follow_redirects=True)
check("退出后回到登录页", "登录" in r.get_data(as_text=True))
r = client.get("/", follow_redirects=False)
check("退出后访问首页被拦截", r.status_code == 302)

print()
print("=" * 56)
print(f"结果：通过 {passed} 项，失败 {failed} 项")
print("=" * 56)

os.unlink(tmp_db)
raise SystemExit(1 if failed else 0)