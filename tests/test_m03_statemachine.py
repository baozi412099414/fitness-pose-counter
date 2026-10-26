"""模块 03 测试 —— 动作状态机与计数（准备 / 下压 / 还原 三态迁移与防抖防重复）

对应《选题说明》第 11 题「功能模块」第 3 项：动作状态机与计数。
用例直接喂 RepCounter.update(信号值, now=秒)，不依赖摄像头；阈值、enter_hold、
exit_hold、min_interval 全部从 configs/squat.json 的真实值取，改配置后仍然有效。
"""

import json
import os
import sys

from harness import ROOT, suite
from pose_logic import RepCounter

with open(os.path.join(ROOT, "configs", "squat.json"), encoding="utf-8") as f:
    SQUAT = json.load(f)["counter"]          # lo=140 / hi=155 是深蹲的真实双阈值

STAND, DOWN = 170.0, 130.0                  # 站直（>hi）/ 蹲到位（<lo）
BAND = (141, 154)                           # lo 与 hi 之间的迟滞区


def counter(**over):
    """用 squat.json 的真实计数配置建状态机；只覆盖本用例真正要测的字段。"""
    cfg = dict(SQUAT)
    cfg.update(over)
    return RepCounter(cfg)


def one_rep(t0, stand=STAND, down=DOWN):
    """一次完整往返：0.6 秒内走完（蹲下 2 帧 → 还原 2 帧）。"""
    return [(t0 + 0.00, stand), (t0 + 0.10, down), (t0 + 0.20, down),
            (t0 + 0.50, stand), (t0 + 0.60, stand)]


def play(c, frames):
    """按 (时间, 信号值) 序列喂帧，返回最后一次 update 的 (count, stage)。"""
    last = (c.count, c.stage)
    for now, value in frames:
        last = c.update(value, now)
    return last


