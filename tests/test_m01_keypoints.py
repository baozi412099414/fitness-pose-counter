"""模块 01 测试 —— 人体关键点实时检测（核心模块）

对应《选题说明》第 11 题「功能模块」第 1 项：用 MediaPipe Pose 从摄像头画面实时检测 33 个关键点。
只做**契约验证**、不改被测代码：模型是否完整、能否用该模型创建 PoseLandmarker、空图必须返回
0 个 pose（造一张有人的真图不现实）、配置里的关键点编号必须 < 33（最能抓配置写错）、Camera
线程启停契约、摄像头打不开记为「跳过」而不是失败。
"""

import json
import os
import sys
import threading
import time

from harness import suite

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import realtime_pose

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "pose_landmarker_lite.task")
CONFIG_DIR = os.path.join(ROOT, "configs")


def _walk_points(node, out):
    """递归收集配置里所有 points / unit_points 的关键点编号。"""
    if isinstance(node, dict):
        for key, val in node.items():
            if key in ("points", "unit_points") and isinstance(val, list):
                out.extend(int(v) for v in val if isinstance(v, (int, float)))
            else:
                _walk_points(val, out)
    elif isinstance(node, list):
        for item in node:
            _walk_points(item, out)


@suite("模块 01 · 人体关键点实时检测")
def _run(t):
    t.section("模型文件与依赖")
    size = os.path.getsize(MODEL) if os.path.exists(MODEL) else 0
    t.check("模型 pose_landmarker_lite.task 存在且大小 > 1MB（实际 %.2f MB）" % (size / 1048576.0),
            size > 1024 * 1024 and os.path.exists(os.path.join(ROOT, realtime_pose.MODEL_PATH)),
            "大小=%d 字节（>1048576 才算完整）；MODEL_PATH=%r 可解析=是" % (size, realtime_pose.MODEL_PATH))
    t.truthy("mediapipe 可 import 且版本号可读", getattr(mp, "__version__", None))
    t.section("PoseLandmarker：创建 + 空图不崩")
    # 和主程序一样用**相对路径** MODEL_PATH（相对项目根）：MediaPipe 1.1.1 的 C++ 层在本机
    # 打不开含中文的绝对路径（实测 FileNotFoundError: ...\选题 2\...），而项目目录名就是中文。
    landmarker, old_cwd, t0 = None, os.getcwd(), time.time()
    try:
        os.chdir(ROOT)
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=realtime_pose.MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,           # 单帧模式，测试里最好控制
            num_poses=1)
        landmarker = vision.PoseLandmarker.create_from_options(options)
        t.check("用该模型在 RunningMode.IMAGE 下能创建 PoseLandmarker", True,
                "以相对路径 %r 从项目根创建，用时 %.1f 秒" % (realtime_pose.MODEL_PATH, time.time() - t0))
    except Exception as e:
        t.check("用该模型在 RunningMode.IMAGE 下能创建 PoseLandmarker", False,
                "初始化抛异常 %s: %s" % (type(e).__name__, e))
    finally:
        os.chdir(old_cwd)

    if landmarker is not None:
        try:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)          # 纯黑图 = 画面里没有人
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=blank))
            lms, world, err = res.pose_landmarks, res.pose_world_landmarks, None
        except Exception as e:
            lms, world, err = None, None, "%s: %s" % (type(e).__name__, e)
        finally:
            landmarker.close()
        t.check("纯黑 640x480 图上 detect 不崩，pose_landmarks 是 list 且长度为 0（没人 = 0 个 pose）",
                err is None and isinstance(lms, list) and len(lms) == 0
                and isinstance(world, list) and len(world) == 0,
                "异常=%r type=%r len=%r world=%r（有人时应为 list[list[33]]）"
                % (err, type(lms).__name__, None if lms is None else len(lms), world))

    t.section("关键点编号合法性（0~32 共 33 个）")
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
        nums = [int(p.value) for p in mp.solutions.pose.PoseLandmark]
        t.check("PoseLandmark 枚举共 33 个关键点、编号范围 0~32",
                len(nums) == 33 and min(nums) == 0 and max(nums) == 32,
                "数量=%d 范围=%r~%r" % (len(nums), min(nums), max(nums)))
    else:
        t.check("跳过：mediapipe %s 已移除 legacy mp.solutions，无法枚举 PoseLandmark；"
                "33 点契约改用下一条项目常量校验" % (getattr(mp, "__version__", "?"),),
                True, "跳过原因：mp.solutions 不存在（本机 mediapipe 只保留 tasks API）")
    used = [i for pair in realtime_pose.SKELETON for i in pair]
    t.check("realtime_pose.SKELETON 用到的关键点编号全部落在 0~32（画骨架不会 IndexError）",
            len(used) > 0 and all(0 <= i < 33 for i in used),
            "连线 %d 条，编号范围 %r~%r" % (len(realtime_pose.SKELETON), min(used), max(used)))

    t.section("动作配置里的关键点编号")
    files = sorted(os.path.join(CONFIG_DIR, f) for f in os.listdir(CONFIG_DIR) if f.endswith(".json"))
    bad, total = [], 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            idxs = []
            _walk_points(json.load(f), idxs)
        total += len(idxs)
        bad += [(os.path.basename(path), i) for i in idxs if not (0 <= i < 33)]
    # 同时要求「至少 3 份配置」：空目录会让编号校验假通过
    t.check("configs/*.json 的 points/unit_points 编号全部 < 33（%d 份配置共 %d 个编号，需 ≥3 份）"
            % (len(files), total), len(files) >= 3 and total > 0 and not bad,
            "越界编号=%r（写错编号会让角度/距离算到别的关节上）" % (bad or "无",))

    t.section("Camera 取帧线程")
    cls, cam, video = realtime_pose.Camera, None, os.path.join(t.tmpdir(), "tiny.avi")
    writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    if not writer.isOpened():
        t.check("跳过：本机 OpenCV 无 MJPG 编码器，无法合成测试视频", True,
                "跳过原因：cv2.VideoWriter(MJPG) 打不开")
    else:
        for i in range(5):
            writer.write(np.full((48, 64, 3), 30 + i * 10, dtype=np.uint8))
        writer.release()
        cam = cls(video)                                    # 文件源：可复现、不依赖硬件
        cam.start()
        time.sleep(0.5)
        cam.stop()                                          # 置位 + join(timeout) + release
        t1 = time.time()
        cam.join(timeout=1.0)                               # 已停的线程必须立刻返回
        dt = time.time() - t1
        t.check("Camera(视频文件) 能实例化；stop() 后线程已退出、join() 立刻返回并释放 VideoCapture",
                (not cam.is_alive()) and dt < 0.5 and not cam.cap.isOpened(),
                "is_alive=%r join 耗时=%.3fs cap.isOpened()=%r" % (cam.is_alive(), dt, cam.cap.isOpened()))
    t.check("Camera 不覆盖 threading.Thread._stop（否则 join() 会报 'Event object is not callable'）",
            "_stop" not in vars(cls) and callable(getattr(cls, "_stop", None))
            and (cam is None or isinstance(cam._stop_event, threading.Event)),
            "类自有属性=%r  '_stop' 仍可调用=%r  实例 _stop_event=%r"
            % (sorted(vars(cls)), callable(getattr(cls, "_stop", None)),
               type(getattr(cam, "_stop_event", None)).__name__))

    t.section("平台后端与摄像头探测")
    be = realtime_pose._backend()
    want = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    t.check("_backend() 按平台选后端：Windows 上应是 cv2.CAP_ANY(%r) 而非 CAP_AVFOUNDATION(%r)，实际=%r"
            % (cv2.CAP_ANY, cv2.CAP_AVFOUNDATION, be), be == want,
            "平台=%r 预期=%r（macOS 才该用 AVFoundation）" % (sys.platform, want))
    cap = cv2.VideoCapture(0, be)
    ok, frame = cap.read() if cap.isOpened() else (False, None)
    cap.release()
    if frame is None:
        t.check("探测设备号 0 的摄像头：打不开/读不出帧 → 记为跳过（不算失败）", True,
                "跳过：本机无可用摄像头（cv2.VideoCapture(0) 打不开），实时取帧无法在本机验证")
    else:
        t.check("设备号 0 的摄像头能读出 3 通道 BGR 画面（read 成功，形状形如 480x640x3）",
                bool(ok) and frame.ndim == 3 and frame.shape[2] == 3,
                "ok=%r shape=%r" % (ok, frame.shape))


if __name__ == "__main__":
    import sys
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
