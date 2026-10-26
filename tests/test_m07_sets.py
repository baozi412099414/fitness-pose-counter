"""模块 7 测试 —— 训练组与间歇管理

对应《选题说明》第 11 题功能模块第 7 项：
「支持设定每组次数与组间休息时长，自动记录每组成绩。」
"""

import sys

from harness import suite

if __name__ == "__main__":
    pass


@suite("模块 07 · 训练组与间歇管理")
def _run(t):
    from training_manager import SetManager

    # ---------------- 组数与次数 ----------------
    t.section("3 组 x 10 次，组间休息 30 秒")
    sm = SetManager(sets=3, reps_per_set=10, rest_seconds=30.0)
    now = 1000.0
    events = []
    for i in range(1, 11):
        events += sm.on_rep(i, now=now)
        now += 2.0
    kinds = [e["type"] for e in events]
    t.truthy("做满一组触发 set_done", "set_done" in kinds, detail="事件=%r" % (kinds,))
    t.truthy("做满一组进入组间休息", "rest_start" in kinds, detail="事件=%r" % (kinds,))
    t.truthy("休息剩余时间接近 30 秒", sm.rest_remaining(now=now) > 25,
             detail="剩余=%.1f 秒" % sm.rest_remaining(now=now))

    # ---------------- 休息期间计数隔离 ----------------
    t.section("休息期间外部计数不该被计入下一组")
    before = sm.total_reps
    sm.on_rep(999, now=now)
    t.eq("休息中喂 count=999，累计次数不变", sm.total_reps, before)

    # ---------------- 休息结束 ----------------
    t.section("休息结束后恢复计数")
    now += 31.0
    events = sm.on_rep(sm.total_reps, now=now)
    kinds = [e["type"] for e in events]
    t.truthy("休息结束触发 rest_end", "rest_end" in kinds, detail="事件=%r" % (kinds,))

    # ---------------- 跑完 3 组 ----------------
    t.section("跑完全部 3 组")
    for _set_index in range(2, 4):
        now += 1.0
        base = sm.total_reps
        for i in range(1, 11):
            events = sm.on_rep(base + i, now=now)
            now += 2.0
        kinds = [e["type"] for e in events]
        if "all_done" in kinds:
            break
        now += 31.0
        sm.on_rep(sm.total_reps, now=now)
    t.truthy("最后一组做满触发 all_done",
             "all_done" in [e["type"] for e in events] or sm.finished)
    t.eq("累计次数 = 3 组 x 10 次 = 30", sm.total_reps, 30)
    t.truthy("finished 标记为真", sm.finished)

    # ---------------- 一次喂进多次 ----------------
    t.section("离线回放：一次喂进 12 次应跨过 2 个满组")
    sm2 = SetManager(sets=4, reps_per_set=5, rest_seconds=0.0)
    events = sm2.on_rep(12, now=100.0)
    kinds = [e["type"] for e in events]
    t.eq("12 次应跨过 2 个满组（set_done 计 2 次）", kinds.count("set_done"), 2)
    t.eq("停在当前第 3 组", sm2.current_set, 3)
    t.eq("本组已做 2 次", sm2.reps_in_set, 2)

    # ---------------- 清零 ----------------
    t.section("reset 清零")
    sm2.reset()
    t.eq("清零后回到第 1 组", sm2.current_set, 1)
    t.eq("清零后累计次数为 0", sm2.total_reps, 0)
    t.falsy("清零后 finished 为假", sm2.finished)

    # ---------------- 边界：休息 0 秒 ----------------
    t.section("边界条件：组间休息 0 秒")
    sm3 = SetManager(sets=2, reps_per_set=3, rest_seconds=0.0)
    ev = []
    for i in range(1, 7):
        ev += sm3.on_rep(i, now=10.0 + i)
    t.truthy("休息 0 秒时能连做 6 次触发 all_done", sm3.finished,
             detail="事件=%r" % ([e["type"] for e in ev],))

    # ---------------- 边界：组数/次数为 1 ----------------
    t.section("边界条件：1 组 x 1 次")
    sm4 = SetManager(sets=1, reps_per_set=1, rest_seconds=5.0)
    ev = sm4.on_rep(1, now=50.0)
    t.truthy("1 组 1 次立即 all_done", any(e["type"] == "all_done" for e in ev),
             detail="事件=%r" % ([e["type"] for e in ev],))

    # ---------------- 超额完成 ----------------
    t.section("边界条件：on_rep 的参数是「当前总计数」而不是「新增几次」")
    sm5 = SetManager(sets=4, reps_per_set=5, rest_seconds=0.0)
    sm5.on_rep(5, now=1.0)          # 外部计数器报到 5：第 1 组满
    t.eq("报到 5 时累计 5", sm5.total_reps, 5)
    ev = sm5.on_rep(17, now=2.0)    # 外部计数器涨到 17：本次新增 12
    kinds = [e["type"] for e in ev]
    t.eq("总计数涨到 17 时累计 17（按差值 12 计）", sm5.total_reps, 17)
    t.eq("本组剩余 2 次（12 - 5 - 5）", sm5.reps_in_set, 2)
    t.eq("当前指向下一组（第 4 组，第 3 组已做满 2 次的一半）", sm5.current_set, 4)
    t.eq("新增 12 次里跨过了 2 个满组", kinds.count("set_done"), 2)
    t.section("边界条件：总计数不变/回退时不重复累计")
    before = sm5.total_reps
    sm5.on_rep(17, now=3.0)         # 总计数没变
    t.eq("总计数不变 -> 累计不变", sm5.total_reps, before)
    sm5.on_rep(3, now=4.0)          # 总计数回退（例如外部清零后又开始）
    t.eq("总计数回退 -> 不会减计数、也不多计", sm5.total_reps, before)

    # ---------------- status() 结构 ----------------
    t.section("status() 返回结构")
    st = SetManager(sets=3, reps_per_set=10, rest_seconds=30.0).status()
    t.truthy("status 是 dict", isinstance(st, dict), detail=type(st).__name__)
    for key in ("current_set", "total_reps"):
        t.truthy("status 含字段 %s" % key, key in st, detail="实际字段=%r" % (sorted(st),))


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
