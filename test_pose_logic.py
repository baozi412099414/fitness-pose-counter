#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用合成数据验证动作配置解释器（不依赖摄像头 / MediaPipe）。

跑法：
    .venv/bin/python test_pose_logic.py
"""

import time
from unittest.mock import patch

from pose_logic import RepCounter, QualityChecker, load_action


def test_rep_counter():
    print("=== 测试 1：俯卧撑计数（合成肘角序列） ===")
    c = RepCounter({"lo": 90, "hi": 160, "first": "lo", "min_interval": 0.3})
    # 一次完整俯卧撑：165(伸直) -> 90(下压) -> 165(撑起)，下压途中在 90 附近抖两下
    seq = [165, 165, 150, 130, 110, 95, 92, 90, 92, 90, 100, 120, 140, 155, 160, 165, 165]
    now = 0.0
    for s in seq:
        now += 0.1
        count, stage = c.update(s, now)
        print(f"  角度 {s:5.1f}° -> 阶段 {stage:6s} 计数 {count}")
    assert c.count == 1, f"期望 1 次，实际 {c.count}"
    print(f"  ✅ 一次完整俯卧撑，计数 = {c.count}\n")


def test_hysteresis():
    print("=== 测试 2：迟滞防抖（阈值边缘抖动不重复计数） ===")
    c = RepCounter({"lo": 90, "hi": 160, "first": "lo", "min_interval": 0.3})
    now = 0.0
    for s in [165, 120, 90, 120, 165]:   # 先完整做一次
        now += 0.1
        c.update(s, now)
    before = c.count
    for s in [159, 161, 159, 161, 158, 162, 159]:   # 在 hi=160 附近反复抖
        now += 0.05
        c.update(s, now)
    print(f"  抖动前 {before} 次，抖动后 {c.count} 次")
    assert c.count == before, "边缘抖动不应增加计数"
    print("  ✅ 迟滞区挡住了抖动\n")


def test_quality():
    print("=== 测试 3：质量判定（塌腰检测） ===")
    q = QualityChecker([
        {"name": "low_back", "check": "collinear", "points": [11, 23, 27],
         "min_angle": 165, "tip": "身体没绷直，塌腰了"}
    ])
    pts = [(0, 0)] * 33
    pts[11] = (100, 100)   # 肩
    pts[27] = (200, 200)   # 踝
    # 标准：肩-髋-踝三点在一条直线上（共线角 180°）
    pts[23] = (150, 150)
    checks = q.check(pts)
    print(f"  标准姿态: 共线度 {checks[0]['value']:.1f}° / 阈值 {checks[0]['limit']}° -> {q.hits(checks) or '(无)'}")
    assert not q.hits(checks), "标准姿态不应报错"
    # 塌腰：髋下沉，共线角变小
    pts[23] = (150, 190)
    checks = q.check(pts)
    print(f"  塌腰姿态: 共线度 {checks[0]['value']:.1f}° / 阈值 {checks[0]['limit']}° -> {q.hits(checks)}")
    assert q.hits(checks), "塌腰应该被检出"
    print("  ✅ 塌腰被正确检出\n")


def test_invisible_points():
    print("=== 测试 5：关键点不可见时不误报（照不全身体的场景） ===")
    q = QualityChecker([
        {"name": "low_back", "check": "collinear", "points": [11, 23, 27],
         "min_angle": 165, "tip": "塌腰"}
    ])
    pts = [(0, 0)] * 33
    pts[11] = (100, 100)
    pts[23] = (150, 190)   # 塌腰姿态
    pts[27] = (200, 200)
    # 关键点都拍到了 -> 应该报
    vis_all = [1.0] * 33
    checks = q.check(pts, vis_all)
    print("  关键点都可见 ->", q.hits(checks))
    assert q.hits(checks), "可见时塌腰应被检出"
    # 脚踝出画（visibility 很低）-> 不该报，而是标记为不可见
    vis_hidden = [1.0] * 33
    vis_hidden[27] = 0.1
    checks = q.check(pts, vis_hidden)
    print("  脚踝出画     -> hits:", q.hits(checks), "  visible:", checks[0]["visible"])
    assert not q.hits(checks), "关键点不可见时不应误报"
    assert checks[0]["visible"] is False, "应标记为不可见"
    print("  ✅ 拍不到就不判定，交给上层提示调整机位\n")


def test_load_and_update():
    print("=== 测试 4：整条链路（读 JSON → 算角度 → 状态机 → 质量明细） ===")
    action = load_action("configs/pushup.json")
    print(f"  已加载动作：{action.name}（{action.id}），信号类型 {action.signal_type}")
    # 构造一个明确姿态：肩(100,100)、肘(100,120)、腕(100,200) 三点竖直共线 => 肘角 180°
    pts = [(0, 0)] * 33
    pts[11] = (100, 100)
    pts[13] = (100, 120)
    pts[15] = (100, 200)
    pts[23] = (150, 150)
    pts[27] = (200, 200)
    pts[12], pts[14], pts[16] = (300, 100), (300, 120), (300, 200)
    pts[24], pts[28] = (350, 150), (400, 200)
    sig = action.signal(pts)
    print(f"  肘角 = {sig:.1f}°（预期 180°）")
    assert abs(sig - 180) < 0.5, f"肘角应接近 180，实际 {sig}"
    vis = [1.0] * 33
    count, stage, s, hits, checks = action.update(pts, vis)
    print(f"  update -> 计数 {count} 阶段 {stage}")
    for c in checks:
        print(f"    [{c['name']}] 实测 {c['value']:.1f}° / 阈值 {c['limit']}°  "
              f"可见={c['visible']} 本阶段判={c['checked']} 达标={c['ok']}")
    print("  ✅ 读配置 + 算角度 + 状态机 + 质量明细 全链路跑通\n")


def test_stage_filter():
    print("=== 测试 6：约束只在指定阶段判定（避免动作过程中误报） ===")
    q = QualityChecker([
        {"name": "arm_not_straight", "check": "angle_min", "points": [11, 13, 15],
         "min": 150, "when": "ready", "tip": "没伸直"}
    ])
    pts = [(0, 0)] * 33
    pts[11] = (100, 100)
    pts[13] = (160, 150)   # 肘外展 -> 肘角约 80°（像弯举 / 下压过程中的姿态）
    pts[15] = (100, 200)
    vis = [1.0] * 33
    # 动作阶段（active）：不该判「没伸直」
    checks = q.check(pts, vis, stage="active")
    print(f"  active 阶段 -> hits {q.hits(checks)}   本阶段判={checks[0]['checked']}")
    assert not q.hits(checks), "active 阶段不该判「没伸直」"
    # 还原阶段（ready）：该判，这里肘角小 -> 应报
    checks = q.check(pts, vis, stage="ready")
    print(f"  ready  阶段 -> hits {q.hits(checks)}   本阶段判={checks[0]['checked']}")
    assert q.hits(checks), "ready 阶段肘角小应报「没伸直」"
    print("  ✅ 约束只在指定阶段生效，动作过程中不再误报\n")


def test_no_count_without_person():
    print("=== 测试 7：人没拍到时不该计数（幽灵骨架不加数） ===")
    action = load_action("configs/squat.json")
    # 蹲下姿态：膝角约 87°（若不看可信度，这帧会触发 active）
    down = [(0, 0)] * 33
    down[23] = (100, 100)
    down[25] = (160, 140)
    down[27] = (100, 220)
    down[11], down[12] = (100, 40), (300, 40)
    down[24], down[26], down[28] = (300, 100), (360, 140), (300, 220)
    down[31], down[32] = (100, 220), (300, 220)
    # 站起姿态：三点竖直共线 => 膝角 180°
    up = [(0, 0)] * 33
    up[23] = (100, 100)
    up[25] = (100, 160)
    up[27] = (100, 220)
    up[11], up[12] = (100, 40), (300, 40)
    up[24], up[26], up[28] = (300, 100), (300, 160), (300, 220)
    up[31], up[32] = (100, 220), (300, 220)

    vis_bad = [0.1] * 33      # 人没拍到 / 目标跟丢
    vis_ok = [1.0] * 33       # 人在画面里

    c1, s1, sig1, _, _ = action.update(down, vis_bad, now=0.0)
    print(f"  可信度 0.1（没人）+ 蹲下姿态 -> REPS {c1}  阶段 {s1}（应保持 0 / ready）")
    assert c1 == 0 and s1 == "ready", "人没拍到时不该改变计数状态"

    action.update(down, vis_ok, now=1.0)                         # 持续蹲下，过滤单帧跳变
    action.update(down, vis_ok, now=1.1)                         # -> active
    action.update(up, vis_ok, now=1.5)                           # 持续站起
    c2, s2, sig2, _, _ = action.update(up, vis_ok, now=1.6)      # -> 计 1
    print(f"  可信度 1.0（有人）+ 蹲下再站起 -> REPS {c2}  阶段 {s2}  膝角 {sig2:.0f}°")
    assert c2 == 1, f"有人时一次完整深蹲应计 1，实际 {c2}"
    print("  ✅ 没人不加数，有人正常加数\n")


def test_peak_judgment():
    print("=== 测试 8：峰值判定（看本轮最高站到多少，不看计数那一刻） ===")
    vis = [1.0] * 33

    def knee_pts(offset):
        """offset 越大膝角越小：3≈174°（站直）, 10≈161°（差一点）, 60≈90°（蹲下）"""
        p = [(0, 0)] * 33
        p[23] = (100, 100)
        p[25] = (100 + offset, 160)
        p[27] = (100, 220)
        p[11], p[12] = (100, 40), (300, 40)
        p[24], p[26], p[28] = (300, 100), (300 + offset, 160), (300, 220)
        p[31], p[32] = (100, 220), (300, 220)
        return p

    # 场景 1：先站到 174° 再蹲 -> 本轮峰值 174°，站起计数时不该报
    a = load_action("configs/squat.json")
    a.update(knee_pts(3), vis, now=0.0)                              # 站着 174°
    a.update(knee_pts(60), vis, now=1.0)
    a.update(knee_pts(60), vis, now=1.1)                             # 持续蹲下 -> active
    a.update(knee_pts(10), vis, now=1.5)
    c, s, sig, hits, _ = a.update(knee_pts(10), vis, now=1.6)        # 持续站起 -> 计数
    print(f"  站在 174° 后深蹲：计数时 sig={sig:.1f}°  报错 {[h['name'] for h in hits]}")
    assert c == 1, "应计 1 次"
    assert not hits, "本轮峰值 174° >= 162°，不该报「没伸直」"

    # 场景 2：全程只站到约 158° -> 能越过宽松计数线，但没有达到质量标准
    a2 = load_action("configs/squat.json")
    a2.update(knee_pts(12), vis, now=0.0)
    a2.update(knee_pts(60), vis, now=1.0)
    a2.update(knee_pts(60), vis, now=1.1)
    a2.update(knee_pts(12), vis, now=1.5)
    c, s, sig, hits, _ = a2.update(knee_pts(12), vis, now=1.6)
    print(f"  只站到 {sig:.0f}° 后深蹲：报错 {[h['name'] for h in hits]}")
    assert c == 1, "应计 1 次"
    assert hits, "越过计数线但没达到 160° 质量标准，应报「没伸直」"
    print("  ✅ 判定看本轮峰值，而不是「刚过计数线那一帧」的角度\n")


def test_depth_judgment():
    print("=== 测试 9：蹲下深度判定（用下蹲阶段谷值，准确不滞后） ===")
    vis = [1.0] * 33

    def knee_pts(offset):
        """3≈174°（站直）, 35≈120°（只蹲一点）, 60≈90°（蹲够深）"""
        p = [(0, 0)] * 33
        p[23] = (100, 100)
        p[25] = (100 + offset, 160)
        p[27] = (100, 220)
        p[11], p[12] = (100, 40), (300, 40)
        p[24], p[26], p[28] = (300, 100), (300 + offset, 160), (300, 220)
        p[31], p[32] = (100, 220), (300, 220)
        return p

    # 场景 1：蹲到 90° -> 深度够，不该报
    a = load_action("configs/squat.json")
    a.update(knee_pts(3), vis, now=0.0)                          # 站着
    _, _, sig_down, _, _ = a.update(knee_pts(60), vis, now=1.0)
    a.update(knee_pts(60), vis, now=1.1)
    a.update(knee_pts(3), vis, now=1.5)
    c, s, sig, hits, _ = a.update(knee_pts(3), vis, now=1.6)
    print(f"  蹲到 {sig_down:.0f}° 再站起 -> 报错 {[h['name'] for h in hits]}（应为空）")
    assert c == 1, "应计 1 次"
    assert not hits, "蹲够深了不该报"

    # 场景 2：只蹲到约 120° -> 深度不够，应报
    a2 = load_action("configs/squat.json")
    a2.update(knee_pts(3), vis, now=0.0)
    _, _, sig_down2, _, _ = a2.update(knee_pts(35), vis, now=1.0)
    a2.update(knee_pts(35), vis, now=1.1)
    a2.update(knee_pts(3), vis, now=1.5)
    c, s, sig, hits, _ = a2.update(knee_pts(3), vis, now=1.6)
    print(f"  只蹲到 {sig_down2:.0f}° 再站起 -> 报错 {[h['name'] for h in hits]}")
    assert c == 1, "蹲了一点也算一次（计数宽松）"
    assert any(h["name"] == "not_deep_enough" for h in hits), "应报「蹲得不够深」"
    print("  ✅ 下蹲深度判定准确（谷值在计数那一刻已完整）\n")


def test_jumping_jack():
    print("=== 测试 10：开合跳（双臂 + 双腿同步计数与质量约束） ===")
    action = load_action("configs/jumping_jack.json")
    print(f"  计数条件 {len(action.conditions)} 个，质量约束 {len(action.quality.rules)} 条")
    L_SHOULDER, R_SHOULDER = (200, 300), (350, 300)
    L_HIP, R_HIP = (200, 400), (350, 400)
    L_DOWN, L_SHOULDER_HIGH, L_UP = (200, 400), (300, 300), (200, 100)
    R_DOWN, R_SHOULDER_HIGH, R_UP = (350, 400), (250, 300), (350, 100)
    CLOSE, OPEN, HALF_OPEN = 25, 100, 75

    def pose(left_elbow, right_elbow, foot_half=CLOSE):
        p = [(0, 0)] * 33
        p[11], p[12] = L_SHOULDER, R_SHOULDER
        p[13], p[14] = left_elbow, right_elbow
        p[23], p[24] = L_HIP, R_HIP
        p[27] = (275 - foot_half, 700)
        p[28] = (275 + foot_half, 700)
        return p

    vis = [1.0] * 33

    def rep(a, opened):
        closed = pose(L_DOWN, R_DOWN)
        a.update(closed, vis, now=0.0)
        _, _, opened_sig, _, _ = a.update(opened, vis, now=0.5)
        a.update(opened, vis, now=0.6)
        a.update(closed, vis, now=1.0)
        result = a.update(closed, vis, now=1.1)
        return opened_sig, result

    # 1 标准开合跳（手举过头 + 脚张开）
    sig_up, (c, s, sig, hits, _) = rep(action, pose(L_UP, R_UP, OPEN))
    print(f"  1 标准开合跳（肩角 {sig_up:.0f} 度）-> 计数 {c}，报错 {[h['name'] for h in hits]}（应为空）")
    assert c == 1, "标准动作应计 1 次"
    assert not hits, "标准动作不该报错"

    # 2 手只举到肩膀高度（90 度：过了进入门槛 60 度，但没到举过头标准 150 度）
    a2 = load_action("configs/jumping_jack.json")
    shoulder_sig, (c, s, sig, hits, _) = rep(a2, pose(L_SHOULDER_HIGH, R_SHOULDER_HIGH, OPEN))
    print(f"  2 手只举到肩高（肩角 {shoulder_sig:.0f} 度）-> 计数 {c}，报错 {[h['name'] for h in hits]}")
    assert c == 1, "过了进入门槛也算一次"
    assert any(h["name"] == "hand_not_up" for h in hits), "应报「手没举过头顶」"

    # 3 手举过头、但腿没张开
    a3 = load_action("configs/jumping_jack.json")
    _, (c, s, sig, hits, _) = rep(a3, pose(L_UP, R_UP, HALF_OPEN))
    print(f"  3 手举过头但腿只张开一半 -> 计数 {c}，报错 {[h['name'] for h in hits]}")
    assert any(h["name"] == "legs_not_apart" for h in hits), "应报「腿没张开」"

    # 4 手只抬到胸前（约 30 度，没过进入门槛 60 度）-> 不算一次动作
    a4 = load_action("configs/jumping_jack.json")
    _, (c, s, sig, hits, _) = rep(a4, pose((250, 387), (300, 387), OPEN))
    print(f"  4 手只抬到胸前 -> 计数 {c}（应为 0，不算一次动作）")
    assert c == 0, "没举过肩不该算一次动作"
    print("  双臂和双腿必须同步；幅度不足仍可计数并给出明确提醒")



def test_abnormal_frame_dropped():
    print("=== 测试 11：关键点异常帧被丢弃（肩宽趋近 0 时不产生离谱比值） ===")
    a = load_action("configs/jumping_jack.json")

    def pts(shoulder_w):
        p = [(0, 0)] * 33
        p[11] = (150, 100)
        p[12] = (150 + shoulder_w, 100)     # 肩宽可变（腿距归一化用）
        p[27] = (100, 400)                  # 两脚左右张开 100px
        p[28] = (200, 400)
        return p

    # 腿距信号 = dx / 肩宽，肩宽只剩 2px 时应该判为异常帧，而不是算出 50 倍这种离谱值
    bad = a._calc_signal("dx", pts(2), [27, 28], [11, 12])
    print(f"  肩宽 2px   -> 腿距信号 {bad}（应是 None，被丢弃）")
    assert bad is None, "肩宽过小应判为异常帧"

    good = a._calc_signal("dx", pts(100), [27, 28], [11, 12])
    print(f"  肩宽 100px -> 腿距信号 {good:.2f}（正常）")
    assert good is not None and 0.9 < good < 1.1, "正常帧应算出 ≈1.0"

    # 角度类信号不依赖归一化，不会被异常肩宽影响
    ang = a._calc_signal("angle", pts(2), [13, 11, 23])
    print(f"  肩角信号（不依赖归一化）-> {ang:.1f} 度")
    print("  异常帧不会污染距离类约束的峰值")


def test_reset_clears_cycle_state():
    print("=== 测试 12：清零同时清除本轮动作状态 ===")
    a = load_action("configs/squat.json")
    a.counter.count = 3
    a.counter.stage = "active"
    a.sig_peak = 175.0
    a.depth_valley = 88.0
    a.rule_ext = {"demo": {"peak": 2.0, "valley": 1.0}}
    a.last_values = [123.0]
    a.unit_smooth = 100.0
    a.reset()
    assert a.counter.count == 0 and a.counter.stage == "ready"
    assert a.sig_peak is None and a.depth_valley is None and a.unit_smooth is None
    assert a.rule_ext == {} and a.last_values == [] and a.unit_smooth is None
    print("  计数、阶段、峰值、谷值和规则极值均已清除")


def test_low_confidence_does_not_pollute_counter_extrema():
    print("=== 测试 13：低可信度帧不污染计数信号极值 ===")
    a = load_action("configs/squat.json")
    pts = [(0, 0)] * 33
    pts[23], pts[25], pts[27] = (100, 100), (100, 160), (100, 220)
    vis = [1.0] * 33
    vis[25] = 0.1
    a.update(pts, vis, now=0.0)
    assert a.sig_peak is None and a.depth_valley is None
    assert a.counter.count == 0 and a.counter.stage == "ready"
    print("  幽灵骨架既不计数，也不写入峰值/谷值")


def test_hidden_quality_points_do_not_pollute_rule_extrema():
    print("=== 测试 14：质量规则关键点不可见时不写入规则极值 ===")
    a = load_action("configs/jumping_jack.json")
    pts = [(0, 0)] * 33
    pts[11], pts[12], pts[13], pts[23] = (100, 100), (200, 100), (100, 200), (100, 300)
    pts[27], pts[28] = (0, 500), (300, 500)
    vis = [1.0] * 33
    vis[27] = vis[28] = 0.1
    a.update(pts, vis, now=0.0)
    assert "legs_not_apart" not in a.rule_ext
    print("  脚踝不可见时，腿部质量规则不会记录虚假峰值")


def test_camera_thread_stops_cleanly():
    print("=== 测试 15：摄像头线程可正常停止并 join ===")
    from realtime_pose import Camera

    class FakeCapture:
        def __init__(self):
            self.released = False

        def isOpened(self):
            return True

        def set(self, *_):
            return True

        def read(self):
            return False, None

        def release(self):
            self.released = True

    fake = FakeCapture()
    with patch("realtime_pose.cv2.VideoCapture", return_value=fake):
        cam = Camera(0)
        cam.start()
        time.sleep(0.02)
        cam.stop()
    assert not cam.is_alive() and fake.released
    print("  stop() 后线程退出、资源释放，未覆盖 Thread._stop()")


def test_transition_hold_rejects_single_frame_glitch():
    print("=== 测试 16：单帧跳变不触发动作阶段或计数 ===")
    c = RepCounter({
        "lo": 90, "hi": 160, "first": "lo", "min_interval": 0.3,
        "enter_hold": 0.06, "exit_hold": 0.06, "min_active_duration": 0.2,
    })
    c.update(80, now=0.00)       # 只有一个异常低值
    c.update(170, now=0.04)      # 未持续 60ms 就恢复
    assert c.stage == "ready" and c.count == 0

    c.update(80, now=0.10)
    c.update(80, now=0.18)       # 已进入 active
    c.update(170, now=0.20)
    c.update(170, now=0.28)      # active 仅 20ms，整轮丢弃
    assert c.stage == "ready" and c.count == 0

    c.update(80, now=1.00)
    c.update(80, now=1.08)       # 持续满足，进入 active
    c.update(170, now=1.30)
    c.update(170, now=1.38)      # 持续还原，计 1
    assert c.stage == "ready" and c.count == 1
    for t in (1.40, 1.50, 1.60):
        c.update(170, now=t)     # 停在还原位不能重复计数
    assert c.count == 1
    print("  单帧异常被过滤，完整往返计一次，停在原位不重复")


def test_jumping_jack_rejects_walking_and_partial_moves():
    print("=== 测试 17：走路、单边摆臂和只张腿不算开合跳 ===")
    vis = [1.0] * 33

    def pose(left_up=False, right_up=False, legs_open=False):
        p = [(0, 0)] * 33
        p[11], p[12] = (200, 300), (350, 300)
        p[23], p[24] = (200, 400), (350, 400)
        p[13] = (200, 100) if left_up else (200, 400)
        p[14] = (350, 100) if right_up else (350, 400)
        half = 100 if legs_open else 25
        p[27], p[28] = (275 - half, 700), (275 + half, 700)
        return p

    cases = {
        "walking": [
            pose(), pose(True, False, True), pose(True, False, True), pose(),
            pose(False, True, True), pose(False, True, True), pose(),
        ],
        "arms_only": [pose(), pose(True, True, False), pose(True, True, False), pose()],
        "legs_only": [pose(), pose(False, False, True), pose(False, False, True), pose()],
    }
    for name, frames in cases.items():
        a = load_action("configs/jumping_jack.json")
        for i, frame in enumerate(frames):
            a.update(frame, vis, now=i * 0.1)
        print(f"  {name:10s} -> 计数 {a.counter.count}")
        assert a.counter.count == 0
    print("  只有双臂抬起与双腿打开同步发生，才进入开合跳动作阶段")


def test_partial_motion_does_not_contaminate_next_rep_quality():
    print("=== 测试 18：未成形动作不污染下一次完整动作的质量判定 ===")
    a = load_action("configs/jumping_jack.json")
    vis = [1.0] * 33

    def pose(arm_position, legs_open):
        p = [(0, 0)] * 33
        p[11], p[12] = (200, 300), (350, 300)
        p[23], p[24] = (200, 400), (350, 400)
        if arm_position == "up":
            p[13], p[14] = (200, 100), (350, 100)
        elif arm_position == "half":
            p[13], p[14] = (300, 300), (250, 300)
        else:
            p[13], p[14] = (200, 400), (350, 400)
        half = 100 if legs_open else 25
        p[27], p[28] = (275 - half, 700), (275 + half, 700)
        return p

    # 先只举手、不张腿：不是一次开合跳，不应成为后续动作的质量峰值。
    a.update(pose("down", False), vis, now=0.0)
    a.update(pose("up", False), vis, now=0.2)
    a.update(pose("up", False), vis, now=0.3)
    a.update(pose("down", False), vis, now=0.4)

    # 再完成一次幅度偏小但可计数的动作，应该报双手没有举高。
    a.update(pose("half", True), vis, now=1.0)
    a.update(pose("half", True), vis, now=1.1)
    a.update(pose("down", False), vis, now=1.4)
    count, _, _, hits, _ = a.update(pose("down", False), vis, now=1.5)
    names = {h["name"] for h in hits}
    assert count == 1
    assert {"hand_not_up", "right_hand_not_up"}.issubset(names)
    print("  前一次单纯举手未替后一次幅度不足动作通过质量检查")


def test_live_quality_requires_consecutive_bad_frames():
    print("=== 测试 19：实时姿态错误需连续出现，单帧抖动不提醒 ===")
    a = load_action("configs/pushup.json")
    p = [(0, 0)] * 33
    # 左侧明显塌腰；右侧保持直线。肘部保持伸直，避免计数状态变化。
    p[11], p[13], p[15] = (100, 100), (150, 100), (200, 100)
    p[23], p[27] = (150, 190), (200, 200)
    p[12], p[14], p[16] = (100, 300), (150, 300), (200, 300)
    p[24], p[28] = (150, 300), (200, 300)
    vis = [1.0] * 33
    assert not a.update(p, vis, now=0.0)[3]
    assert not a.update(p, vis, now=0.04)[3]
    hits = a.update(p, vis, now=0.08)[3]
    assert any(h["name"] == "low_back" for h in hits)
    print("  前两帧不误报，第 3 个连续错误帧快速确认")


def test_quality_priority_and_degenerate_geometry():
    print("=== 测试 20：严重问题优先提示，重合关键点不误判 ===")
    q = QualityChecker([
        {"name": "minor", "check": "angle_min", "points": [0, 1, 2],
         "min": 170, "priority": 10},
        {"name": "major", "check": "angle_min", "points": [0, 1, 2],
         "min": 170, "priority": 100},
    ])
    pts = [(0, 0)] * 33
    pts[0], pts[1], pts[2] = (0, 0), (1, 0), (1, 1)  # 90°，两条都失败
    hits = q.hits(q.check(pts, [1.0] * 33))
    assert [h["name"] for h in hits] == ["major", "minor"]
    pts[0] = pts[1]  # 线段长度为 0，不应伪造一个 90°错误
    checks = q.check(pts, [1.0] * 33)
    assert not q.hits(checks) and all(not c["visible"] for c in checks)
    print("  高优先级先播报；无效角度被标为不可判定")


def test_bilateral_asymmetry_signals():
    print("=== 测试 21：左右动作明显不同步可被检测 ===")
    a = load_action("configs/pushup.json")
    p = [(0, 0)] * 33
    # 左肘 180°，右肘 90°。
    p[11], p[13], p[15] = (0, 0), (1, 0), (2, 0)
    p[12], p[14], p[16] = (0, 2), (1, 2), (1, 3)
    diff = a._calc_signal("angle_pair_diff", p, [11, 13, 15, 12, 14, 16])
    assert abs(diff - 90.0) < 0.1
    p[16] = (2, 2)
    diff_ok = a._calc_signal("angle_pair_diff", p, [11, 13, 15, 12, 14, 16])
    assert diff_ok < 0.1
    print("  90°左右差异被识别，同步动作差异接近 0°")


def test_squat_quality_extra_signals():
    print("=== 测试 22：深蹲明显膝前移与躯干-小腿失配信号 ===")
    a = load_action("configs/squat.json")
    p = [(0, 0)] * 33
    p[11], p[12] = (100, 40), (300, 40)       # 肩宽 200
    p[23], p[25], p[27] = (100, 100), (160, 160), (100, 220)
    p[31] = (-20, 220)                         # 膝-脚尖水平差 180 = 0.9肩宽
    travel = a._calc_signal("dx", p, [25, 31], [11, 12])
    assert travel > 0.75
    # 水平躯干配竖直小腿，是明显不协调的极端姿态。
    p[11], p[23], p[25], p[27] = (0, 100), (100, 100), (100, 160), (100, 220)
    mismatch = a._calc_signal("segment_angle_diff", p, [11, 23, 25, 27])
    assert mismatch > 80
    print(f"  膝前移比 {travel:.2f}、线段夹角差 {mismatch:.0f}° 均越过宽松阈值")



if __name__ == "__main__":
    test_rep_counter()
    test_hysteresis()
    test_quality()
    test_invisible_points()
    test_stage_filter()
    test_load_and_update()
    test_no_count_without_person()
    test_peak_judgment()
    test_depth_judgment()
    test_jumping_jack()
    test_abnormal_frame_dropped()
    test_reset_clears_cycle_state()
    test_low_confidence_does_not_pollute_counter_extrema()
    test_hidden_quality_points_do_not_pollute_rule_extrema()
    test_camera_thread_stops_cleanly()
    test_transition_hold_rejects_single_frame_glitch()
    test_jumping_jack_rejects_walking_and_partial_moves()
    test_partial_motion_does_not_contaminate_next_rep_quality()
    test_live_quality_requires_consecutive_bad_frames()
    test_quality_priority_and_degenerate_geometry()
    test_bilateral_asymmetry_signals()
    test_squat_quality_extra_signals()
    print("全部通过 ✅")
