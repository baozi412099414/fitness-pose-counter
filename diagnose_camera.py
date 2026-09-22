#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头诊断 —— 一次性把所有排查信息打出来

用法：
    .venv/bin/python diagnose_camera.py

把完整输出（包括红色的 warning）复制发回来即可定位问题。
"""

import os
import subprocess
import sys

BAR = "=" * 64


def title(s):
    print(f"\n{BAR}\n  {s}\n{BAR}")


# ---------------------------------------------------------------- 1. cv2 本体
title("1. cv2 从哪来、什么版本")
try:
    import cv2
except Exception as e:
    print(f"导入 cv2 失败：{e}")
    sys.exit(1)

print(f"  版本      : {cv2.__version__}")
print(f"  模块路径  : {cv2.__file__}")
print(f"  解释器    : {sys.executable}")
print(f"  Python    : {sys.version.split()[0]}")

# 同时装了 opencv-python 和 opencv-contrib-python 会互相覆盖
try:
    from importlib.metadata import distributions
    ocv = sorted(
        f"{d.metadata['Name']}=={d.version}"
        for d in distributions()
        if d.metadata["Name"] and "opencv" in d.metadata["Name"].lower()
    )
    print(f"  已装的 opencv 包 : {', '.join(ocv) if ocv else '(查不到)'}")
    if len(ocv) > 1:
        print("  ⚠ 装了多个 opencv 包，它们会互相覆盖 cv2，可能是本次故障的原因")
except Exception as e:
    print(f"  (包列表读取失败: {e})")


# ------------------------------------------------- 2. 这个 cv2 编进了哪些后端
title("2. Video I/O 后端（关键：有没有 AVFOUNDATION）")
try:
    backends = cv2.videoio_registry.getCameraBackends()
    names = [cv2.videoio_registry.getBackendName(b) for b in backends]
    print(f"  可用摄像头后端 : {', '.join(names) if names else '(空)'}")
    if not any("AVFOUNDATION" in n.upper() for n in names):
        print("  ⚠ 没有 AVFOUNDATION —— macOS 上没它就读不到摄像头，这就是原因")
except Exception as e:
    print(f"  查询失败：{e}")
    info = cv2.getBuildInformation()
    keep, out = False, []
    for line in info.splitlines():
        if line.strip().startswith("Video I/O"):
            keep = True
        elif keep and line.strip() and not line.startswith(" "):
            break
        if keep:
            out.append(line)
    print("\n".join(out[:25]))


# --------------------------------------------- 3. 系统层面认不认得这些摄像头
title("3. macOS 系统认得的摄像头（绕开 OpenCV）")
if sys.platform == "darwin":
    try:
        r = subprocess.run(
            ["system_profiler", "SPCameraDataType"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout or "").strip()
        print(out if out else "  (系统没报告任何摄像头)")
    except Exception as e:
        print(f"  查询失败：{e}")
else:
    print("  非 macOS，跳过")


# ------------------------------------------------------- 4. 逐后端逐设备号试
title("4. 逐个尝试打开（下面的 warning 也是有用信息）")

cands = []
for attr in ("CAP_AVFOUNDATION", "CAP_ANY"):
    if hasattr(cv2, attr):
        cands.append((attr, getattr(cv2, attr)))

for name, backend in cands:
    print(f"\n  --- 后端 {name} ---")
    for i in range(4):
        try:
            cap = cv2.VideoCapture(i, backend)
            opened = cap.isOpened()
            ok, frame = (False, None)
            if opened:
                ok, frame = cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                print(f"    设备 {i}: 打开=True  读帧=True   {w}x{h}   <== 可用")
            elif opened:
                print(f"    设备 {i}: 打开=True  读帧=False  (多半是权限没给，或 iPhone 没唤醒)")
            else:
                print(f"    设备 {i}: 打开=False")
            cap.release()
        except Exception as e:
            print(f"    设备 {i}: 异常 {e}")


# ------------------------------------------------------------ 5. 权限提示
title("5. 权限自查")
print("""  macOS 的摄像头权限是按「哪个 App 启动了这个进程」算的。
  你从终端跑 python，要授权的就是「终端」，不是 python。

  检查：系统设置 → 隐私与安全性 → 摄像头 → 看列表里有没有「终端」，开关是否打开。

  · 列表里没有「终端」 -> 说明从没触发过授权请求，见下面的最小测试
  · 有但是关着         -> 打开它，然后【完全退出终端】(Cmd+Q) 再重开
  · 有且开着还是不行   -> 把开关关掉再打开，Cmd+Q 退出终端重开

  最小测试（会强制触发一次权限请求）：
      .venv/bin/python -c "import cv2; c=cv2.VideoCapture(0); print('opened=',c.isOpened()); print('read=',c.read()[0])"
""")

print(BAR)
print("  把以上全部输出复制发回即可")
print(BAR)
