#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二头弯举的合成关键点数据生成器。

为什么单独写一个：`motion_synth.py` 里只内置了深蹲 / 俯卧撑 / 开合跳三种动作，
二头弯举是**配置驱动**加的第四个动作（`configs/bicep_curl.json`），
这里顺手给它造一批「标准动作 / 半程 / 后仰借力」的轨迹，
用来验证配置写对了没有，也给网页版的「回放」模式提供样本。

用法：
    .venv/bin/python gen_bicep_curl.py          # 生成并打印判定结果
    .venv/bin/python gen_bicep_curl.py --check  # 只跑判定，不写文件
"""

from __future__ import annotations

import argparse
import math
import os

from motion_synth import Synth, export_sequence, run_sequence

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
WEB_SAMPLES = os.path.join(HERE, "web", "frontend", "public", "samples")

# 侧面机位：人面朝画面右侧（+x 为前）
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_FOOT, R_FOOT = 31, 32


def _ease(t: float) -> float:
    """0→1 的余弦缓动，动作看起来像真人而不是线性机器人。"""
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


class CurlSynth(Synth):
    """在 Synth 的人体比例上，加一个「站着弯举」的姿态生成。"""

    def curl_frame(self, elbow_deg: float, lean_deg: float = 0.0,
                   swing_deg: float = 0.0):
        """
        elbow_deg  肩-肘-腕夹角：180 = 手臂完全伸直下垂，40 ≈ 弯到顶
        lean_deg   躯干后仰角（0 = 竖直；正数 → 上身往后倒，用来注入「借力」错误）
        swing_deg  上臂前摆角（0 = 上臂贴身体）
        """
        p = self._blank()

        # 下肢：脚踩地、腿伸直
        ankle = (0.0, 0.0)
        knee = (0.0, -self.SHIN)
        hip = (0.0, -self.SHIN - self.THIGH)

        # 躯干：后仰角作用在髋→肩
        lean = math.radians(lean_deg)
        shoulder = (hip[0] + self.TORSO * math.sin(lean),
                    hip[1] - self.TORSO * math.cos(lean))

        # 上臂：从肩往下，可带一点前摆
        swing = math.radians(swing_deg)
        elbow = (shoulder[0] + self.UPPER_ARM * math.sin(swing),
                 shoulder[1] + self.UPPER_ARM * math.cos(swing))

        # 前臂：从肘出发，θ 是从「竖直向下」量起的角度；θ = 180° - 肘角
        theta = math.radians(180.0 - max(5.0, min(178.0, elbow_deg)))
        wrist = (elbow[0] + self.FOREARM * math.sin(theta),
                 elbow[1] + self.FOREARM * math.cos(theta))

        foot = (ankle[0] + self.FOOT, ankle[1])
        # 侧面机位左右两侧几乎重合，给一点 x 偏移，看起来不像「一个点」。
        # 计数与判定只用左侧（11/13/15 与 11/23/25），右侧只是让骨架画得完整。
        back = -0.16

        p[L_SHOULDER] = self._px(*shoulder)
        p[L_ELBOW] = self._px(*elbow)
        p[L_WRIST] = self._px(*wrist)
        p[L_HIP] = self._px(*hip)
        p[L_KNEE] = self._px(*knee)
        p[L_ANKLE] = self._px(*ankle)
        p[L_FOOT] = self._px(*foot)

        p[R_SHOULDER] = self._px(shoulder[0] + back, shoulder[1])
        p[R_ELBOW] = self._px(elbow[0] + back, elbow[1])
        p[R_WRIST] = self._px(wrist[0] + back, wrist[1])
        p[R_HIP] = self._px(hip[0] + back, hip[1])
        p[R_KNEE] = self._px(knee[0] + back, knee[1])
        p[R_ANKLE] = self._px(ankle[0] + back, ankle[1])
        p[R_FOOT] = self._px(foot[0] + back, foot[1])

        p[0] = self._px(shoulder[0] + 0.18, shoulder[1] - 0.55)   # 鼻子（只为骨架完整）
        return p

    def curl_sequence(self, curl_deg: float = 40.0, up_deg: float = 170.0,
                      lean_deg: float = 0.0, swing_deg: float = 0.0,
                      reps: int = 3, fps: float = 30.0,
                      down_frames: int = 26, hold_frames: int = 10,
                      up_frames: int = 26, gap_frames: int = 20):
        """3 次弯举：起始静立 → 弯起 → 顶端停一下 → 放下 → 静立，循环。"""
        frames = [self.curl_frame(up_deg, lean_deg, swing_deg)] * gap_frames
        for _ in range(reps):
            for i in range(down_frames):
                t = _ease((i + 1) / down_frames)
                frames.append(self.curl_frame(
                    up_deg - (up_deg - curl_deg) * t, lean_deg, swing_deg))
            frames += [self.curl_frame(curl_deg, lean_deg, swing_deg)] * hold_frames
            for i in range(up_frames):
                t = _ease((i + 1) / up_frames)
                frames.append(self.curl_frame(
                    curl_deg + (up_deg - curl_deg) * t, lean_deg, swing_deg))
            frames += [self.curl_frame(up_deg, lean_deg, swing_deg)] * gap_frames
        return frames, fps


CASES = [
    # 文件名, 说明, 参数
    ("bicep_curl_standard", "标准二头弯举：弯到 40°，放回 170°",
     {"curl_deg": 40, "up_deg": 170}),
    ("bicep_curl_half", "半程弯举：只弯到 90°，没到位",
     {"curl_deg": 90, "up_deg": 170}),
    ("bicep_curl_swing", "后仰借力：躯干后倒 14°",
     {"curl_deg": 40, "up_deg": 170, "lean_deg": 14}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只跑判定，不写文件")
    args = ap.parse_args()

    synth = CurlSynth()
    os.makedirs(SAMPLES, exist_ok=True)
    if not args.check:
        os.makedirs(WEB_SAMPLES, exist_ok=True)

    print(f"{'样本':<26}{'计数':<6}{'报出的错误'}")
    print("─" * 78)
    for name, note, kw in CASES:
        frames, fps = synth.curl_sequence(**kw)
        result = run_sequence("bicep_curl", frames, fps=fps)
        errors = "、".join(f"{k}×{v}" for k, v in result["errors"].items()) or "无"
        print(f"{name:<26}{result['reps']:<6}{errors}")
        if not args.check:
            path = os.path.join(SAMPLES, f"{name}.json")
            export_sequence("bicep_curl", frames, path, fps=fps, note=note)
            # 网页版的回放样本从 public/samples/ 取，同步一份过去
            with open(path, encoding="utf-8") as src, \
                    open(os.path.join(WEB_SAMPLES, f"{name}.json"), "w",
                         encoding="utf-8") as dst:
                dst.write(src.read())
    print("─" * 78)
    if not args.check:
        print(f"已写入 {SAMPLES} 与 {WEB_SAMPLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
