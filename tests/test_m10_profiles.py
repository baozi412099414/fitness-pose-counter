"""模块 10 测试 —— 个人档案与多用户切换

对应《选题说明》第 11 题功能模块第 10 项：
「区分不同训练者的记录。」
"""

import os
import sys

from harness import suite

if __name__ == "__main__":
    pass


@suite("模块 10 · 个人档案与多用户切换")
def _run(t):
    from training_manager import UserStore, History, Goals

    # ---------------- 创建与列出 ----------------
    t.section("创建用户并列出")
    root = t.tmpdir()
    store = UserStore(root=root)
    store.create_user("小王")
    store.create_user("小李")
    users = store.list_users()
    t.eq("用户列表应有 2 个", len(users), 2)
    t.truthy("包含小王和小李", set(users) == {"小王", "小李"}, detail=users)

    t.section("重复创建同名用户不报错、不覆盖档案")
    # 用一个此前没建过的名字，单独验证「首次写入 / 再次不覆盖」
    p1 = store.create_user("张三", height_cm=175, weight_kg=70)
    t.eq("首次创建能写入身高", p1.get("height_cm"), 175)
    t.eq("首次创建能写入体重", p1.get("weight_kg"), 70)
    p2 = store.create_user("张三", height_cm=180, weight_kg=80)
    t.eq("再次创建不覆盖已存身高", p2.get("height_cm"), 175)
    t.eq("再次创建不覆盖已存体重", p2.get("weight_kg"), 70)
    t.eq("create_user 是幂等的（不会多出用户）", len(store.list_users()), 3)

    t.section("非法用户名")
    t.expect_exception("空用户名抛 ValueError", lambda: store.create_user("   "), ValueError)

    # ---------------- 切换与当前用户 ----------------
    t.section("切换用户")
    store.switch_user("小王")
    t.eq("切换后当前用户是小王", store.current_user(), "小王")
    store.switch_user("小李")
    t.eq("再次切换后是用户小李", store.current_user(), "小李")

    t.section("当前用户在任何时候都有可用档案")
    store2 = UserStore(root=t.tmpdir())
    cur = store2.current_user()
    t.truthy("空库调用 current_user 会自动建默认用户", cur in store2.list_users(), detail=cur)
    t.eq("默认用户名为「默认用户」", cur, "默认用户")

    # ---------------- 数据隔离（本模块最关键的验收点） ----------------
    t.section("数据按用户隔离：各自的记录互不覆盖")
    store3 = UserStore(root=t.tmpdir())
    store3.create_user("甲")
    store3.create_user("乙")
    h甲 = History(store3, "甲")
    h乙 = History(store3, "乙")
    h甲.add_session("squat", 100, score=90.0)
    h乙.add_session("squat", 7, score=40.0)
    t.eq("甲的历史 1 条", len(h甲.all_sessions()), 1)
    t.eq("乙的历史 1 条", len(h乙.all_sessions()), 1)
    t.eq("甲的次数是 100", h甲.all_sessions()[0]["reps"], 100)
    t.eq("乙的次数是 7", h乙.all_sessions()[0]["reps"], 7)
    t.eq("甲今日次数 100", h甲.today_reps("squat"), 100)
    t.eq("乙今日次数 7", h乙.today_reps("squat"), 7)

    t.section("目标也按用户隔离")
    g甲 = Goals(store3, "甲")
    g乙 = Goals(store3, "乙")
    g甲.set_goal("squat", 50)
    t.eq("甲的目标是 50", g甲.get_goal("squat"), 50)
    t.eq("乙没有目标（0）", g乙.get_goal("squat"), 0)

    t.section("档案目录按用户分开")
    d甲 = store3.user_dir("甲")
    d乙 = store3.user_dir("乙")
    t.truthy("两个用户目录不是同一个", os.path.abspath(d甲) != os.path.abspath(d乙),
             detail="%s / %s" % (d甲, d乙))
    t.truthy("甲的目录存在", os.path.isdir(d甲))
    t.truthy("乙的目录存在", os.path.isdir(d乙))

    # ---------------- 删除用户与保护规则 ----------------
    t.section("删除用户：保护最后一个")
    store4 = UserStore(root=t.tmpdir())
    store4.create_user("唯一用户")
    ok, msg = store4.delete_user("唯一用户")
    t.falsy("只剩一个用户时拒绝删除", ok, detail=msg)
    t.eq("唯一用户仍在列表里", store4.list_users(), ["唯一用户"])

    t.section("删除用户：正常删除")
    store5 = UserStore(root=t.tmpdir())
    store5.create_user("甲")
    store5.create_user("乙")
    store5.switch_user("甲")
    ok, msg = store5.delete_user("甲")
    t.truthy("有多个用户时允许删除", ok, detail=msg)
    t.falsy("甲已不在列表", "甲" in store5.list_users(), detail=store5.list_users())
    t.eq("删除当前用户后自动切到剩下的用户", store5.current_user(), "乙")
    t.truthy("被删用户的目录已清理", not os.path.isdir(store5.user_dir("甲")))

    t.section("删除不存在的用户")
    ok, msg = store5.delete_user("查无此人")
    t.falsy("删除不存在的用户返回 False", ok, detail=msg)

    # ---------------- 持久化 ----------------
    t.section("持久化：重新打开库后用户与当前人仍在")
    store6 = UserStore(root=t.tmpdir())
    store6.create_user("持久用户")
    store6.switch_user("持久用户")
    store6b = UserStore(root=store6.root)
    t.eq("重启后当前用户仍是持久用户", store6b.current_user(), "持久用户")
    t.truthy("重启后用户列表含持久用户", "持久用户" in store6b.list_users())


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
