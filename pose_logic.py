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
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    # 关键点重合时不存在有意义的关节角。以前加一个极小数会得到 90°，
    # 反而把异常骨架当成真实错误；返回 None 让上层丢弃该帧。
    if denom < 1e-9:
        return None
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
                visible = visible and value is not None
                ok = True if value is None else value >= limit
            elif kind == "angle_min":
                # 某个角要 >= min（例如还原时肘角 >= 150 才叫伸直）
                value = angle_between(pts[0], pts[1], pts[2])
                limit = rule.get("min", 0)
                visible = visible and value is not None
                ok = True if value is None else value >= limit
            elif kind == "angle_max":
                # 某个角要 <= max（例如弯起时肘角 <= 70 才算弯到位）
                value = angle_between(pts[0], pts[1], pts[2])
                limit = rule.get("max", 180)
                visible = visible and value is not None
                ok = True if value is None else value <= limit
            elif kind == "peak_min":
                # 用「本轮动作里信号达到过的最大值」判定。
                # 例：「站起时腿没伸直」不能用计数瞬间的角度（那时刚好刚过计数线），
                # 要看这一轮最高站到多少度。
                #
                # ⚠ r_peak 为 None 表示**本轮根本没采到极值**（关键点一直不可信）。
                #   这时必须判成「无数据」（visible=False），绝不能拿 0 去比 ——
                #   否则「看不清」会被误报成「动作不到位」，而且每一轮都报。
                value = r_peak
                limit = rule.get("min", 0)
                if value is None:
                    visible, ok = False, True
                else:
                    ok = value >= limit
            elif kind == "peak_max":
                # 同理，用峰值判「有没有到位（角度够小）」；同样要区分「没数据」
                value = r_peak
                limit = rule.get("max", 180)
                if value is None:
                    visible, ok = False, True
                else:
                    ok = value <= limit
            elif kind == "valley_max":
                # 用「动作阶段里信号达到过的最小值」判定。
                # 例：「有没有蹲下去」—— 看这一轮蹲到最低时是多少度。
                # 谷值只在下蹲阶段采集，所以计数那一刻就已经完整了，判定准确、不滞后。
                value = r_valley
                limit = rule.get("max", 180)
                if value is None:
                    visible, ok = False, True
                else:
                    ok = value <= limit
            elif kind == "valley_min":
                value = r_valley
                limit = rule.get("min", 0)
                if value is None:
                    visible, ok = False, True
                else:
                    ok = value >= limit
            checks.append({
                "name": rule.get("name", "动作不标准"),
                "tip": rule.get("tip", rule.get("name", "动作不标准")),
                "value": value,
                "limit": limit,
                "ok": ok,
                "visible": visible,
                "checked": checked,
                "priority": int(rule.get("priority", 0)),
                # 0~100 分：及格线 60 分、满分线（ideal）100 分
                "score": self._score(value, limit, kind, rule.get("ideal")),
            })
        return checks

    # ------------------------------------------------------------------
    # 评分：把「合格 / 不合格」升级成 0~100 分
    # ------------------------------------------------------------------
    @staticmethod
    def _score(value, limit, kind, ideal=None):
        """
        把「实测值 vs 阈值」折算成 0~100 分。

        约定：**及格线（limit）= 60 分，满分线（ideal）= 100 分**，之间线性插值；
        不及格按偏离程度线性衰减到 0。

        为什么这样做：原来的判定只有合格/不合格两种结果，「刚好压线」和「做得很好」
        完全分不出来。有了分数就能看出趋势（今天平均 72 分，上周 85 分）——
        这也是训练历史里唯一能画成曲线的东西。

        kind 决定方向：
          · min / collinear / *_min 类 → 值**越大**越好
          · max / *_max 类           → 值**越小**越好
        ideal 没配时按阈值自动外推 15%（角度、比值都适用）。
        """
        if value is None or limit is None:
            return 100.0                      # 判不了就不扣分，避免误伤
        worse_when_larger = kind.endswith("_max") or kind == "max"

        if worse_when_larger:
            if ideal is None:
                ideal = limit * 0.85
            if value <= ideal:
                return 100.0
            if value <= limit:
                span = max(limit - ideal, 1e-6)
                return 60.0 + 40.0 * (limit - value) / span
            # 不及格：按超出阈值的比例衰减，**偏离 50% 即归零**。
            # 原来用 60*limit/value，衰减太慢 —— 蹲到 130° 还有 48 分，不合理。
            over = (value - limit) / max(abs(limit), 1e-6)
            return max(0.0, 60.0 * (1.0 - over / 0.5))
        else:
            if ideal is None:
                # 自动外推 15%；但角度不可能超过 180°，否则「站起伸直」这类约束
                # 会永远拿不到满分（160×1.15=184 就已经越界了）。
                ideal = min(limit * 1.15, 179.0) if limit > 20 else limit * 1.15
            if value >= ideal:
                return 100.0
            if value >= limit:
                span = max(ideal - limit, 1e-6)
                return 60.0 + 40.0 * (value - limit) / span
            # 不及格：低于阈值 50% 即归零（同理，衰减要够快）
            under = (limit - value) / max(abs(limit), 1e-6)
            return max(0.0, 60.0 * (1.0 - under / 0.5))

    @staticmethod
    def total_score(checks):
        """
        汇总总分（0~100）。

        **不单纯用加权平均** —— 那会把「一条严重不合格」稀释掉：
        例如浅蹲的人幅度分只有 30，但其他几条姿态都没毛病（满分），平均下来还有 80 分，
        完全体现不出「蹲不到位」这个核心问题。

        所以总分 = 0.5 × 加权平均 + 0.5 × 最低分（木桶效应）：
        任何一条明显不合格都会直接把总分拉下来，同时保留整体水平的区分度。

        没有任何可判定的约束时返回 None（这次算不出分数）。
        """
        pool = [c for c in checks if c.get("visible") and c.get("checked")]
        if not pool:
            return None
        num = sum(c["score"] * max(1, c.get("priority", 50)) for c in pool)
        den = sum(max(1, c.get("priority", 50)) for c in pool)
        avg = num / den
        worst = min(c["score"] for c in pool)
        return round(0.5 * avg + 0.5 * worst, 1)

    @staticmethod
    def grade(score):
        """把分数翻译成等级，方便直接显示。"""
        if score is None:
            return "—"
        if score >= 90:
            return "优秀"
        if score >= 75:
            return "良好"
        if score >= 60:
            return "及格"
        return "待改进"

    @staticmethod
    def hits(checks):
        """挑出有效错误，并让高优先级问题先提示。"""
        hits = [c for c in checks if c["visible"] and c["checked"] and not c["ok"]]
        return sorted(hits, key=lambda c: c.get("priority", 0), reverse=True)


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
        self.violation_streaks = {}      # 连续错误确认：过滤单帧关键点抖动造成的误提醒
        self.last_values = []           # 最近一帧各条件的信号值（供 HUD 显示）
        self.last_score = None          # 最近一次动作「完成那一刻」的得分（0~100）
        self.face_sign = 0              # 人面朝画面哪一侧：+1 朝右 / -1 朝左 / 0 未知
        self.unit_smooth = None         # 归一化基准（肩宽）的平滑值，避免抖动被放大

    @staticmethod
    def estimate_face_sign(pts, vis=None, min_vis=0.5):
        """
        估计人**面朝画面的哪一侧**：+1 = 面朝右，-1 = 面朝左，0 = 判不出来。

        依据很朴素：**脚尖总在脚踝的前方**。取左右两脚 (脚尖x − 脚踝x) 之和，
        符号就是朝向 —— 不需要额外机位信息，也不受人站在画面哪个位置影响。

        为什么需要它：`dxs`（带符号水平差）的物理含义依赖朝向。同一个「膝在脚尖后」
        的动作，面朝右算出来是正、面朝左是负。有了朝向就能把符号翻正，
        让**同一份配置对左右朝向都成立**。
        """
        vals = []
        for toe, ankle in ((31, 27), (32, 28)):
            if vis is not None and (vis[toe] < min_vis or vis[ankle] < min_vis):
                continue
            vals.append(pts[toe][0] - pts[ankle][0])
        if not vals:
            return 0
        total = sum(vals)
        # 脚尖和脚踝几乎重合时（脚被遮挡 / 侧对机位）判不出来，宁可返回 0 也不瞎猜
        if abs(total) < 3.0:
            return 0
        return 1 if total > 0 else -1

    def signals(self, points):
        """算所有判定条件的信号值（单条件模式就一个）。"""
        conds = self.conditions or [{"signal": self.signal_type,
                                     "points": self.signal_points,
                                     "unit_points": self.unit_points}]
        return [self._calc_signal(c["signal"], points, c["points"], c.get("unit_points"),
                                  c.get("face_relative", False))
                for c in conds]

    def signal(self, points):
        """显示用的主信号（多条件时取第一个）。"""
        return self.signals(points)[0]

    def _calc_signal(self, sig_type, points, idx, unit_points=None, face_relative=False):
        """
        算一个信号值。计数信号和「规则自带信号」共用这套算法：
          angle    三点夹角（度）
          distance 两点欧氏距离
          dx       两点的水平差（开合跳判「脚左右张开」，能区分走路的前后迈步）
          dxs      带符号的水平差（深蹲判「膝是否超过脚尖」，绝对值版分不清前后）
          tilt     两点连线相对竖直方向的夹角（判「上身前倾程度」）
          dy       两点的竖直差（图像 y 向下，所以「上面的点 − 下面的点」为正）
          angle_pair_diff  两个三点角的绝对差（检查左右肢体是否明显不同步）
          segment_angle_diff 两条线段方向的夹角差（检查躯干与小腿是否协调）
        给了 unit_points 就再除以这对点的距离做归一化（一般传两肩 —— 用肩宽当尺子，
        这样站远站近数值都稳定）。

        注意：归一化基准用**指数平滑值**，不是当帧值 —— 肩宽本身会抖（跳动、抬手
        都会影响肩点），拿当帧值当除数等于把这抖动放大成比值乱跳（实测出现过
        「手高度 = 3.36 倍肩宽」这种不可能的数）。
        """
        pts = [points[i] for i in idx]
        if sig_type == "angle":
            return angle_between(pts[0], pts[1], pts[2])
        if sig_type == "angle_pair_diff":
            if len(pts) != 6:
                return None
            left = angle_between(*pts[:3])
            right = angle_between(*pts[3:])
            if left is None or right is None:
                return None
            return abs(left - right)
        if sig_type == "segment_angle_diff":
            if len(pts) != 4:
                return None
            a = np.asarray(pts[1], dtype=np.float64) - np.asarray(pts[0], dtype=np.float64)
            b = np.asarray(pts[3], dtype=np.float64) - np.asarray(pts[2], dtype=np.float64)
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            if denom < 1e-9:
                return None
            # 线段没有正反方向，取 0~90° 的最小夹角。
            raw = math.degrees(math.acos(np.clip(np.dot(a, b) / denom, -1.0, 1.0)))
            return min(raw, 180.0 - raw)
        if sig_type == "distance":
            v = distance_between(pts[0], pts[1])
        elif sig_type == "dx":
            # 两点的「水平」差 —— 开合跳要用它：走路是前后迈步（图像里 y 差大、x 差小），
            # 开合跳是左右张开（x 差大）。用直线距离区分不开这两件事。
            v = abs(pts[0][0] - pts[1][0])
        elif sig_type == "dxs":
            # 带符号的水平差（pts[0].x − pts[1].x），**不取绝对值**。
            # 用途：判断「膝是否超过脚尖」—— 绝对值版本分不清「膝在前」还是「膝在后」，
            # 而这两者在深蹲里意义完全相反。配置里按人的朝向决定点的先后顺序：
            #   人面朝画面右侧时写 [脚尖, 膝]，正常深蹲结果为正；膝越过脚尖就变负。
            v = pts[0][0] - pts[1][0]
            # face_relative：先按人的朝向把符号翻正，再和阈值比。
            # 不加这个开关的话，用户面朝画面左侧时符号整个反过来，
            # 「膝超脚尖」会每一帧都误报 —— 而阈值本身其实是对的。
            if face_relative:
                if not self.face_sign:
                    # 朝向判不出来（脚被遮挡）时**不能退回用原始符号** ——
                    # 那等于赌用户恰好面朝右边。判不了就不判，让这一帧无效。
                    return None
                v *= self.face_sign
        elif sig_type == "dy":
            v = pts[0][1] - pts[1][1]
        elif sig_type == "tilt":
            # 两点连线相对「竖直方向」的夹角（0° = 竖直，90° = 水平，恒为非负）。
            # 用途：判断躯干前倾程度 —— 注意不能用「躯干与小腿的方向差」代替，
            # 因为深蹲时躯干和小腿会**同步前倾**，方向差很小，抓不到上身前倾。
            dx = pts[0][0] - pts[1][0]
            dy = abs(pts[0][1] - pts[1][1])
            if dx == 0 and dy == 0:
                return None
            v = abs(math.degrees(math.atan2(dx, dy)))
            return v
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
        # 关键点数量不足直接跳过。正常情况 MediaPipe 总给 33 个点，但异常时可能给不全
        # （模型内部出错、图像格式异常），后面按索引取点会 IndexError ——
        # 那会把整个识别主循环搞崩，表现为「画面卡住」。宁可丢这一帧。
        if points is None or len(points) < 33:
            return self.counter.count, self.counter.stage, None, [], []

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

        # 每帧更新朝向（脚看不清时保持上一次的判断，避免左右来回翻）
        face = self.estimate_face_sign(points, visibilities)
        if face:
            self.face_sign = face

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
            v = self._calc_signal(st, points, r_idx, rule.get("unit_points"),
                                  rule.get("face_relative", False))
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
        raw_hits = self.quality.hits(checks)
        hits = []
        by_name = {r.get("name"): r for r in self.quality.rules}
        failed_names = {c["name"] for c in raw_hits}
        # 连续若干帧都不合格才实时提醒，标准动作偶发一帧越界不会被打扰；on_rep
        # 是整个周期极值结算，已经天然防抖，因此立即给结果。
        for c in checks:
            name = c["name"]
            rule = by_name.get(name, {})
            if name not in failed_names:
                self.violation_streaks[name] = 0
                continue
            if rule.get("when") == "on_rep":
                hits.append(c)
                continue
            streak = self.violation_streaks.get(name, 0) + 1
            self.violation_streaks[name] = streak
            if streak >= int(rule.get("confirm_frames", 3)):
                hits.append(c)
        hits.sort(key=lambda c: c.get("priority", 0), reverse=True)

        if just_counted:
            # 评分必须在「动作完成那一刻」结算：on_rep 类约束只在计数那一帧才 checked，
            # 拿别的帧去算会把它们漏掉（浅蹲也曾因此拿到满分）。
            self.last_score = self.quality.total_score(checks)
            self.sig_peak = None                # 结算完，开新的一轮
            self.depth_valley = None
            self.rule_ext = {}

        return count, stage, sig, hits, checks

    def reset(self):
        """
        清零：计数 + 本轮动作周期的全部状态。

        必须把峰值/谷值/规则极值一起清掉 —— 否则按 r 清零后，清零前留下的极值
        会参与下一次动作的质量判定，出现「计数清了但判定没清」的串轮问题。
        """
        self.counter.reset()
        self.sig_peak = None
        self.depth_valley = None
        self.rule_ext = {}
        self.violation_streaks = {}
        self.last_values = []
        self.last_score = None
        self.unit_smooth = None
        # face_sign 故意不清：朝向是人的属性，清零计数不该把它忘掉


