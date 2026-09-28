#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pose_logic.py —— 动作配置的解释器（纯逻辑，不依赖摄像头 / MediaPipe）

这是本题的核心自研模块。读一份 JSON 动作配置，就能：
  1. 从 33 个关键点算出「判定信号」（关节角度 或 两点距离）
  2. 用带迟滞的状态机数动作次数（防边缘抖动、防重复计数）
  3. 按姿态约束判断动作标不标准，给出提示

新增一个动作 = 写一份 JSON 放进 configs/，这里的代码一行都不用改。
（这正是答辩要演示的「配置 → 状态机 → 计数」链路）
"""

import json
import math
import time

import numpy as np


# --------------------------------------------------------------------------
# 几何计算（输入都是 (x, y) 像素坐标）
# --------------------------------------------------------------------------
def angle_between(a, b, c):
    """以 b 为顶点，返回 a-b-c 的夹角（0~180 度）。180 度 = 三点成直线。"""
    ba = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    bc = np.asarray(c, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9
    cos = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return math.degrees(math.acos(cos))


def distance_between(a, b):
    """两点欧氏距离（像素）。开合跳用它判断两脚并拢 / 张开。"""
    return float(np.linalg.norm(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)))


# 归一化基准（肩宽）的最小像素值：比这个还小就说明关键点异常，该帧丢弃
MIN_UNIT_LEN = 40.0


# --------------------------------------------------------------------------
# 计数状态机（带迟滞）
# --------------------------------------------------------------------------
class RepCounter:
    """
    两态状态机。配置给 lo / hi 两个阈值 + first 方向：
      - first="lo"：信号先 < lo（进入动作阶段），再 > hi（还原）→ 计 1 次
        适用于俯卧撑 / 深蹲 / 二头弯举（角度先变小再变大）
      - first="hi"：信号先 > hi（进入动作阶段），再 < lo（还原）→ 计 1 次
        适用于开合跳（两脚距离先变大再变小）
    lo 和 hi 之间是「迟滞区」，信号在阈值边缘抖动时不会反复翻转。
    """

    def __init__(self, counter_cfg):
        # 两种模式：
        #  · 单条件（默认）：给 lo / hi 两个阈值，看一个信号
        #  · 多条件 AND    ：给 conditions 列表，**所有条件同时满足**才算进入动作
        #    （开合跳必须这样 —— 只拿「手举起」当条件的话，抬手就会误计数）
        self.conditions = counter_cfg.get("conditions")
        if self.conditions:
            self.first = counter_cfg.get("first", "on")
        else:
            self.lo = float(counter_cfg["lo"])
            self.hi = float(counter_cfg["hi"])
            self.first = counter_cfg.get("first", "lo")
        self.min_interval = float(counter_cfg.get("min_interval", 0.35))
        # 阈值必须连续满足一小段时间才允许换阶段。迟滞解决「阈值附近抖动」，
        # hold 解决「单帧关键点跳变」；两者作用不同，缺一项仍可能误计数。
        self.enter_hold = float(counter_cfg.get("enter_hold", 0.0))
        self.exit_hold = float(counter_cfg.get("exit_hold", 0.0))
        self.min_active_duration = float(counter_cfg.get("min_active_duration", 0.0))
        self.stage = "ready"        # ready=等待开始；active=已进入动作阶段
        self.count = 0
        self._last_t = -1e9
        self._act_since = None
        self._rest_since = None
        self._active_since = None

    def _act_and_rest(self, values):
        """返回 (是否满足「进入动作」, 是否满足「回到还原」)。"""
        if self.conditions:
            def act_ok(v, c):
                return v <= c["on"] if c.get("direction", "hi") == "lo" else v >= c["on"]

            def rest_ok(v, c):
                return v >= c["off"] if c.get("direction", "hi") == "lo" else v <= c["off"]

            act = all(act_ok(v, c) for v, c in zip(values, self.conditions))
            rest = all(rest_ok(v, c) for v, c in zip(values, self.conditions))
            return act, rest
        v = values[0]
        if self.first == "lo":
            return (v <= self.lo), (v >= self.hi)
        return (v >= self.hi), (v <= self.lo)

    def update(self, values, now=None):
        """values 可以是单个数，也可以是各条件的信号值列表（多条件模式）。"""
        if not isinstance(values, (list, tuple)):
            values = [values]
        now = time.time() if now is None else now
        act, rest = self._act_and_rest(values)
        if self.stage == "ready":
            self._rest_since = None
            if act:
                if self._act_since is None:
                    self._act_since = now
                if now - self._act_since >= self.enter_hold:
                    self.stage = "active"
                    self._active_since = now
                    self._act_since = None
            else:
                self._act_since = None
        else:  # active：等待还原
            self._act_since = None
            if rest:
                if self._rest_since is None:
                    self._rest_since = now
                active_long_enough = (
                    self._active_since is None
                    or self._rest_since - self._active_since >= self.min_active_duration
                )
                if now - self._rest_since >= self.exit_hold:
                    # active 持续太短说明只是一次快速关键点跳变：结束本轮但不计数。
                    # 不能用当前 now 计算持续时间，否则人在还原位多站一会儿也会被补记一次。
                    if active_long_enough and now - self._last_t >= self.min_interval:
                        self.count += 1
                        self._last_t = now
                    self.stage = "ready"
                    self._rest_since = None
                    self._active_since = None
            else:
                self._rest_since = None
        return self.count, self.stage

    def reset(self):
        self.count = 0
        self.stage = "ready"
        self._last_t = -1e9
        self._act_since = None
        self._rest_since = None
        self._active_since = None


# --------------------------------------------------------------------------
# 质量判定（姿态约束）
# --------------------------------------------------------------------------
class QualityChecker:
    """
    按配置里的 quality 规则逐条检查。

    关键点：如果某条规则用到的关键点「不可见」（visibility 太低，例如脚出画了），
    就**不判定**该规则 —— 因为 MediaPipe 对拍不到的点会猜一个位置，拿它算角度
    得到的是乱值，只会误报。这种情况标 visible=False，让上层提示用户调整机位。
    """

    def __init__(self, quality_cfgs, min_visibility=0.5):
        self.rules = quality_cfgs or []
        self.min_visibility = min_visibility

    def check(self, points, visibilities=None, stage="any", just_counted=False,
              peak=None, valley=None, rule_ext=None):
        """
        逐条检查，返回明细列表，每项含：
          name / tip / value(实测值) / limit(阈值) / ok(是否达标)
          visible  关键点是否拍全（拍不到 → 不判定，避免误报）
          checked  本次是否参与判定（"when" 可选 any / ready / active / on_rep）

        peak / valley : 「计数信号」本轮的峰值 / 谷值
        rule_ext      : {规则名: {"peak":…, "valley":…}} —— 给「自带 signal」的规则用。
                        一条约束可以看自己的信号，不必和计数信号相同。
                        例：开合跳计数看手腕高度，而「腿没张开」看脚距/肩宽。
        """
        checks = []
        for rule in self.rules:
            # ---- 判定时机 ----
            when = rule.get("when", "any")
            if when == "any":
                checked = True
            elif when == "on_rep":
                checked = just_counted
            else:
                checked = (when == stage)

            kind = rule.get("check")
            has_own_signal = "signal" in rule

            # ---- 本规则要用的极值：自带信号用自己的，否则用计数信号的 ----
            if has_own_signal:
                ext = (rule_ext or {}).get(rule.get("name"), {})
                r_peak, r_valley = ext.get("peak"), ext.get("valley")
            else:
                r_peak, r_valley = peak, valley

            # ---- 关键点可见性（纯 peak_* 且不带信号的规则不依赖关键点）----
            idx = rule.get("points")
            need_points = kind in ("collinear", "angle_min", "angle_max")
            pts = [points[i] for i in idx] if idx else None
            visible = True
            if (need_points or has_own_signal) and idx and visibilities is not None:
                visible = min(visibilities[i] for i in idx) >= self.min_visibility

            # ---- 算实测值与是否达标 ----
            value, limit, ok = None, None, True
            if kind == "collinear":
                # 三点共线度：算中间点的夹角，180 度为完全直线（塌腰/撅臀时变小）
                value = angle_between(pts[0], pts[1], pts[2])
                limit = rule.get("min_angle", 160)
                ok = value >= limit
            elif kind == "angle_min":
                # 某个角要 >= min（例如还原时肘角 >= 150 才叫伸直）
                value = angle_between(pts[0], pts[1], pts[2])
                limit = rule.get("min", 0)
                ok = value >= limit
            elif kind == "angle_max":
                # 某个角要 <= max（例如弯起时肘角 <= 70 才算弯到位）
                value = angle_between(pts[0], pts[1], pts[2])
                limit = rule.get("max", 180)
                ok = value <= limit
            elif kind == "peak_min":
                # 用「本轮动作里信号达到过的最大值」判定。
                # 例：「站起时腿没伸直」不能用计数瞬间的角度（那时刚好刚过计数线），
                # 要看这一轮最高站到多少度。
                value = r_peak if r_peak is not None else 0.0
                limit = rule.get("min", 0)
                ok = value >= limit
            elif kind == "peak_max":
                # 同理，用峰值判「有没有到位（角度够小）」
                value = r_peak if r_peak is not None else 0.0
                limit = rule.get("max", 180)
                ok = value <= limit
            elif kind == "valley_max":
                # 用「动作阶段里信号达到过的最小值」判定。
                # 例：「有没有蹲下去」—— 看这一轮蹲到最低时是多少度。
                # 谷值只在下蹲阶段采集，所以计数那一刻就已经完整了，判定准确、不滞后。
                value = r_valley if r_valley is not None else 999.0
                limit = rule.get("max", 180)
                ok = value <= limit
            elif kind == "valley_min":
                value = r_valley if r_valley is not None else 999.0
                limit = rule.get("min", 0)
                ok = value >= limit
            checks.append({
                "name": rule.get("name", "动作不标准"),
                "tip": rule.get("tip", rule.get("name", "动作不标准")),
                "value": value,
                "limit": limit,
                "ok": ok,
                "visible": visible,
                "checked": checked,
            })
        return checks

    @staticmethod
    def hits(checks):
        """挑出「关键点可见 + 本阶段该判 + 不达标」的，作为要报的错误。"""
        return [c for c in checks if c["visible"] and c["checked"] and not c["ok"]]


# --------------------------------------------------------------------------
# 动作对象：把计数 + 质量 + 信号计算组合起来
# --------------------------------------------------------------------------
class Action:
    """一个动作：从配置加载，持有计数状态机和质量检查器。"""

    def __init__(self, cfg):
        self.id = cfg["id"]
        self.name = cfg.get("name", cfg["id"])
        counter_cfg = cfg["counter"]
        # 多条件 AND 模式：conditions 里每个条件自带 signal / points / unit_points
        self.conditions = counter_cfg.get("conditions")
        if self.conditions:
            first = self.conditions[0]
            self.signal_type = first["signal"]
            self.signal_points = first["points"]
            self.unit_points = first.get("unit_points")
        else:
            self.signal_type = counter_cfg["signal"]   # "angle" | "distance" | "dy"
            self.signal_points = counter_cfg["points"]
            # 可选：归一化参考点对（一般传「两肩」= 用肩宽当尺子，站远站近数值都稳定）
            self.unit_points = counter_cfg.get("unit_points")
        self.counter = RepCounter(counter_cfg)
        # 是否允许「站立基线自动校准」。校准用「基线 − 偏移」的公式，只适合
        # 「角度变小」的动作（深蹲），对「角度变大」的动作（开合跳举手）必须关掉。
        self.calibrate = cfg.get("calibrate", True)
        self.min_visibility = cfg.get("min_visibility", 0.5)
        self.quality = QualityChecker(cfg.get("quality", []),
                                      min_visibility=self.min_visibility)
        self.sig_peak = None            # 本轮动作里信号达到过的最大值（供 peak_* 判定）
        self.depth_valley = None        # 动作阶段里信号的最小值（供 valley_* 判定）
        self.rule_ext = {}              # {规则名: {peak, valley}} 自带 signal 的规则各自记极值
        self.last_values = []           # 最近一帧各条件的信号值（供 HUD 显示）
        self.unit_smooth = None         # 归一化基准（肩宽）的平滑值，避免抖动被放大

    def signals(self, points):
        """算所有判定条件的信号值（单条件模式就一个）。"""
        conds = self.conditions or [{"signal": self.signal_type,
                                     "points": self.signal_points,
                                     "unit_points": self.unit_points}]
        return [self._calc_signal(c["signal"], points, c["points"], c.get("unit_points"))
                for c in conds]

    def signal(self, points):
        """显示用的主信号（多条件时取第一个）。"""
        return self.signals(points)[0]

    def _calc_signal(self, sig_type, points, idx, unit_points=None):
        """
        算一个信号值。计数信号和「规则自带信号」共用这套算法：
          angle    三点夹角（度）
          distance 两点欧氏距离
          dx       两点的水平差（开合跳判「脚左右张开」，能区分走路的前后迈步）
          dy       两点的竖直差（图像 y 向下，所以「上面的点 − 下面的点」为正）
        给了 unit_points 就再除以这对点的距离做归一化（一般传两肩 —— 用肩宽当尺子，
        这样站远站近数值都稳定）。

        注意：归一化基准用**指数平滑值**，不是当帧值 —— 肩宽本身会抖（跳动、抬手
        都会影响肩点），拿当帧值当除数等于把这抖动放大成比值乱跳（实测出现过
        「手高度 = 3.36 倍肩宽」这种不可能的数）。
        """
        pts = [points[i] for i in idx]
        if sig_type == "angle":
            return angle_between(pts[0], pts[1], pts[2])
        if sig_type == "distance":
            v = distance_between(pts[0], pts[1])
        elif sig_type == "dx":
            # 两点的「水平」差 —— 开合跳要用它：走路是前后迈步（图像里 y 差大、x 差小），
            # 开合跳是左右张开（x 差大）。用直线距离区分不开这两件事。
            v = abs(pts[0][0] - pts[1][0])
        elif sig_type == "dy":
            v = pts[0][1] - pts[1][1]
        else:
            return None
        if unit_points:
            u = [points[i] for i in unit_points]
            unit_len = distance_between(u[0], u[1])
            # 归一化基准（一般 = 肩宽）太小，说明这一帧关键点异常（两点几乎重合）。
            # 直接除会算出离谱的比值（实测见过 28），把「峰值判定」彻底污染掉
            # —— 结果就是「永远判定通过、永远不报错」。所以这种帧直接丢弃。
            if unit_len < MIN_UNIT_LEN:
                return None
            # 基准用指数平滑值，避免逐帧抖动被放大成比值乱跳
            if self.unit_smooth is None:
                self.unit_smooth = unit_len
            else:
                self.unit_smooth = 0.9 * self.unit_smooth + 0.1 * unit_len
            v = v / self.unit_smooth
        return v

    def update(self, points, visibilities=None, now=None):
        """喂一帧关键点，返回 (count, stage, signal, hits, checks)。"""
        # 先检查计数关键点可信度，再计算信号。距离类信号在计算时会更新归一化
        # 平滑基准；如果先算后过滤，低可信度帧仍可能污染 unit_smooth。
        conf = 1.0
        if visibilities is not None:
            idxs = set()
            for c in (self.conditions or [{"points": self.signal_points}]):
                idxs.update(c["points"])
            conf = min(visibilities[i] for i in idxs)
        if conf < self.min_visibility:
            cond_count = len(self.conditions) if self.conditions else 1
            self.last_values = [None] * cond_count
            checks = self.quality.check(
                points, visibilities, self.counter.stage, False,
                self.sig_peak, self.depth_valley, self.rule_ext,
            )
            return self.counter.count, self.counter.stage, None, [], checks

        values = self.signals(points)
        self.last_values = values                # 供 HUD 显示每个条件的当前值
        sig = values[0] if values else None      # 显示用（多条件时是第一个）
        # 任一条件的信号算不出来（关键点异常，如「肩宽」趋近 0）→ 整帧跳过，
        # 否则一个离谱值就会污染峰值，导致「永远判定通过、永远不报错」。
        if any(v is None for v in values):
            return self.counter.count, self.counter.stage, None, [], []
        just_counted = False
        self.sig_peak = sig if self.sig_peak is None else max(self.sig_peak, sig)
        previous_stage = self.counter.stage
        before = self.counter.count
        count, stage = self.counter.update(values, now)
        just_counted = count > before           # 这一帧刚数上一个

        # 真正进入 active 才算一轮动作开始。此前可能有挥手、走路等不满足全部
        # 门控条件的零散运动，不能让这些旧峰值替下一次动作“作弊”。
        if previous_stage == "ready" and stage == "active":
            self.sig_peak = sig
            self.depth_valley = None
            self.rule_ext = {}

        # 下蹲阶段的谷值（这一轮蹲到最低多少度）—— 只在 active 阶段采集，
        # 所以等计数那一刻（离开 active）它已经完整了，判定准确、不滞后。
        if stage == "active":
            self.depth_valley = sig if self.depth_valley is None else min(self.depth_valley, sig)

        # 自带 signal 的规则：为每条规则维护「它自己信号」的峰值 / 谷值
        # （例：开合跳的「腿没张开」看脚距/肩宽，和计数用的手腕高度不是同一个信号）
        for rule in self.quality.rules:
            st = rule.get("signal")
            r_idx = rule.get("points")
            if not st or not r_idx:
                continue
            # 自带信号的规则还要检查它自己的关键点是否可信；计数关键点可见，
            # 不代表脚踝等质量判定点也一定可见。
            if visibilities is not None:
                rule_conf = min(visibilities[i] for i in r_idx)
                if rule_conf < self.min_visibility:
                    continue
            v = self._calc_signal(st, points, r_idx, rule.get("unit_points"))
            if v is None:
                continue
            name = rule.get("name")
            ext = self.rule_ext.get(name)
            if ext is None:
                self.rule_ext[name] = {"peak": v, "valley": v}
            else:
                ext["peak"] = max(ext["peak"], v)
                ext["valley"] = min(ext["valley"], v)

        # peak / valley / rule_ext 传进去，让各类约束用「本轮极值」判定
        checks = self.quality.check(points, visibilities, stage, just_counted,
                                    self.sig_peak, self.depth_valley, self.rule_ext)
        hits = self.quality.hits(checks)

        if just_counted:
            self.sig_peak = None                # 结算完，开新的一轮
            self.depth_valley = None
            self.rule_ext = {}

        return count, stage, sig, hits, checks

    def reset(self):
        self.counter.reset()
        # 清零必须同时结束当前动作周期；否则按 r 后，清零前留下的峰值/谷值
        # 会参与下一次动作的质量判定，出现「计数清了但判定没清」的串轮问题。
        self.sig_peak = None
        self.depth_valley = None
        self.rule_ext = {}
        self.last_values = []
        self.unit_smooth = None


def load_action(path):
    """从 JSON 文件加载一个动作。"""
    with open(path, encoding="utf-8") as f:
        return Action(json.load(f))
