"""模块 8 测试 —— 训练历史与目标

对应《选题说明》第 11 题功能模块第 8 项：
「按日期记录每日总次数与组数并绘制趋势图，同时显示每日或每周目标的完成进度。」
"""

import sys
from datetime import datetime, timedelta

from harness import suite

if __name__ == "__main__":
    pass


def _fresh(t):
    """在临时目录里造一个干净的用户库，避免污染项目真实 data/。"""
    from training_manager import UserStore
    store = UserStore(root=t.tmpdir())
    store.create_user("测试用户")
    store.switch_user("测试用户")
    return store


@suite("模块 08 · 训练历史与目标")
def _run(t):
    from training_manager import UserStore, History, Goals

    # ---------------- 写入与读取 ----------------
    t.section("写入一次训练记录并能读回")
    store = _fresh(t)
    h = History(store, "测试用户")
    rec = h.add_session("squat", 30, sets=3, errors={"not_deep_enough": 2},
                        duration_sec=120.0, source="test", score=78.2)
    t.truthy("add_session 返回记录 dict", isinstance(rec, dict), detail=type(rec).__name__)
    sessions = h.all_sessions()
    t.eq("历史里应有 1 条记录", len(sessions), 1)
    t.eq("记录的动作是 squat", sessions[0].get("action"), "squat")
    t.eq("记录的次数是 30", sessions[0].get("reps"), 30)
    t.near("记录的评分是 78.2", sessions[0].get("score"), 78.2, 1e-6)

    # ---------------- 按动作过滤 ----------------
    t.section("按动作过滤")
    h.add_session("pushup", 20, score=88.3)
    h.add_session("squat", 15, score=60.0)
    t.eq("squat 共 2 条", len(h.sessions(action="squat")), 2)
    t.eq("pushup 共 1 条", len(h.sessions(action="pushup")), 1)
    t.eq("不存在的动作返回 0 条", len(h.sessions(action="pullup")), 0)

    # ---------------- 今日次数 ----------------
    t.section("今日次数（按日期过滤）")
    store2 = _fresh(t)
    h2 = History(store2, "测试用户")
    now = datetime(2026, 3, 15, 10, 0, 0)
    h2.add_session("squat", 10, when=now)
    h2.add_session("squat", 5, when=now)
    h2.add_session("squat", 7, when=now - timedelta(days=1))   # 昨天
    t.eq("今日 squat 共 15 次（不含昨天）", h2.today_reps("squat", now=now), 15)
    t.eq("今日不限动作也是 15 次", h2.today_reps(now=now), 15)
    t.eq("指定 3-14 的 squat 次数为 7", h2.reps_on("2026-03-14", action="squat"), 7)
    t.eq("指定 3-13 无记录为 0", h2.reps_on("2026-03-13", action="squat"), 0)

    # ---------------- 周趋势 ----------------
    t.section("周趋势")
    store3 = _fresh(t)
    h3 = History(store3, "测试用户")
    base = datetime(2026, 3, 15, 9, 0, 0)
    h3.add_session("squat", 12, when=base)
    h3.add_session("squat", 8, when=base - timedelta(days=7))
    trend = h3.weekly_trend("squat", weeks=4, now=base)
    t.eq("周趋势返回 4 个点", len(trend), 4)
    t.truthy("每个点是含 week_start / reps 的 dict",
             all(isinstance(p, dict) and "week_start" in p and "reps" in p for p in trend),
             detail="实际=%r" % (trend,))
    t.eq("最近一周次数为 12", trend[-1]["reps"], 12)
    t.eq("上一周次数为 8", trend[-2]["reps"], 8)
    t.truthy("周起始日期是升序", [p["week_start"] for p in trend] == sorted(p["week_start"] for p in trend),
             detail=[p["week_start"] for p in trend])

    # ---------------- 评分趋势与均值 ----------------
    t.section("评分趋势与近 7 天均值")
    store4 = _fresh(t)
    h4 = History(store4, "测试用户")
    d0 = datetime(2026, 3, 15, 9, 0, 0)
    for i, sc in enumerate([60.0, 70.0, 80.0]):
        h4.add_session("squat", 10, when=d0 - timedelta(days=i), score=sc)
    h4.add_session("squat", 10, when=d0 - timedelta(days=5))   # 无评分
    t.near("近 7 天均值 = (60+70+80)/3 = 70", h4.avg_score("squat", days=7, now=d0), 70.0, 0.2)
    t.eq("无分数时返回 None（参数不存在的动作）", h4.avg_score("pullup", days=7, now=d0), None)
    st = h4.score_trend("squat", days=14, now=d0)
    scored = [p for p in st if p["score"] is not None]
    t.eq("评分趋势里只有 3 天有分（其余占位 None）", len(scored), 3)
    t.truthy("有分的三天数值正确（按日期升序 80/70/60）",
             [p["score"] for p in scored] == [80.0, 70.0, 60.0],
             detail=[p["score"] for p in scored])
    t.eq("评分趋势覆盖完整 14 天窗口", len(st), 14)

    # ---------------- 高频错误汇总 ----------------
    t.section("错误汇总（按次数降序）")
    store5 = _fresh(t)
    h5 = History(store5, "测试用户")
    h5.add_session("squat", 10, errors={"not_deep_enough": 4, "knee_over_toe": 2})
    h5.add_session("squat", 10, errors={"not_deep_enough": 3})
    summ = h5.error_summary("squat")
    t.eq("not_deep_enough 累计 7 次", summ.get("not_deep_enough"), 7)
    t.eq("knee_over_toe 累计 2 次", summ.get("knee_over_toe"), 2)
    t.truthy("汇总按次数降序（第一个是最多的）",
             list(summ)[0] == "not_deep_enough", detail="实际=%r" % (summ,))

    # ---------------- 目标与达成率 ----------------
    t.section("每日目标与达成率")
    store6 = _fresh(t)
    h6 = History(store6, "测试用户")
    g6 = Goals(store6, "测试用户")
    now6 = datetime(2026, 3, 15, 20, 0, 0)
    h6.add_session("squat", 35, when=now6)
    g6.set_goal("squat", 40)
    prog = g6.progress("squat", h6, now=now6)
    t.eq("已完成 35 次", prog["done"], 35)
    t.eq("目标 40 次", prog["target"], 40)
    t.near("达成率 0.875（保留 3 位）", prog["ratio"], 0.875, 1e-3)
    t.falsy("未达成", prog["reached"])
    t.eq("还差 5 次", prog["remaining"], 5)

    g6.set_goal("squat", 30)
    prog2 = g6.progress("squat", h6, now=now6)
    t.truthy("目标降到 30 后达成", prog2["reached"])
    t.near("达成率封顶为 1.0", prog2["ratio"], 1.0, 1e-9)

    t.section("目标边界：未设目标 / 清零目标")
    g6.clear_goal("squat")
    prog3 = g6.progress("squat", h6, now=now6)
    t.eq("未设目标时 target=0", prog3["target"], 0)
    t.falsy("未设目标时 reached=False", prog3["reached"])
    t.eq("未设目标时 ratio=0.0", prog3["ratio"], 0.0)

    # ---------------- all_progress ----------------
    t.section("all_progress 覆盖全部已设目标")
    g6.set_goal("squat", 40)
    g6.set_goal("pushup", 20)
    allp = g6.all_progress(h6, now=now6)
    t.eq("应返回 2 个动作的进度", len(allp), 2)
    t.truthy("包含 squat 和 pushup", set(allp) == {"squat", "pushup"}, detail=sorted(allp))

    # ---------------- 持久化 ----------------
    t.section("持久化：重新构造对象后数据仍在")
    store7 = _fresh(t)
    h7 = History(store7, "测试用户")
    g7 = Goals(store7, "测试用户")
    h7.add_session("squat", 25, score=66.6)
    g7.set_goal("squat", 30)
    h7b = History(store7, "测试用户")
    g7b = Goals(store7, "测试用户")
    t.eq("重启后历史仍是 1 条", len(h7b.all_sessions()), 1)
    t.eq("重启后目标仍是 30", g7b.get_goal("squat"), 30)


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
