#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练管理模块的自动化测试（模块 7 / 8 / 10）。

这些测试**不碰摄像头、不碰 MediaPipe**，因此可以在任何环境完整跑通 ——
正好弥补「没有真人视频素材」的短板：核心逻辑一样能被验证。

运行：.venv/bin/python test_training_manager.py
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta

from training_manager import SetManager, UserStore, History, Goals


# ══════════════════════════════════════════════════════════════
# 模块 7：训练组与间歇
# ══════════════════════════════════════════════════════════════
def test_set_manager_basic():
    print("=== 测试 1：训练组与间歇（3 组 × 10 次，组间休息 30 秒） ===")
    sm = SetManager(sets=3, reps_per_set=10, rest_seconds=30)
    t = 1000.0

    # 第 1 组：做 10 次
    events = []
    for i in range(1, 11):
        events += sm.on_rep(i, now=t)
        t += 2.0
    kinds = [e["type"] for e in events]
    print(f"  第 1 组做满 -> 事件 {kinds}")
    assert "set_done" in kinds, "做满一组应触发 set_done"
    assert "rest_start" in kinds, "应进入组间休息"
    assert sm.rest_remaining(now=t) > 25, "休息时间应接近 30 秒"

    # 休息期间继续喂计数：不该被算进去
    before_total = sm.total_reps
    sm.on_rep(999, now=t)          # 休息中，外部计数就算涨了也不认
    print(f"  休息中喂 count=999 -> 累计次数保持 {sm.total_reps}（未被计入）")
    assert sm.total_reps == before_total, "休息期间的计数不该算进下一组"

    # 休息结束
    t += 31
    events = sm.on_rep(sm.total_reps, now=t)
    print(f"  休息结束后 -> 事件 {[e['type'] for e in events]}")
    assert any(e["type"] == "rest_end" for e in events), "休息结束应发 rest_end"

    # 第 2 组、第 3 组
    t += 1
    base = sm.total_reps
    for i in range(1, 11):
        sm.on_rep(base + i, now=t)
        t += 2.0
    t += 31
    sm.on_rep(sm.total_reps, now=t)
    t += 1
    base = sm.total_reps
    last_events = []
    for i in range(1, 11):
        last_events += sm.on_rep(base + i, now=t)
        t += 2.0
    kinds = [e["type"] for e in last_events]
    print(f"  第 3 组做满 -> 事件 {kinds}，总计 {sm.total_reps} 次")
    assert "all_done" in kinds, "最后一组做完应触发 all_done"
    assert sm.finished and sm.total_reps == 30
    print("  ✅ 分组、间歇、组间计数隔离都正确\n")


def test_set_manager_bulk_and_reset():
    print("=== 测试 2：一次喂进多次（离线视频跑得快）/ 清零 ===")
    sm = SetManager(sets=4, reps_per_set=5, rest_seconds=0)

    # 一次喂 12 次：应跨过 2 组（5+5），停在第 3 组的 2 次
    events = sm.on_rep(12, now=100.0)
    kinds = [e["type"] for e in events]
    print(f"  一次喂 12 次 -> 事件 {kinds}，当前第 {sm.current_set} 组、本组 {sm.reps_in_set} 次")
    assert kinds.count("set_done") == 2, "12 次应跨过 2 个满组"
    assert sm.current_set == 3 and sm.reps_in_set == 2

    sm.reset()
    print(f"  清零后 -> 第 {sm.current_set} 组、累计 {sm.total_reps} 次、finished={sm.finished}")
    assert sm.current_set == 1 and sm.total_reps == 0 and not sm.finished
    print("  ✅ 批量计数与清零都正确\n")


