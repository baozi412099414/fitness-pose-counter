#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用合成数据验证动作配置解释器（不依赖摄像头 / MediaPipe）。

跑法：
    .venv/bin/python test_pose_logic.py
"""

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
    # 站起姿态：三点竖直共线 => 膝角 180°
    up = [(0, 0)] * 33
    up[23] = (100, 100)
    up[25] = (100, 160)
    up[27] = (100, 220)

    vis_bad = [0.1] * 33      # 人没拍到 / 目标跟丢
    vis_ok = [1.0] * 33       # 人在画面里

    c1, s1, sig1, _, _ = action.update(down, vis_bad, now=0.0)
    print(f"  可信度 0.1（没人）+ 蹲下姿态 -> REPS {c1}  阶段 {s1}（应保持 0 / ready）")
    assert c1 == 0 and s1 == "ready", "人没拍到时不该改变计数状态"

    action.update(down, vis_ok, now=1.0)                        # 有人：蹲下 -> active
    c2, s2, sig2, _, _ = action.update(up, vis_ok, now=2.0)     # 有人：站起 -> 计 1
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
        return p

    # 场景 1：先站到 174° 再蹲 -> 本轮峰值 174°，站起计数时不该报
    a = load_action("configs/squat.json")
    a.update(knee_pts(3), vis, now=0.0)                              # 站着 174°
    a.update(knee_pts(60), vis, now=1.0)                             # 蹲下
    c, s, sig, hits, _ = a.update(knee_pts(10), vis, now=2.0)        # 站起到刚过计数线
    print(f"  站在 174° 后深蹲：计数时 sig={sig:.1f}°  报错 {[h['name'] for h in hits]}")
    assert c == 1, "应计 1 次"
    assert not hits, "本轮峰值 174° >= 162°，不该报「没伸直」"

    # 场景 2：全程只站到 161° -> 峰值不够，应该报
    a2 = load_action("configs/squat.json")
    a2.update(knee_pts(10), vis, now=0.0)                            # 站着只有 161°
    a2.update(knee_pts(60), vis, now=1.0)                            # 蹲下
    c, s, sig, hits, _ = a2.update(knee_pts(10), vis, now=2.0)
    print(f"  只站到 161° 后深蹲：计数时 sig={sig:.1f}°  报错 {[h['name'] for h in hits]}")
    assert c == 1, "应计 1 次"
    assert hits, "本轮峰值只有 161° < 162°，应报「没伸直」"
    print("  ✅ 判定看本轮峰值，而不是「刚过计数线那一帧」的角度\n")


if __name__ == "__main__":
    test_rep_counter()
    test_hysteresis()
    test_quality()
    test_invisible_points()
    test_stage_filter()
    test_load_and_update()
    test_no_count_without_person()
    test_peak_judgment()
    print("全部通过 ✅")