def load_action(path):
    """
    从 JSON 文件加载一个动作。

    配置写错时给**看得懂的错误**（说明是哪个文件、缺什么），而不是直接抛 KeyError ——
    自定义动作的用户多半不是程序员，一句 "KeyError: 'counter'" 帮不上任何忙。

    ⚠ 静态检查请优先用 `validate_config.py`（它能一次列出所有问题）；
    这里的容错只是运行期的兜底。
    """
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到动作配置文件：{path}") from None
    except json.JSONDecodeError as e:
        raise ValueError(
            f"动作配置 {path} 不是合法 JSON：第 {e.lineno} 行第 {e.colno} 列 —— {e.msg}"
        ) from None
    if not isinstance(cfg, dict):
        raise ValueError(f"动作配置 {path} 的根节点必须是一个对象 {{}}")
    if "id" not in cfg:
        raise ValueError(f"动作配置 {path} 缺少 id 字段（动作标识）")
    if "counter" not in cfg:
        raise ValueError(f"动作配置 {path} 缺少 counter 段（计数配置）")
    if not cfg["counter"].get("conditions") and "signal" not in cfg["counter"]:
        raise ValueError(
            f"动作配置 {path} 的 counter 既没有 conditions，也没有 signal —— "
            f"至少要给一种计数方式（建议先跑 validate_config.py 看看）"
        )
    return Action(cfg)
