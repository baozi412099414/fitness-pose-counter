#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头能力探测 —— 看这台设备支持哪些可调参数（重点是变焦 zoom / 视野）

用途：判断能不能把画面「拉广」（缩小放大倍数），让空间不够时也能拍全身。
前提认知：软件层面只能裁剪（放大），不能扩宽视野；要「拉广」必须硬件支持。

用法（必须从系统自带「终端.app」跑）：
    .venv/bin/python camera_probe.py --cam 1
"""

import argparse
import sys

import cv2

BACKEND = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY

# 常见可读属性
PROPS = [
    "CAP_PROP_FRAME_WIDTH", "CAP_PROP_FRAME_HEIGHT", "CAP_PROP_FPS",
    "CAP_PROP_ZOOM", "CAP_PROP_FOCUS", "CAP_PROP_AUTOFOCUS",
    "CAP_PROP_EXPOSURE", "CAP_PROP_AUTO_EXPOSURE", "CAP_PROP_BRIGHTNESS",
    "CAP_PROP_CONTRAST", "CAP_PROP_SATURATION", "CAP_PROP_SHARPNESS",
    "CAP_PROP_GAIN", "CAP_PROP_PAN", "CAP_PROP_TILT", "CAP_PROP_ROLL",
    "CAP_PROP_IRIS", "CAP_PROP_BUFFERSIZE",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=1, help="摄像头设备号")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.cam, BACKEND)
    if not cap.isOpened():
        print(f"打不开设备号 {args.cam}，试试 --cam 0 / 2")
        return

    print(f"=== 设备号 {args.cam} 的可读属性 ===")
    for name in PROPS:
        prop = getattr(cv2, name, None)
        if prop is None:
            continue
        try:
            print(f"  {name:30s} = {cap.get(prop)}")
        except Exception as e:
            print(f"  {name:30s} 读失败: {e}")

    print("\n=== 变焦测试：能不能把画面拉广 / 拉近 ===")
    zoom = getattr(cv2, "CAP_PROP_ZOOM", None)
    if zoom is None:
        print("  这个 OpenCV 版本没有 CAP_PROP_ZOOM")
    else:
        before = cap.get(zoom)
        print(f"  当前 zoom = {before}")
        for z in (0.5, 1.0, 2.0, 3.0):
            ok = cap.set(zoom, z)
            got = cap.get(zoom)
            print(f"  set({z}) -> 返回 {ok}   读回 {got}")
        cap.set(zoom, before)   # 还原

    print("\n=== 分辨率测试：有哪些档位可设 ===")
    for (w, h) in [(640, 480), (1280, 720), (1920, 1080)]:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        aw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        ah = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"  请求 {w}x{h} -> 实际 {int(aw)}x{int(ah)}")

    cap.release()
    print("\n把以上输出整段贴回来，我判断能不能靠变焦解决")


if __name__ == "__main__":
    main()