# ══════════════════════════════════════════════════════════════
# 模块 10：多用户
# ══════════════════════════════════════════════════════════════
def test_user_store():
    print("=== 测试 3：个人档案与多用户切换 ===")
    tmp = tempfile.mkdtemp()
    try:
        store = UserStore(root=os.path.join(tmp, "users"))
        store.create_user("小王", height_cm=175)
        store.create_user("小李")
        users = store.list_users()
        print(f"  创建后用户列表：{users}")
        assert users == ["小李", "小王"] or set(users) == {"小王", "小李"}

        # 重复创建不该覆盖已有档案
        store.create_user("小王")
        assert store.profile("小王")["height_cm"] == 175, "重复创建不该覆盖原档案"

        store.switch_user("小李")
        print(f"  切换后当前用户：{store.current_user()}")
        assert store.current_user() == "小李"

        # 数据目录按用户分开
        assert store.user_dir("小王") != store.user_dir("小李")
        print(f"  数据目录：{os.path.basename(store.user_dir('小王'))} / "
              f"{os.path.basename(store.user_dir('小李'))}")
        print("  ✅ 多用户创建、切换、档案保护正确\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ══════════════════════════════════════════════════════════════
# 模块 8：历史与目标
# ══════════════════════════════════════════════════════════════
def test_history_and_goals():
    print("=== 测试 4：训练历史、每日目标、每周趋势 ===")
    tmp = tempfile.mkdtemp()
    try:
        store = UserStore(root=os.path.join(tmp, "users"))
        store.switch_user("测试员")
        hist = History(store, "测试员")
        goals = Goals(store, "测试员")

        # 记三次训练
        hist.add_session("squat", 20, sets=2, errors={"not_deep_enough": 3})
        hist.add_session("squat", 15, sets=2, errors={"not_deep_enough": 1, "knee_over_toe": 2})
        hist.add_session("pushup", 12, sets=2, errors={"low_back": 4})

        today = datetime.now().strftime("%Y-%m-%d")
        squat_today = hist.today_reps("squat")
        print(f"  今日深蹲 {squat_today} 次（历史共 {len(hist.all_sessions())} 条记录）")
        assert squat_today == 35, "今日深蹲应是 20+15=35"

        # 按动作过滤
        assert len(hist.sessions(action="squat")) == 2
        assert len(hist.sessions(action="pushup")) == 1
        print(f"  按动作过滤：深蹲 {len(hist.sessions(action='squat'))} 条、"
              f"俯卧撑 {len(hist.sessions(action='pushup'))} 条")

        # 错误汇总（最常犯的错排前面）
        errs = hist.error_summary()
        print(f"  错误汇总：{errs}")
        assert list(errs)[0] == "not_deep_enough", "出现最多的错误应排第一"
        assert errs["not_deep_enough"] == 4
        assert errs["low_back"] == 4

        # 目标与达成度
        goals.set_goal("squat", 40)
        p = goals.progress("squat", hist)
        print(f"  目标 40 次 -> 已完成 {p['done']}，达成率 {p['ratio']:.0%}，还差 {p['remaining']}")
        assert p["done"] == 35 and p["target"] == 40 and not p["reached"]

        goals.set_goal("pushup", 10)     # 已做 12，应算达成
        p2 = goals.progress("pushup", hist)
        print(f"  目标 10 次 -> 已完成 {p2['done']}，达成={p2['reached']}，达成率 {p2['ratio']:.0%}")
        assert p2["reached"] and p2["ratio"] == 1.0, "超额完成应封顶 100%"

        # 每周趋势（4 周，本周应有 47 次 = 35+12）
        trend = hist.weekly_trend(weeks=4)
        print(f"  每周趋势：{[(t['week_start'][5:], t['reps']) for t in trend]}")
        assert len(trend) == 4 and trend[-1]["reps"] == 47, "本周应是 35+12=47"

        # 跨用户数据隔离
        hist2 = History(store, store.create_user("另一个人")["name"])
        print(f"  换用户后历史条数：{len(hist2.all_sessions())}（应为 0，数据按人隔离）")
        assert hist2.all_sessions() == [], "不同用户的历史不能混在一起"
        print("  ✅ 历史记录、目标达成、趋势统计、多用户隔离都正确\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_persistence():
    print("=== 测试 5：重新加载后数据仍在（JSON 持久化） ===")
    tmp = tempfile.mkdtemp()
    try:
        root = os.path.join(tmp, "users")
        store = UserStore(root=root)
        store.switch_user("持久化用户")
        History(store, "持久化用户").add_session("jumping_jack", 25, sets=3)
        Goals(store, "持久化用户").set_goal("jumping_jack", 30)

        # 模拟程序重启：重新 new 一遍对象
        store2 = UserStore(root=root)
        hist2 = History(store2, "持久化用户")
        goals2 = Goals(store2, "持久化用户")
        print(f"  重启后：当前用户 {store2.current_user()}，"
              f"历史 {len(hist2.all_sessions())} 条，目标 {goals2.get_goal('jumping_jack')}")
        assert store2.current_user() == "持久化用户"
        assert hist2.all_sessions()[0]["reps"] == 25
        assert goals2.get_goal("jumping_jack") == 30
        print("  ✅ 用户、历史、目标都能跨进程保留\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_score_tracking():
    print("=== 测试 8：动作评分的历史统计（0~100 分） ===")
    tmp = tempfile.mkdtemp()
    try:
        store = UserStore(root=os.path.join(tmp, "users"))
        store.switch_user("评分用户")
        hist = History(store, "评分用户")
        now = datetime.now()

        for off, sc in ((4, 61.0), (3, 72.5), (2, 80.0), (1, 88.5), (0, 91.0)):
            hist.add_session("squat", 30, score=sc, when=now - timedelta(days=off))
        hist.add_session("squat", 25, when=now)          # 混一条没有分数的记录

        trend = hist.score_trend("squat", days=6)
        print(f"  评分趋势：{[(t['date'][5:], t['score']) for t in trend]}")
        assert trend[-1]["score"] == 91.0
        assert trend[0]["score"] is None, "第一天没记录应返回 None（不是 0）"

        avg = hist.avg_score("squat", days=7)
        expect = round((61 + 72.5 + 80 + 88.5 + 91) / 5, 1)
        print(f"  近 7 天平均分：{avg}（期望 {expect}）")
        assert avg == expect, "无分数的记录必须被跳过，不能拉低均值"

        # 完全没有分数的动作 → None（区别于「0 分」）
        hist.add_session("pushup", 20)
        print(f"  全无分数的动作平均分：{hist.avg_score('pushup')}")
        assert hist.avg_score("pushup") is None

        # 分数取值范围
        assert all(t["score"] is None or 0 <= t["score"] <= 100 for t in trend)
        print("  ✅ 评分趋势、均值、无分数容忍、范围约束都正确\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_delete_user():
    print("=== 测试 7：删除用户（保护规则 + 数据清理 + 自动切换） ===")
    tmp = tempfile.mkdtemp()
    try:
        store = UserStore(root=os.path.join(tmp, "users"))
        store.create_user("甲")
        store.create_user("乙")
        History(store, "乙").add_session("squat", 20)
        store.switch_user("乙")

        # ① 删非当前用户
        ok, msg = store.delete_user("甲")
        print(f"  删非当前用户 -> {msg}，剩余 {store.list_users()}")
        assert ok and "甲" not in store.list_users()
        assert not os.path.isdir(store.user_dir("甲")), "数据目录应被真的删掉"

        # ② 不允许删掉最后一个（否则程序没有可用档案）
        ok, msg = store.delete_user("乙")
        print(f"  删最后一个   -> {msg}")
        assert not ok, "最后一个用户不该被删掉"
        assert store.list_users() == ["乙"], "失败时不该动数据"

        # ③ 删掉的正好是当前用户 -> 自动切到剩下的用户
        store.create_user("丙")
        store.switch_user("丙")
        History(store, "丙").add_session("pushup", 10)
        ok, msg = store.delete_user("丙")
        print(f"  删当前用户   -> {msg}，当前切到「{store.current_user_or_none()}」")
        assert ok
        assert store.current_user_or_none() == "乙", "删当前用户后应切到其他有效用户"
        assert not os.path.isdir(store.user_dir("丙"))

        # ④ 删不存在的用户要有明确返回，而不是抛异常
        ok, msg = store.delete_user("查无此人")
        print(f"  删不存在的   -> {msg}")
        assert not ok
        print("  ✅ 删除用户、保护最后一个、自动切换、目录清理都正确\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_plot_trend(tmp_note=""):
    print("=== 测试 6：趋势图能正常生成（模块 8 的可视化） ===")
    tmp = tempfile.mkdtemp()
    try:
        os.environ["FITNESS_DATA_DIR"] = os.path.join(tmp, "users")   # 隔离，别污染真实数据
        from training_manager import UserStore as US
        store = US()
        user = store.switch_user("画图用户")
        hist = History(store, user)
        goals = Goals(store, user)
        goals.set_goal("squat", 40)

        now = datetime.now()
        for off in (6, 3, 1, 0):                    # 造几天的记录
            hist.add_session("squat", 20 + off, sets=2,
                             errors={"not_deep_enough": 2},
                             when=now - timedelta(days=off))

        out = os.path.join(tmp, "trend.png")
        import plot_trend
        plot_trend.plot(user, action="squat", weeks=4, days=7, out=out, show=False)
        size = os.path.getsize(out)
        print(f"  生成 {os.path.basename(out)}（{size} 字节）")
        assert size > 5000, "图片应该有实际内容"
        print("  ✅ 趋势图可生成（中文标题、周/日趋势、目标线）\n")
    finally:
        os.environ.pop("FITNESS_DATA_DIR", None)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_set_manager_basic()
    test_set_manager_bulk_and_reset()
    test_user_store()
    test_history_and_goals()
    test_persistence()
    test_score_tracking()
    test_delete_user()
    test_plot_trend()
    print("全部通过 ✅")