@suite("模块 03 · 动作状态机与计数")
def _run(t):
    t.section("一、完整往返 = 1 次")
    c = counter()
    c.update(STAND, 0.0)
    c.update(DOWN, 0.10)
    c.update(DOWN, 0.20)
    mid = c.stage
    count, stage = play(c, [(0.50, STAND), (0.60, STAND)])
    t.check("170°→130°→170°（完整下压再还原）→ 下压中 active，还原后计 1 次并回 ready",
            mid == "active" and count == 1 and stage == "ready",
            "下压中阶段=%r；还原后计数=%r 阶段=%r" % (mid, count, stage))

    t.section("二、迟滞防抖：阈值边缘反复抖动不计数")
    c = counter()
    play(c, one_rep(0.0))
    before = c.count
    play(c, [(1.0 + i * 0.2, v) for i, v in enumerate([141, 154, 142, 153, 145, 150])])
    band_ok = c.count == before and c.stage == "ready"
    play(c, [(2.5, 156.0), (2.6, 150.0)])      # 只一帧冒过 hi，不够 exit_hold 就落回
    t.check("141~154（lo=140~hi=155 的迟滞区内）抖动 6 帧、再单帧冒到 156 → 计数不增加",
            band_ok and c.count == before,
            "抖动前=%r 抖动后=%r（迟滞区=%r~%r）" % (before, c.count, BAND[0], BAND[1]))

    t.section("三、防重复计数：停在已计数的位置不再加数")
    c = counter()
    play(c, one_rep(0.0))
    for i in range(12):
        c.update(STAND, 1.0 + i * 0.1)
    t.check("计满 1 次后继续喂 12 帧 170°（人站着不动）→ 计数仍为 1，不因停留重复计数",
            c.count == 1 and c.stage == "ready", "计数=%r 阶段=%r" % (c.count, c.stage))

    t.section("四、单帧跳变：一帧异常值不该改变状态")
    c = counter()
    play(c, [(0.0, 150.0), (0.1, 30.0), (0.2, 150.0)])   # 一帧掉到 30° 立刻回来
    spike = (c.count, c.stage)
    count, stage = play(c, one_rep(1.0))                  # 随后做一次真正的往返
    t.check("150°→30°→150° 只插一帧异常值 → 计数 0 且仍 ready；之后正常一次仍计 1",
            spike == (0, "ready") and count == 1 and stage == "ready",
            "跳变后=%r；再正常一次=%r" % (spike, (count, stage)))

    t.section("五、不完整动作不计数")
    c = counter()
    play(c, [(0.0, STAND), (0.1, DOWN), (0.2, DOWN), (0.6, DOWN), (2.0, DOWN)])
    t.check("只下压不起身（蹲到底停 2 秒）→ 计数 0，停在 active 等还原",
            c.count == 0 and c.stage == "active", "计数=%r 阶段=%r" % (c.count, c.stage))
    c = counter()
    play(c, [(0.0, STAND), (0.1, 145.0), (0.4, 145.0), (0.8, 145.0)])
    t.check("只蹲一半（145° 未穿过 lo=140°）→ 计数 0 且始终 ready，不算一次动作",
            c.count == 0 and c.stage == "ready",
            "计数=%r 阶段=%r（145° 落在迟滞区，未触发下压）" % (c.count, c.stage))

    t.section("六、min_interval：两次计数间隔太近时第二次被拒绝")
    c = counter(min_interval=2.0)                 # 调大只为让「间隔守门」单独起作用
    c1, _ = play(c, one_rep(0.0))                 # 0.6s 计第 1 次
    c2, _ = play(c, one_rep(0.8))                 # 1.4s 结束，间隔 0.8s < 2.0s → 应被拒
    c3, _ = play(c, one_rep(2.8))                 # 3.4s 结束，间隔 2.8s ≥ 2.0s → 计入
    t.check("连做三次：第 2 次（间隔 0.8s < min_interval=2.0s）被拒，第 3 次（2.8s）才计",
            c1 == 1 and c2 == 1 and c3 == 2, "三次计数序列=%r,%r,%r（预期 1,1,2）" % (c1, c2, c3))
    inverted = {k: v for k, v in SQUAT.items() if k != "min_active_duration"}
    inverted.update({"lo": 160, "hi": 140})        # 阈值写反：lo > hi，迟滞区不成立
    c = RepCounter(inverted)
    play(c, [(i * 0.1, 150.0) for i in range(30)])  # 人站着不动，信号恒为 150°
    t.check("【记录当前行为】阈值写反（lo=160>hi=140）且没配 min_active_duration 时，"
            "恒定 150° 也会每 0.6s 数一次 → 计数=%r（期望应为 0）" % c.count, c.count > 0,
            "缺陷：解释器自己不校验 lo<hi，只靠 validate_config 拦（见模块 02）；"
            "手写配置绕过校验器就会出现「站着不动一直加数」")

    t.section("七、enter_hold / exit_hold 时间确认（用配置真实值）")
    enter_hold = float(SQUAT["enter_hold"])
    c = counter()
    c.update(DOWN, 0.0)
    single = c.stage
    c.update(DOWN, enter_hold / 2)
    half = c.stage
    c.update(DOWN, enter_hold)
    full = c.stage
    t.check("单帧到达 lo 不迁移：不足 enter_hold（%.2fs）保持 ready，连续保持满才进 active"
            % enter_hold, single == "ready" and half == "ready" and full == "active",
            "1 帧=%r、%.3fs=%r、%.2fs=%r" % (single, enter_hold / 2, half, enter_hold, full))
    exit_hold = float(SQUAT["exit_hold"])
    c = counter()
    play(c, [(0.0, STAND), (0.1, DOWN), (0.2, DOWN)])       # 0.2s 进入 active
    c.update(STAND, 0.5)                                     # 回到还原位，开始计时
    c.update(STAND, 0.5 + exit_hold / 2)
    early = (c.count, c.stage)
    c.update(STAND, 0.5 + exit_hold)
    t.check("回到 hi 后不足 exit_hold（%.2fs）不计数，连续保持满才计 1 次" % exit_hold,
            early == (0, "active") and c.count == 1 and c.stage == "ready",
            "半程=%r；满程后计数=%r 阶段=%r" % (early, c.count, c.stage))
    c = counter()
    play(c, [(0.0, STAND), (0.1, DOWN), (0.2, DOWN), (0.3, STAND), (0.4, STAND)])
    t.check("动作只持续 0.10s（< min_active_duration=%.2fs）的快速上下 → 结束本轮但不计数"
            % float(SQUAT["min_active_duration"]), c.count == 0 and c.stage == "ready",
            "计数=%r 阶段=%r（时长不足按关键点跳变处理）" % (c.count, c.stage))

    t.section("八、reset() 与 cycle_progress")
    c = counter()
    play(c, one_rep(0.0))
    play(c, one_rep(0.8))
    before = (c.count, c.stage)
    c.reset()
    cleared = (c.count, c.stage, c.cycle_progress)
    after_reset, _ = play(c, one_rep(0.0))
    t.check("计满 2 次后 reset() → 计数/阶段/循环进度全清零，且立刻能重新计 1 次（时间戳也清了）",
            before == (2, "ready") and cleared == (0, "ready", 0) and after_reset == 1,
            "清零前=%r 清零后=%r 再计=%r" % (before, cleared, after_reset))
    c = counter(cycles_per_rep=2)
    first, _ = play(c, one_rep(0.0))
    progress = c.cycle_progress
    second, _ = play(c, one_rep(0.8))
    t.check("cycles_per_rep=2：第 1 个往返只攒进度（计数 0、progress 1），第 2 个往返才计 1 次",
            first == 0 and progress == 1 and second == 1 and c.cycle_progress == 0,
            "第 1 轮计数=%r 进度=%r；第 2 轮计数=%r 进度=%r"
            % (first, progress, second, c.cycle_progress))


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
