#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合成动作轨迹生成器 —— 选题 11：健身动作计数与姿态纠正

【为什么需要它】
判断阈值是否合理，理想做法是拿「真人标准动作 + 真人错误动作」视频来回归。
但真人素材难以获取（见 CLAUDE.md 的「阈值现状与校准要求」章节：用户无法自录，
网上素材适用性又差）。不过 —— **阈值行为本身是可以被验证的**：

    用程序生成符合人体比例的关键点轨迹，覆盖「标准动作」与「各类典型错误」，
    再检查程序是否按预期计数、是否按预期报出对应错误。

这本质上是把「参数敏感性分析」做成**可重复、可回归、不依赖任何视频**的自动化测试，
而且不受机位 / 光照 / 体型 / 遮挡的影响 —— 变量的控制比真人拍摄严格得多。

【用途】
  1. 验证某个阈值改完之后，标准动作还合格吗、错误动作还抓得住吗
  2. 扫描一个参数（例如下蹲深度），看计数与判定在哪里发生翻转 → 找到阈值的安全边界
  3. 答辩时演示「参数敏感性分析」，比空口说「我调过参」有力得多

【用法】
    .venv/bin/python motion_synth.py --all                      # 标准/错误用例全跑
    .venv/bin/python motion_synth.py --action squat --depth 110
    .venv/bin/python motion_synth.py --sweep squat --param depth --lo 85 --hi 175 --step 10
    .venv/bin/python motion_synth.py --action pushup --param low_back
