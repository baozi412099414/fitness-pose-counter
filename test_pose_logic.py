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


if __name__ == "__main__":
    test_rep_counter()
    test_hysteresis()
    test_quality()
    test_invisible_points()
    test_stage_filter()
    test_load_and_update()
    print("全部通过 ✅")
