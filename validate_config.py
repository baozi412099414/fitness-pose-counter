#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动作配置校验器 —— 选题 11：健身动作计数与姿态纠正

配合「自定义健身姿势」模块使用。用户写新动作配置时最容易犯这些错：
关键点编号写错、signal 类型与 points 数量不匹配、阈值方向写反、
约束的 check 名字拼错、到位类约束忘了写 when="on_rep"……
这些错误**在摄像头前才发现代价很高**（要重新架机位、重做动作），
所以这个工具把它们在**运行之前**就全部指出来。

用法：
    .venv/bin/python validate_config.py                  # 校验 configs/ 下全部配置
    .venv/bin/python validate_config.py configs/my.json  # 校验单个文件

返回码：0 = 没有错误；1 = 存在「错误」级问题（警告不影响返回码）。
"""

import json
import os
import sys

# ── MediaPipe Pose 的 33 个关键点里常用的那些（报错时显示名字，比编号直观）
LANDMARK_NAMES = {
    0: "鼻子", 2: "左眼", 5: "右眼", 7: "左耳", 8: "右耳",
    9: "嘴左", 10: "嘴右",
    11: "左肩", 12: "右肩", 13: "左肘", 14: "右肘", 15: "左腕", 16: "右腕",
    17: "左手小指", 18: "右手小指", 19: "左手食指", 20: "右手食指",
    21: "左手拇指", 22: "右手拇指",
    23: "左髋", 24: "右髋", 25: "左膝", 26: "右膝",
    27: "左踝", 28: "右踝", 29: "左脚跟", 30: "右脚跟",
    31: "左脚尖", 32: "右脚尖",
}

# 信号类型 -> 需要几个关键点
SIGNAL_ARITY = {
    "angle": 3,            # 三点夹角，中间那个是顶点
    "distance": 2,
    "dx": 2,
    "dxs": 2,
    "dy": 2,
    "tilt": 2,
    "angle_pair_diff": 6,      # 两组三点，比较左右两侧夹角是否同步
    "segment_angle_diff": 4,   # 两条线段方向差
}

# 判定类型 -> (需要几个关键点, 是"周期极值"类吗)
CHECK_ARITY = {
    "collinear": 3,
    "angle_min": 3,
    "angle_max": 3,
    "peak_min": 0,
    "peak_max": 0,
    "valley_max": 0,
    "valley_min": 0,
    "min": 0,
    "max": 0,
}

VALID_WHEN = ("any", "ready", "active", "on_rep")


class Report:
    """收集问题；error 会让校验失败，warn 只提示。"""

    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warns = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    @property
    def ok(self):
        return not self.errors


def _landmark(idx):
    if not isinstance(idx, int):
        return f"非整数({idx!r})"
    if not 0 <= idx <= 32:
        return f"{idx} ⚠超出 0~32"
    return f"{idx}({LANDMARK_NAMES.get(idx, '?')})"


def _points_str(points):
    return "[" + ", ".join(_landmark(i) for i in points) + "]"


def _check_points(rep, points, arity, where):
    """检查关键点数组：是列表、长度对、编号合法。"""
    if not isinstance(points, list):
        rep.error(f"{where}：points 必须是数组，现在是 {type(points).__name__}")
        return False
    if arity and len(points) != arity:
        rep.error(f"{where}：points 需要 {arity} 个关键点，现在给了 {len(points)} 个 {points}")
    if len(points) != len(set(points)) and arity != 6:
        rep.warn(f"{where}：points 里有重复关键点 {points}，算出来的角度/距离可能没有意义")
    bad = [i for i in points if not isinstance(i, int) or not 0 <= i <= 32]
    if bad:
        rep.error(f"{where}：关键点编号越界 {bad}（合法范围 0~32）"
                  f"，正确写法参考 {_points_str([p for p in points if isinstance(p, int) and 0 <= p <= 32])}")
    return True


def validate_file(path):
    """校验一个配置，返回 Report。"""
    rep = Report(path)

    # ---- 0. 能不能解析 ----
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        rep.error(f"文件不存在：{path}")
        return rep
    except json.JSONDecodeError as e:
        rep.error(f"JSON 语法错误：第 {e.lineno} 行第 {e.colno} 列 → {e.msg}")
        return rep

    if not isinstance(cfg, dict):
        rep.error("配置根节点必须是一个 JSON 对象 {}")
        return rep

    # ---- 1. 基本信息 ----
    if not cfg.get("id"):
        rep.error("缺少 id（动作英文标识，也用于 --action 参数和文件名）")
    elif os.path.basename(path) not in (f"{cfg['id']}.json", "configs.json"):
        rep.warn(f"文件名 {os.path.basename(path)} 与 id「{cfg['id']}」不一致，"
                 f"命令行要写 --action {os.path.splitext(os.path.basename(path))[0]}")
    if not cfg.get("name"):
        rep.warn("缺少 name（界面按钮和 HUD 上显示的中文名），会退回用 id 显示")

    # ---- 2. 计数部分 ----
    counter = cfg.get("counter")
    if not isinstance(counter, dict):
        rep.error("缺少 counter 段（计数配置）")
        return rep

    conditions = counter.get("conditions")
    if conditions is not None:
        # 多条件 AND 模式
        if not isinstance(conditions, list) or not conditions:
            rep.error("conditions 必须是非空数组（所有条件同时满足才算一次动作）")
        else:
            for i, cond in enumerate(conditions, 1):
                where = f"counter.conditions[{i}]"
                sig = cond.get("signal")
                if sig not in SIGNAL_ARITY:
                    rep.error(f"{where}：signal「{sig}」不支持，可选 {list(SIGNAL_ARITY)}")
                    continue
                _check_points(rep, cond.get("points", []), SIGNAL_ARITY[sig], where)
                on, off = cond.get("on"), cond.get("off")
                if on is None or off is None:
                    rep.error(f"{where}：缺少 on / off（进入动作阈值 / 回到还原阈值）")
                elif on == off:
                    rep.error(f"{where}：on 与 off 相等，没有迟滞区，阈值附近会反复翻转")
                direction = cond.get("direction", "hi")
                if direction not in ("hi", "lo"):
                    rep.error(f"{where}：direction 只能是 hi 或 lo，现在是「{direction}」")
                elif direction == "hi" and on <= off:
                    rep.warn(f"{where}：direction=hi 时通常应 on > off（进入值高于还原值），"
                             f"现在是 on={on} ≤ off={off}，确认没写反")
                elif direction == "lo" and on >= off:
                    rep.warn(f"{where}：direction=lo 时通常应 on < off，现在是 on={on} ≥ off={off}")
    else:
        # 单信号模式
        sig = counter.get("signal")
        if sig not in SIGNAL_ARITY:
            rep.error(f"counter.signal「{sig}」不支持，可选 {list(SIGNAL_ARITY)}")
        else:
            _check_points(rep, counter.get("points", []), SIGNAL_ARITY[sig], "counter")
        lo, hi = counter.get("lo"), counter.get("hi")
        if lo is None or hi is None:
            rep.error("counter 缺少 lo / hi 阈值")
        elif lo >= hi:
            rep.error(f"counter：lo({lo}) 必须小于 hi({hi})，否则迟滞区不成立")
        first = counter.get("first", "lo")
        if first not in ("lo", "hi"):
            rep.error(f"counter.first 只能是 lo 或 hi，现在是「{first}」")

    mi = counter.get("min_interval", 0.35)
    if not isinstance(mi, (int, float)) or mi < 0:
        rep.error(f"min_interval 要是非负数，现在是 {mi!r}")
    elif mi > 3:
        rep.warn(f"min_interval={mi}s 偏大，动作做得快时可能漏计")

    # ---- 3. 质量约束 ----
    rules = cfg.get("quality", [])
    if not isinstance(rules, list):
        rep.error("quality 必须是数组")
        rules = []
    seen_names = set()
    for i, rule in enumerate(rules, 1):
        where = f"quality[{i}]"
        if not isinstance(rule, dict):
            rep.error(f"{where}：必须是对象")
            continue
        name = rule.get("name")
        if not name:
            rep.error(f"{where}：缺少 name（错误事件的标识，会写进报告和统计）")
        elif name in seen_names:
            rep.warn(f"{where}：name「{name}」重复，报告里会把两条合并统计")
        else:
            seen_names.add(name)

        kind = rule.get("check")
        if kind not in CHECK_ARITY:
            rep.error(f"{where}：check「{kind}」不支持，可选 {list(CHECK_ARITY)}")
            continue

        # 自带 signal 时用它的 arity；否则用约束自己的 points
        own_sig = rule.get("signal")
        if own_sig is not None:
            if own_sig not in SIGNAL_ARITY:
                rep.error(f"{where}：signal「{own_sig}」不支持")
            else:
                _check_points(rep, rule.get("points", []), SIGNAL_ARITY[own_sig], where)
        elif CHECK_ARITY[kind]:
            _check_points(rep, rule.get("points", []), CHECK_ARITY[kind], where)

        when = rule.get("when", "any")
        if when not in VALID_WHEN:
            rep.error(f"{where}：when「{when}」不支持，可选 {list(VALID_WHEN)}")

        # 阈值字段要和 check 对得上
        if kind.endswith("_min") and "min" not in rule:
            rep.error(f"{where}：check={kind} 需要 min 字段")
        if kind.endswith("_max") and "max" not in rule:
            rep.error(f"{where}：check={kind} 需要 max 字段")
        if kind == "collinear" and "min_angle" not in rule:
            rep.error(f"{where}：check=collinear 需要 min_angle 字段")

        if not rule.get("tip"):
            rep.warn(f"{where}：没有 tip，语音播报时只会念出英文 name")

        # 经验规则：到位类判定必须放到「计数那一刻」看整轮极值
        # 只在「没显式写 when」时提醒：显式写了 when 说明用户是有意选择判定时机
        # （例如「膝前移」就是要实时提示，而不是等整个动作做完）
        if (kind in ("peak_min", "peak_max", "valley_max", "valley_min")
                and when != "on_rep" and "when" not in rule):
            rep.warn(f"{where}：{kind} 是「整轮极值」判定，多数情况应配 when=\"on_rep\""
                     f"（动作做完再判）。若确实要实时提示，请显式写 \"when\": \"{when}\""
                     f" 表明这是有意选择")

        # ideal（满分线）必须比及格线「更好」，否则评分曲线是反的
        ideal = rule.get("ideal")
        if ideal is not None:
            if not isinstance(ideal, (int, float)):
                rep.error(f"{where}：ideal 要是数字（满分线）")
            elif kind.endswith("_max") or kind == "max":
                lim = rule.get("max")
                if lim is not None and ideal > lim:
                    rep.error(f"{where}：ideal={ideal} 应 ≤ max={lim}"
                              f"（这类约束「越小越好」，满分线要比及格线更小）")
            elif kind == "collinear":
                lim = rule.get("min_angle")
                if lim is not None and ideal < lim:
                    rep.error(f"{where}：ideal={ideal} 应 ≥ min_angle={lim}")
            elif kind.endswith("_min"):
                lim = rule.get("min")
                if lim is not None and ideal < lim:
                    rep.error(f"{where}：ideal={ideal} 应 ≥ min={lim}"
                              f"（这类约束「越大越好」，满分线要比及格线更大）")

        pr = rule.get("priority")
        if pr is not None and not isinstance(pr, (int, float)):
            rep.error(f"{where}：priority 要是数字（越大越优先播报）")

    # ---- 4. 机位提示（用脚尖判断的约束只在侧面机位可靠）----
    used = set()
    for cond in (conditions or [counter]):
        used.update(cond.get("points") or [])
    for rule in rules:
        used.update(rule.get("points") or [])
    if {31, 32} & used and cfg.get("camera_side") not in ("侧", "侧面"):
        rep.warn(f"用到了脚尖关键点（31/32），建议机位设为侧面（camera_side=\"侧\"）"
                 f"，现在写的是「{cfg.get('camera_side')}」")

    return rep


def main(argv):
    targets = argv[1:]
    if targets and targets[0] != "-h":
        files = targets
    else:
        cfg_dir = "configs"
        if not os.path.isdir(cfg_dir):
            print(f"找不到 {cfg_dir}/ 目录")
            return 1
        files = [os.path.join(cfg_dir, f) for f in sorted(os.listdir(cfg_dir))
                 if f.endswith(".json")]

    if not files:
        print("没有找到要校验的配置文件")
        return 1

    total_err = 0
    for path in files:
        rep = validate_file(path)
        tag = "✅ 通过" if rep.ok else "❌ 有问题"
        print(f"\n══════ {os.path.basename(path)}  {tag}")
        for w in rep.warns:
            print(f"  ⚠ 警告  {w}")
        for e in rep.errors:
            print(f"  ✖ 错误  {e}")
        if rep.ok and not rep.warns:
            print("  没有发现任何问题")
        total_err += len(rep.errors)

    print(f"\n{'─' * 60}")
    print(f"共校验 {len(files)} 个文件，错误 {total_err} 条")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