"""

import argparse
import json
import math
import sys

from pose_logic import load_action

# MediaPipe Pose 关键点编号（只列这里用到的）
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_FOOT, R_FOOT = 31, 32


class Synth:
    """
    合成人体骨架。

    坐标约定：**以「肩宽」为长度单位**（肩宽 = 1.0），这样合成出来的比例与真实人体一致
    —— 这一点很关键：早期测试因为把「脚尖放在脚踝正下方」，导致蹲下时被误判成
    「膝超脚尖」（见 CLAUDE.md 记录）。合成数据的几何必须经得起推敲。

    最终输出会乘 `scale` 变成像素（默认一个肩宽 = 220px，接近真人 2 米外站立的画面比例）。
    """

    # 人体比例（肩宽 = 1.0 为基准，取自常见人体测量比例）
    SHOULDER_W = 1.00
    TORSO = 1.30          # 肩中点到髋中点
    UPPER_ARM = 0.72
    FOREARM = 0.68
    THIGH = 1.05
    SHIN = 1.00
    FOOT = 0.45           # 踝到脚尖的水平距离
    # 折叠角里由「小腿前倾」承担的比例，其余由「大腿后倾」承担。
    # 真实深蹲是「髋部向后坐 + 小腿适度前倾」，**不是对称折叠** ——
    # 如果按对称解（0.5/0.5）来合成，蹲到底时膝会跑到脚尖前面去，
    # 于是「标准深蹲」被误判成「膝超过脚尖」。这个 0.35 是照真实动作定的。
    SHIN_RATIO = 0.35

    def __init__(self, origin=(520.0, 300.0), scale=220.0):
        self.ox, self.oy = origin
        self.scale = scale

    # ------------------------------------------------------------------
    def _px(self, x, y):
        """人体坐标（单位=肩宽，y 向下为正）→ 像素坐标。"""
        return (int(round(self.ox + x * self.scale)),
                int(round(self.oy + y * self.scale)))

    @staticmethod
    def _blank():
        return [(0, 0)] * 33

    # ══════════════════════════════════════════════════════════════
    # 深蹲（侧面机位；人面朝画面右侧，脚尖在右）
    # ══════════════════════════════════════════════════════════════
    def squat_frame(self, knee_deg, lean_deg=0.0, knee_travel_deg=0.0, hip_shift=0.0):
        """
        生成一帧深蹲姿态。

        knee_deg       髋-膝-踝夹角（180 = 完全站直，90 ≈ 大腿与地面平行）
        lean_deg       上身前倾角（0 = 竖直；用来注入「上身前倾」错误）
        knee_travel_deg 膝相对小腿多前倾的角度（用来注入「膝超过脚尖」错误）
        hip_shift      髋部前后平移（单位=肩宽；正常深蹲髋应向后）
        """
        theta = math.radians(max(5.0, min(179.0, knee_deg)))
        fold = math.pi - theta                         # 总折叠角（α + β 恒定 = 膝角不变）
        t = math.radians(knee_travel_deg)
        # 小腿承担 fold 的一部分，其余由大腿后倾承担（体现「髋向后坐」）
        beta = fold * self.SHIN_RATIO + t              # 小腿前倾；+t 表示膝更往前
        alpha = (fold - fold * self.SHIN_RATIO) - t    # 大腿后倾；-t 抵消，保证 α+β = fold

        p = self._blank()
        # 踝固定在原点（脚踩地不动）
        ankle = (0.0, 0.0)
        # 膝：从踝往上前倾 beta
        knee = (ankle[0] + self.SHIN * math.sin(beta),
                ankle[1] - self.SHIN * math.cos(beta))
        # 髋：从膝往上、向后倾 alpha（+ hip_shift 表示更往后坐）
        hip = (knee[0] - self.THIGH * math.sin(alpha) - hip_shift,
               knee[1] - self.THIGH * math.cos(alpha))
        # 肩：从髋往上、按前倾角 lean 前移
        lean = math.radians(lean_deg)
        shoulder = (hip[0] + self.TORSO * math.sin(lean),
                    hip[1] - self.TORSO * math.cos(lean))
        # 手：自然下垂（肘在肩下、腕在肘下）
        elbow = (shoulder[0] + 0.10, shoulder[1] + self.UPPER_ARM)
        wrist = (elbow[0] + 0.10, elbow[1] + self.FOREARM)
        # 脚尖：脚踝前方
        toe = (ankle[0] + self.FOOT, ankle[1])

        half_sw = self.SHOULDER_W / 2.0
        for (hip_i, knee_i, ankle_i, foot_i, sh_i, el_i, wr_i), dx in (
                ((L_HIP, L_KNEE, L_ANKLE, L_FOOT, L_SHOULDER, L_ELBOW, L_WRIST), -0.04),
                ((R_HIP, R_KNEE, R_ANKLE, R_FOOT, R_SHOULDER, R_ELBOW, R_WRIST), +0.04)):
            # 侧面机位：左右两侧几乎重合，只错开一点点表示前后腿
            p[hip_i] = self._px(hip[0] + dx, hip[1])
            p[knee_i] = self._px(knee[0] + dx, knee[1])
            p[ankle_i] = self._px(ankle[0] + dx * 0.5, ankle[1])
            p[foot_i] = self._px(toe[0] + dx * 0.5, toe[1])
            p[sh_i] = self._px(shoulder[0] + dx * 3, shoulder[1])
            p[el_i] = self._px(elbow[0] + dx * 3, elbow[1])
            p[wr_i] = self._px(wrist[0] + dx * 3, wrist[1])
        p[NOSE] = self._px(shoulder[0] + 0.18, shoulder[1] - 0.30)
        # 补上躯干与头部的其它点，让可见性检查不至于因缺省 (0,0) 而判为不可见
        for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 21, 22, 29, 30):
            p[i] = self._px(shoulder[0] + 0.1, shoulder[1] + 0.1)
        return p

    def squat_sequence(self, depth=110.0, reps=3, period=2.0, fps=30.0, top=175.0, **err):
        """一个完整的深蹲序列：站立 → 下蹲到 depth → 站起，重复 reps 次。"""
        frames = []
        per = max(2, int(period * fps))
        half = per // 2
        for _ in range(reps):
            for i in range(half):                       # 下蹲
                k = i / max(1, half - 1)
                ang = top + (depth - top) * (0.5 - 0.5 * math.cos(math.pi * k))
                frames.append(self.squat_frame(ang, **err))
            for i in range(half):                       # 站起
                k = i / max(1, half - 1)
                ang = depth + (top - depth) * (0.5 - 0.5 * math.cos(math.pi * k))
                frames.append(self.squat_frame(ang, **err))
        return frames

    # ══════════════════════════════════════════════════════════════
    # 俯卧撑（侧面机位；身体接近水平）
    # ══════════════════════════════════════════════════════════════
    def pushup_frame(self, elbow_deg, body_sag_deg=0.0):
        """
        elbow_deg     肩-肘-腕夹角（180 = 手臂伸直撑起，90 = 下压到位）
        body_sag_deg  塌腰角（0 = 头肩髋踝一条直线；>0 表示髋部下沉）
        """
        theta = math.radians(max(20.0, min(180.0, elbow_deg)))
        half = (math.pi - theta) / 2.0
        sag = math.radians(body_sag_deg)

        p = self._blank()
        # 身体「直线」参考位置：以肩为起点水平向右延伸（头在左、脚在右）
        shoulder = (0.0, 0.0)
        hip_line = shoulder[0] + self.TORSO
        knee_line = hip_line + self.THIGH
        ankle_line = knee_line + self.SHIN
        # 塌腰的定义是「腰背塌下去」—— 肩和踝基本不动，**只有髋部下沉**，身体成弓形。
        # 早期实现让整条身体一起倾斜，那样肩-髋-踝仍然共线，collinear 永远检测不出来。
        sag_off = math.tan(sag) * self.TORSO
        hip = (hip_line, shoulder[1] + sag_off)
        knee = (knee_line, shoulder[1] + sag_off * 0.45)     # 中途插值，让曲线平滑
        ankle = (ankle_line, shoulder[1])                    # 踝回到直线
        # 手臂：从肩往下支撑；肘角决定肘的位置
        elbow = (shoulder[0] + self.UPPER_ARM * math.sin(half),
                 shoulder[1] + self.UPPER_ARM * math.cos(half))
        wrist = (elbow[0] - self.FOREARM * math.sin(half),
                 elbow[1] + self.FOREARM * math.cos(half))
        # 脚尖（脚掌踩地）
        toe = (ankle[0] + self.FOOT * 0.4, ankle[1] + 0.05)

        for (sh_i, el_i, wr_i, hip_i, knee_i, ankle_i, foot_i), dy in (
                ((L_SHOULDER, L_ELBOW, L_WRIST, L_HIP, L_KNEE, L_ANKLE, L_FOOT), -0.05),
                ((R_SHOULDER, R_ELBOW, R_WRIST, R_HIP, R_KNEE, R_ANKLE, R_FOOT), +0.05)):
            p[sh_i] = self._px(shoulder[0], shoulder[1] + dy)
            p[el_i] = self._px(elbow[0], elbow[1] + dy)
            p[wr_i] = self._px(wrist[0], wrist[1] + dy)
            p[hip_i] = self._px(hip[0], hip[1] + dy)
            p[knee_i] = self._px(knee[0], knee[1] + dy)
            p[ankle_i] = self._px(ankle[0], ankle[1] + dy)
            p[foot_i] = self._px(toe[0], toe[1] + dy)
        p[NOSE] = self._px(shoulder[0] - 0.35, shoulder[1])
        for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 21, 22):
            p[i] = self._px(shoulder[0] - 0.2, shoulder[1])
        return p

    def pushup_sequence(self, bottom=95.0, reps=3, period=2.4, fps=30.0, top=172.0, **err):
        frames = []
        per = max(2, int(period * fps))
        half = per // 2
        for _ in range(reps):
            for i in range(half):
                k = i / max(1, half - 1)
                ang = top + (bottom - top) * (0.5 - 0.5 * math.cos(math.pi * k))
                frames.append(self.pushup_frame(ang, **err))
            for i in range(half):
                k = i / max(1, half - 1)
                ang = bottom + (top - bottom) * (0.5 - 0.5 * math.cos(math.pi * k))
                frames.append(self.pushup_frame(ang, **err))
        return frames

    # ══════════════════════════════════════════════════════════════
    # 开合跳（正面机位）
    # ══════════════════════════════════════════════════════════════
    def jumping_jack_frame(self, shoulder_deg=25.0, foot_ratio=0.10,
                           shoulder_deg_r=None, foot_ratio_r=None):
        """
        shoulder_deg   左臂肩角（肘-肩-髋，180 = 手臂举过头顶；25 ≈ 手垂在身侧）
        foot_ratio     双脚横向距离 / 肩宽
        shoulder_deg_r / foot_ratio_r  右臂、右脚单独给值（用来注入「左右不同步」）
        """
        sr = shoulder_deg if shoulder_deg_r is None else shoulder_deg_r
        fr = foot_ratio if foot_ratio_r is None else foot_ratio_r

        p = self._blank()
        cx = 0.0
        sh_y = 0.0
        hip_y = self.TORSO
        half_sw = self.SHOULDER_W / 2.0

        for sh_i, el_i, wr_i, hip_i, knee_i, ankle_i, foot_i, side, ang, frate in (
                (L_SHOULDER, L_ELBOW, L_WRIST, L_HIP, L_KNEE, L_ANKLE, L_FOOT,
                 -1, shoulder_deg, foot_ratio),
                (R_SHOULDER, R_ELBOW, R_WRIST, R_HIP, R_KNEE, R_ANKLE, R_FOOT,
                 +1, sr, fr)):
            sh = (cx + side * half_sw, sh_y)
            hip = (cx + side * half_sw * 0.75, hip_y)
            # 踝的位置**直接由 foot_ratio 决定**：让 |x27 − x28| / 肩宽 恰好等于 foot_ratio。
            # 早期实现把 frate 当成「相对髋的额外张开量」，于是传 0.10（以为并拢）
            # 实际得到比值 0.95 —— 超过退出线 0.75，永远回不到「并拢」态，结果一个都不计数。
            ankle_x = cx + side * (frate / 2.0)
            knee = ((hip[0] + ankle_x) / 2.0, hip[1] + self.THIGH)
            ankle = (ankle_x, knee[1] + self.SHIN)
            toe = (ankle[0] + side * 0.12, ankle[1])
            # 手臂：肩角 a 表示 肘向量 与 髋向量 的夹角（髋在肩正下方）
            a = math.radians(max(0.0, min(180.0, ang)))
            # 手举起时肘朝上、放下时肘朝下
            # 肩角 a 的含义：a=0 手垂在身侧（肘在肩正下方）、a=90 手平举、a=180 举过头顶。
            #   ex = 肩x + 侧向 * L*sin(a)     ey = 肩y + L*cos(a)
            # 注意 ey 用 **+cos**：a=180 时 cos=-1 → 肘到肩上方；写成 -cos 会把手举到身下。
            ex = sh[0] + side * self.UPPER_ARM * math.sin(a)
            ey = sh[1] + self.UPPER_ARM * math.cos(a)
            wx = ex + side * self.FOREARM * math.sin(a)
            wy = ey + self.FOREARM * math.cos(a)
            p[sh_i] = self._px(*sh)
            p[el_i] = self._px(ex, ey)
            p[wr_i] = self._px(wx, wy)
            p[hip_i] = self._px(*hip)
            p[knee_i] = self._px(*knee)
            p[ankle_i] = self._px(*ankle)
            p[foot_i] = self._px(*toe)
        p[NOSE] = self._px(cx, sh_y - 0.35)
        for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 21, 22, 29, 30):
            p[i] = self._px(cx, sh_y - 0.2)
        return p

    def jumping_jack_sequence(self, up_shoulder=165.0, up_foot=2.0, reps=3,
                              period=1.6, fps=30.0, down_shoulder=25.0,
                              down_foot=0.10, up_shoulder_r=None, **err):
        # up_shoulder_r 表示「右臂举起的最高角度」，也要跟着周期一起插值下去；
        # 早期实现把它当固定值传，导致并拢阶段右臂仍是 100°，永远回不到还原态而不计数。
        ur = up_shoulder if up_shoulder_r is None else up_shoulder_r
        frames = []
        per = max(2, int(period * fps))
        half = per // 2
        for _ in range(reps):
            for i in range(half):                    # 张开
                k = i / max(1, half - 1)
                m = 0.5 - 0.5 * math.cos(math.pi * k)
                frames.append(self.jumping_jack_frame(
                    down_shoulder + (up_shoulder - down_shoulder) * m,
                    down_foot + (up_foot - down_foot) * m,
                    shoulder_deg_r=down_shoulder + (ur - down_shoulder) * m, **err))
            for i in range(half):                    # 并拢
                k = i / max(1, half - 1)
                m = 0.5 - 0.5 * math.cos(math.pi * k)
                frames.append(self.jumping_jack_frame(
                    up_shoulder + (down_shoulder - up_shoulder) * m,
                    up_foot + (down_foot - up_foot) * m,
                    shoulder_deg_r=ur + (down_shoulder - ur) * m, **err))
        return frames

    # ------------------------------------------------------------------
    def build(self, action_id, **kw):
        """按动作 id 生成序列。"""
        if action_id == "squat":
            return self.squat_sequence(**kw)
        if action_id == "pushup":
            return self.pushup_sequence(**kw)
        if action_id == "jumping_jack":
            return self.jumping_jack_sequence(**kw)
        raise ValueError(f"没有为「{action_id}」定义合成轨迹，可选 squat / pushup / jumping_jack")


# ══════════════════════════════════════════════════════════════════
# 跑一遍合成序列，看程序怎么判
# ══════════════════════════════════════════════════════════════════
def run_sequence(action_id, frames, fps=30.0):
    """
    把合成序列喂给动作解释器，返回统计结果。

    返回 dict：reps（计了几次）、errors（各错误事件次数）、first_rep_errors（第一次动作的错误）
    """
    action = load_action(f"configs/{action_id}.json")
    vis = [1.0] * 33
    errors = {}
    first_errors = None
    count = 0
    for i, pts in enumerate(frames):
        c, stage, sig, hits, checks = action.update(pts, vis, now=i / fps)
        if c > count:                      # 刚计上一次
            count = c
            names = [h["name"] for h in hits]
            if first_errors is None:
                first_errors = names
            for n in names:
                errors[n] = errors.get(n, 0) + 1
    return {"reps": count, "errors": errors, "first_rep_errors": first_errors or []}


def fmt_errors(errors):
    if not errors:
        return "无"
    return "、".join(f"{k}×{v}" for k, v in sorted(errors.items(), key=lambda kv: -kv[1]))


def export_sequence(action_id, frames, path, fps=30.0, note=""):
    """
    把合成序列导出成 `pose_player.py` 能读的数据文件。

    用途：给「自带数据测试动作」提供一个**格式模板** ——
    照着这个文件的结构换成你自己的数据即可。
    只导出**实际用到的关键点**（其余是占位），文件小很多也更好读。
    """
    used = sorted({i for p in frames for i in range(33) if tuple(p[i]) != (0, 0)})
    data = {
        "name": f"{action_id} 合成序列（{len(frames)} 帧）",
        "note": note or "由 motion_synth.py 导出，可直接用 pose_player.py 回放",
        "action": action_id,
        "fps": fps,
        "points": used,
        "frames": [[list(p[i]) for i in used] for p in frames],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"已导出 {len(frames)} 帧、{len(used)} 个关键点 → {path}")
    return path


# ══════════════════════════════════════════════════════════════════
# 内置用例：标准动作 + 典型错误
# ══════════════════════════════════════════════════════════════════
# 每条：(说明, 参数, 期望计数>0?, 期望报出的错误名 或 None 表示不该报错)
CASES = {
    "squat": [
        ("标准深蹲（蹲到大腿平行 95°）", {"depth": 95}, True, None),
        ("浅蹲（只到 135°）", {"depth": 135}, True, "not_deep_enough"),
        ("非常浅（只到 160°，连计数线 140° 都没到）", {"depth": 160}, False, None),
        ("膝超过脚尖", {"depth": 95, "knee_travel_deg": 26}, True, "knee_over_toe"),
        ("上身前倾过度（前倾 55°）", {"depth": 95, "lean_deg": 55}, True, "torso_lean_excessive"),
    ],
    "pushup": [
        ("标准俯卧撑（下压到 95°）", {"bottom": 95}, True, None),
        ("下压不够（只到 135°）", {"bottom": 135}, True, "not_low_enough"),
        ("塌腰", {"bottom": 95, "body_sag_deg": 18}, True, "low_back"),
    ],
    "jumping_jack": [
        ("标准开合跳", {"up_shoulder": 168, "up_foot": 2.2}, True, None),
        ("手没举过头顶（只到 100°）", {"up_shoulder": 100, "up_foot": 2.2}, True, "hand_not_up"),
        # 0.6 连进入门槛（0.95）都没到 → 本来就不该算成一次动作
        ("腿张得不够（0.6 倍肩宽，不到门槛）", {"up_shoulder": 168, "up_foot": 0.6}, False, None),
        ("腿张开不足但过了门槛（1.0 倍）", {"up_shoulder": 168, "up_foot": 1.0}, True, "legs_not_apart"),
        ("双臂不同步（左 168° 右 100°）",
         {"up_shoulder": 168, "up_foot": 2.2, "up_shoulder_r": 100}, True, "arm_asymmetry"),
    ],
}


def cmd_all():
    print("═" * 78)
    print("合成轨迹回归：标准动作应计数且不报错；错误动作应报出对应错误")
    print("═" * 78)
    synth = Synth()
    bad = 0
    for action_id, cases in CASES.items():
        print(f"\n【{action_id}】")
        for desc, params, want_count, want_err in cases:
            frames = synth.build(action_id, reps=3, **params)
            res = run_sequence(action_id, frames)
            reps = res["reps"]
            names = set(res["errors"])
            ok_count = (reps > 0) if want_count else (reps == 0)
            ok_err = (want_err is None and not names) or (want_err in names)
            mark = "✅" if (ok_count and ok_err) else "❌"
            if not (ok_count and ok_err):
                bad += 1
            expect = "不报错" if want_err is None else f"报 {want_err}"
            print(f"  {mark} {desc:28s} 计数 {reps:>2}　错误 {fmt_errors(res['errors']) or '无'}"
                  f"　（期望：计数≥1、{expect}）")
    print("\n" + "─" * 78)
    print(f"不符合预期的用例：{bad} 个")
    return 1 if bad else 0


def cmd_sweep(action_id, param, lo, hi, step):
    """扫描一个参数，看计数与判定在哪个位置发生翻转 —— 即阈值的安全边界。"""
    print("═" * 78)
    print(f"参数扫描：{action_id} 的 {param} 从 {lo} 到 {hi}（步长 {step}）")
    print("═" * 78)
    print(f"{'参数值':>8}　{'计数':>4}　{'错误事件'}")
    print("─" * 78)
    synth = Synth()
    v = lo
    rows = []
    while v <= hi + 1e-9:
        frames = synth.build(action_id, reps=3, **{param: v})
        res = run_sequence(action_id, frames)
        rows.append((v, res["reps"], res["errors"]))
        print(f"{v:>8g}　{res['reps']:>4}　{fmt_errors(res['errors'])}")
        v += step
    # 找翻转点：错误集合第一次发生变化的位置
    flips = []
    for i in range(1, len(rows)):
        if set(rows[i][2]) != set(rows[i - 1][2]):
            flips.append((rows[i - 1][0], rows[i][0],
                          fmt_errors(rows[i - 1][2]), fmt_errors(rows[i][2])))
    print("\n" + "─" * 78)
    if flips:
        print("判定发生翻转的位置（说明阈值就落在这个区间）：")
        for a, b, ea, eb in flips:
            print(f"  {a:g} → {b:g}　「{ea}」变成「{eb}」")
    else:
        print("整段区间内判定没有变化（该参数对当前阈值不敏感）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="合成动作轨迹生成器（不依赖摄像头/视频）")
    ap.add_argument("--all", action="store_true", help="跑全部内置用例（标准+错误）")
    ap.add_argument("--action", default="squat", help="动作 id（squat/pushup/jumping_jack）")
    ap.add_argument("--reps", type=int, default=3, help="合成几个完整动作")
    ap.add_argument("--sweep", default=None, help="要扫描参数的动作 id")
    ap.add_argument("--param", default="depth", help="要扫描的参数名（如 depth / bottom / up_foot）")
    ap.add_argument("--lo", type=float, default=85.0)
    ap.add_argument("--hi", type=float, default=175.0)
    ap.add_argument("--step", type=float, default=10.0)
    ap.add_argument("--export", default=None,
                    help="把这次生成的序列导出成数据文件（供 pose_player.py 回放）")
    # 单次运行时可覆盖的常用参数
    for name, dflt in (("depth", 110.0), ("bottom", 95.0), ("up_shoulder", 165.0),
                       ("up_foot", 2.0), ("lean_deg", 0.0), ("knee_travel_deg", 0.0),
                       ("body_sag_deg", 0.0)):
        ap.add_argument(f"--{name.replace('_', '-')}", dest=name, type=float, default=dflt)
    args = ap.parse_args(argv)

    if args.all:
        return cmd_all()
    if args.sweep:
        return cmd_sweep(args.sweep, args.param, args.lo, args.hi, args.step)

    # 单次运行：用命令行给的参数生成一次，打印判定明细
    synth = Synth()
    params = {"depth": args.depth, "bottom": args.bottom, "up_shoulder": args.up_shoulder,
              "up_foot": args.up_foot, "lean_deg": args.lean_deg,
              "knee_travel_deg": args.knee_travel_deg, "body_sag_deg": args.body_sag_deg}
    # 只把该动作认识的参数传进去
    accepted = {
        "squat": ("depth", "lean_deg", "knee_travel_deg"),
        "pushup": ("bottom", "body_sag_deg"),
        "jumping_jack": ("up_shoulder", "up_foot"),
    }[args.action]
    params = {k: v for k, v in params.items() if k in accepted}

    frames = synth.build(args.action, reps=args.reps, **params)
    if args.export:
        export_sequence(args.action, frames, args.export)
    res = run_sequence(args.action, frames)
    print(f"动作：{args.action}　参数：{params}　合成 {len(frames)} 帧（{len(frames)/30:.1f} 秒）")
    print(f"计数：{res['reps']} 次（合成 {args.reps} 个完整动作）")
    print(f"错误事件：{fmt_errors(res['errors'])}")
    print(f"第一次动作的判定：{res['first_rep_errors'] or '全部合格'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
