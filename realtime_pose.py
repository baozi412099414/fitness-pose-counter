#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时姿态捕捉 + 动作计数 + 质量提示  —— 选题 11：健身动作计数与姿态纠正

相对旧版的两处关键改动：
  1. 动作判定不再硬编码，改为从 configs/*.json 读取（pose_logic.load_action），
     新增动作 = 加一份 JSON，不改本文件。
  2. 质量提示：HUD 用英文标签 + macOS 自带 say 语音念中文提示（塌腰/手臂没伸直等）。

运行：
    .venv/bin/python realtime_pose.py --list                    # 列出摄像头
    .venv/bin/python realtime_pose.py --action pushup           # 实时（自动探测）
    .venv/bin/python realtime_pose.py --cam 1 --action pushup   # 指定设备号
    .venv/bin/python realtime_pose.py --src a.mp4 --action pushup  # 读视频调参

按 q 退出，按 r 清零计数。
注意：摄像头相关脚本必须从系统自带「终端.app」跑（见 CLAUDE.md）。
"""

import argparse
import contextlib
import json
import os
import subprocess
import sys
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# 中文叠加：cv2.putText 只认 ASCII，中文会画成「????」，所以用 PIL 渲染成小图再贴。
# Pillow 缺失或字体加载失败时自动降级为「只显示英文 HUD」，不影响主流程。
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except Exception:
    _PIL_OK = False

from pose_logic import load_action, QualityChecker

MODEL_PATH = "pose_landmarker_lite.task"
CONFIG_DIR = "configs"

# 站立基线自动校准用的偏移量（见 main 里的校准逻辑）
LO_DROP = 15.0      # 下蹲门槛 = 站立基线 - 15°（调小更敏感、调大更迟钝）
HI_DROP = 8.0       # 还原线   = 站立基线 - 8°
STRAIGHT_DROP = 10.0  # 「站起伸直」标准 = 站立基线 - 10°

# MediaPipe Pose 33 关键点里常用的几个（画骨架用）
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28

# 画骨架用的连线
SKELETON = [
    (L_SHOULDER, R_SHOULDER), (L_SHOULDER, L_ELBOW), (L_ELBOW, L_WRIST),
    (R_SHOULDER, R_ELBOW), (R_ELBOW, R_WRIST),
    (L_SHOULDER, L_HIP), (R_SHOULDER, R_HIP), (L_HIP, R_HIP),
    (L_HIP, L_KNEE), (L_KNEE, L_ANKLE), (R_HIP, R_KNEE), (R_KNEE, R_ANKLE),
]


# --------------------------------------------------------------------------
# 摄像头：独立线程只保留最新一帧
# --------------------------------------------------------------------------
def _backend():
    """macOS 用 AVFoundation，其它平台交给 OpenCV 自己选。"""
    return cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY


def probe_cameras(max_index=4, wait=8.0):
    """
    挨个试设备号，只认「真的能读出一帧」的那些。

    关键：连续互通相机握手要好几秒。等太短就会「刚连上就被 release 掉」，
    表现为 iPhone 亮一下马上断开、列表里还什么都没有。
    所以对每个设备号最多耐心等 wait 秒。
    （这个坑 CLAUDE.md 里记录过，camera_check.py 早就修了，这里补上。）
    """
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, _backend())
        if cap.isOpened():
            t0 = time.time()
            while time.time() - t0 < wait:
                ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    found.append((i, w, h))
                    break
                time.sleep(0.4)
        cap.release()
    return found


class Camera(threading.Thread):
    """
    实时的关键：取帧放在独立线程里不停 read()，只保留最新一帧。
    主线程推理慢了也没关系——它永远拿到的是「现在」，而不是排队的旧帧。
    """

    def __init__(self, source, width=1280, height=720, fps=30):
        super().__init__(daemon=True)
        self.is_file = not isinstance(source, int)
        if not self.is_file:
            self.cap = cv2.VideoCapture(source, _backend())
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"打不开视频源：{source}")
        self._lock = threading.Lock()
        self._frame = None
        # 不要命名为 _stop：threading.Thread 内部有一个同名方法，join() 在线程
        # 结束时会调用它。用 Event 覆盖后，退出阶段可能报 "Event object is not callable"。
        self._stop_event = threading.Event()
        self._eof_event = threading.Event()
        source_fps = self.cap.get(cv2.CAP_PROP_FPS) if self.is_file else 0
        self._frame_interval = 1.0 / source_fps if source_fps and source_fps > 1 else 0.0

    def run(self):
        while not self._stop_event.is_set():
            ok, f = self.cap.read()
            if not ok:
                if self.is_file:
                    self._eof_event.set()
                    break
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = f          # 覆盖式写入：旧帧直接扔掉
            # 文件按原始帧率播放，避免线程瞬间读到结尾、主线程只拿到最后一帧。
            if self.is_file and self._frame_interval:
                time.sleep(self._frame_interval)

    def read(self):
        with self._lock:
            if self._frame is None:
                return None
            frame = self._frame.copy()
            if self.is_file:
                self._frame = None       # 文件每帧只消费一次；摄像头仍只取最新帧
            return frame

    @property
    def finished(self):
        with self._lock:
            return self.is_file and self._eof_event.is_set() and self._frame is None

    def stop(self):
        self._stop_event.set()
        self.join(timeout=1.0)
        self.cap.release()


class KeypointSource:
    """
    关键点数据源：直接从 JSON 读关键点，**不经过摄像头、也不经过 MediaPipe**。

    目的很明确 —— 让你手上的数据走一遍**和实时识别完全一样的流程**：
    画面 + 骨架 + HUD 计数 + 质量提示 + 语音播报 + 分组间歇 + 训练历史 + JSON 报告，
    一样都不少。区别只是「关键点从哪来」。

    附带好处：不用推理，所以**启动是瞬间的**（不必等 MediaPipe 那约 61 秒）。

    画面：数据里没有图像，所以自己画一张 —— 深色底 + 骨架，
    一眼能看出「这是数据回放，不是真实画面」。
    """

    W, H = 960, 720          # 回放画面的固定尺寸

    def __init__(self, path, speed=1.0):
        from pose_player import DataError, load_data     # 复用同一套数据解析与校验
        self.data = load_data(path)
        self.name = self.data.get("name") or os.path.basename(path)
        self.fps = self.data["fps"]
        self.frames = self.data["frames"]
        self.vis = self.data["vis"]
        self.speed = max(0.1, float(speed))
        self.i = 0
        self._t0 = None
        self._next_at = 0.0

        # 坐标可能不在 0~1 的屏幕范围内（数据来源不同），统一缩放到画面里
        used = [p for fr in self.frames for p in fr if p != (0, 0)]
        if used:
            xs = [p[0] for p in used]
            ys = [p[1] for p in used]
            self._x0, self._x1 = min(xs), max(xs)
            self._y0, self._y1 = min(ys), max(ys)
        else:
            self._x0 = self._y0 = 0
            self._x1 = self._y1 = 1
        span_x = max(1, self._x1 - self._x0)
        span_y = max(1, self._y1 - self._y0)
        pad = 0.12
        self._scale = min(self.W * (1 - 2 * pad) / span_x,
                          self.H * (1 - 2 * pad) / span_y)
        self._off_x = self.W / 2 - (self._x0 + span_x / 2) * self._scale
        self._off_y = self.H / 2 - (self._y0 + span_y / 2) * self._scale

    @property
    def total(self):
        return len(self.frames)

    @property
    def elapsed(self):
        """已回放的数据时间（秒）—— 按 fps 算，不是墙上时间。"""
        return self.i / self.fps

    def _to_screen(self, pts):
        return [(int(x * self._scale + self._off_x), int(y * self._scale + self._off_y))
                for x, y in pts]

    def _render(self, pts, vis, note):
        """画一张回放画面：深色底 + 骨架 + 顶部说明。"""
        import numpy as np
        img = np.full((self.H, self.W, 3), 26, dtype=np.uint8)
        # 淡淡的网格，让画面不至于太空
        for gx in range(0, self.W, 60):
            cv2.line(img, (gx, 0), (gx, self.H), (38, 38, 38), 1)
        for gy in range(0, self.H, 60):
            cv2.line(img, (0, gy), (self.W, gy), (38, 38, 38), 1)

        sp = self._to_screen(pts)
        ok = [i for i in range(33) if tuple(pts[i]) != (0, 0)]
        good = [i for i in ok if vis[i] >= 0.5]
        color = (0, 220, 180) if good else (110, 110, 110)
        for a, b in SKELETON:
            if a in ok and b in ok and vis[a] >= 0.5 and vis[b] >= 0.5:
                cv2.line(img, sp[a], sp[b], color, 3, cv2.LINE_AA)
        for i in ok:
            if vis[i] >= 0.5:
                cv2.circle(img, sp[i], 5, (60, 160, 255), -1, cv2.LINE_AA)
        img = blit_cn(img, note, (14, 14), size=24, color=(255, 226, 150), bg=(48, 42, 18))
        return img

    def read(self):
        """
        取下一帧。返回 (状态, 画面, 关键点, 可见度)，状态 ∈ {"frame", "wait", "eof"}。

        "wait" 的含义是「还没到下一帧的时间」—— 数据回放必须保持真实时间轴，
        否则 enter_hold / min_interval 这些**按秒**的防抖参数会全部失真。
        """
        if self.i >= len(self.frames):
            return "eof", None, None, None
        now = time.time()
        if self._t0 is None:
            self._t0 = now
        if now < self._next_at:
            return "wait", None, None, None

        pts, vis = self.frames[self.i], self.vis[self.i]
        self.i += 1
        # 下一帧的理论时刻（按数据 fps，可整体加速）
        self._next_at = self._t0 + self.i / (self.fps * self.speed)
        note = (f"数据回放 · {self.name} · 第 {self.i}/{self.total} 帧 "
                f"· {self.elapsed:.1f}s")
        return "frame", self._render(pts, vis, note), pts, vis


class ResultBus:
    """LIVE_STREAM 模式下结果从回调里异步回来，这里做个最新值的中转。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.result = None

    def put(self, result, output_image, timestamp_ms):
        with self._lock:
            self.result = result

    def get(self):
        with self._lock:
            return self.result


# --------------------------------------------------------------------------
# 语音播报
# --------------------------------------------------------------------------
def say(text):
    """macOS 自带 say 命令念中文，后台执行不阻塞主循环。非 mac 平台静默跳过。"""
    if sys.platform == "darwin" and text:
        try:
            subprocess.Popen(["say", text])
        except Exception:
            pass


# --------------------------------------------------------------------------
# 中文文字叠加（PIL 渲染一次 → 缓存成小图 → 每帧只做 numpy 贴图）
# --------------------------------------------------------------------------
# 系统自带中文字体，按优先级取第一个存在的
CN_FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
_cn_font_cache = {}      # 字号 -> ImageFont
_cn_img_cache = {}       # (文字, 字号, 颜色, 底色) -> numpy 小图
_CN_CACHE_MAX = 64       # 提示文字组合有限，设上限防止内存膨胀


def _cn_font(size):
    """按字号取字体对象（加载字体有开销，缓存复用）。"""
    if not _PIL_OK:
        return None
    if size not in _cn_font_cache:
        font = None
        for p in CN_FONT_CANDIDATES:
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, size)
                    break
                except Exception:
                    continue
        _cn_font_cache[size] = font
    return _cn_font_cache[size]


def render_cn(text, size=26, color=(255, 255, 255), bg=(0, 0, 0), pad=6):
    """
    把一行中文渲染成一张 BGR numpy 小图，带缓存。

    为什么要缓存：PIL 转整帧再转回来的开销不小，每帧都做会掉帧。
    而提示文案的组合是有限的（几十种），渲染一次存下来，之后只做 numpy 贴图。
    """
    key = (text, size, tuple(color), tuple(bg))
    if key in _cn_img_cache:
        return _cn_img_cache[key]
    font = _cn_font(size)
    if font is None:
        return None
    try:
        probe = Image.new("RGB", (8, 8))
        box = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
        w = max(box[2] - box[0] + pad * 2, 1)
        h = max(box[3] - box[1] + pad * 2, 1)
        img = Image.new("RGB", (w, h), tuple(reversed(bg)))
        ImageDraw.Draw(img).text((pad - box[0], pad - box[1]), text,
                                 font=font, fill=tuple(reversed(color)))
        arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception:
        return None
    if len(_cn_img_cache) >= _CN_CACHE_MAX:
        _cn_img_cache.clear()
    _cn_img_cache[key] = arr
    return arr


def blit_cn(frame, text, org, size=26, color=(255, 255, 255), bg=(0, 0, 0)):
    """把中文小图贴到 frame 上（纯 numpy 赋值，很快）。org = 左上角坐标。"""
    tile = render_cn(text, size, color, bg)
    if tile is None:
        return frame
    fh, fw = frame.shape[:2]
    x, y = max(0, int(org[0])), max(0, int(org[1]))
    if x >= fw or y >= fh:
        return frame
    h = min(tile.shape[0], fh - y)
    w = min(tile.shape[1], fw - x)
    frame[y:y + h, x:x + w] = tile[:h, :w]
    return frame


def start_stdin_watcher(quit_event):
    """
    在后台读**终端**输入：在里面输入 q 并回车（或直接回车）就退出。

    为什么要这个：macOS 上从命令行启动的 OpenCV 窗口经常拿不到键盘焦点，
    按 q 完全没反应 —— 而**终端窗口一定有焦点**（程序就是从这里启动的）。
    所以从 stdin 读命令是最可靠的兜底，而且**不需要任何系统权限**
    （不像全局键盘钩子那样要「输入监控」权限）。

    从 UI 子进程启动时 stdin 是管道，读不到东西会立刻结束，不影响主流程。
    """
    def loop():
        try:
            for line in sys.stdin:
                if line.strip().lower() in ("q", "quit", "exit", ""):
                    quit_event.set()
                    return
        except Exception:
            pass          # 非交互环境（管道 / 已关闭）直接忽略
    threading.Thread(target=loop, daemon=True).start()


def _fmt_num(v, width=5):
    """
    格式化一个可能为 None 的数值。

    **None 和 0 是两回事**：「这一轮没采到极值」（关键点看不清）要显示成 `--`，
    用 0 顶替会让人以为「实测值就是 0」，反而更难排查。
    """
    return " " * (width - 2) + "--" if v is None else f"{v:{width}.2f}"


def bring_window_to_front(verbose=False):
    """
    让识别窗口拿到**键盘焦点**（macOS）。

    从终端启动的 GUI 窗口默认不是「活跃 App」，按键 q / r 会完全没反应。
    这里做三步，**缺一不可**：

      1. 把进程设成「常规 App」（Regular）—— 否则它压根不参与前台竞争。
      2. **激活 App**：macOS 14+ 用 `activate()`；更老的系统才用已废弃的
         `activateIgnoringOtherApps_()`。在 macOS 26 上**只调后者是无效的**。
      3. **把窗口本身设为 key window**（`makeKeyAndOrderFront_`）——
         ⚠ 这一步才是关键：**「激活 App」不等于「窗口拿到键盘」**。
         之前只做了第 1、2 步，所以按 q 一直没反应。

    返回是否至少置前了一个窗口（供调用方决定要不要提示用户手动点一下）。
    """
    if sys.platform != "darwin":
        return False
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
    except Exception as e:
        if verbose:
            print(f"  （没有 pyobjc，无法自动抢焦点：{e}）")
        return False
    try:
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        # 第 2 步：激活 App。这里用**两种** API 各来一次 ——
        # · NSApplication.activate()          macOS 14+ 的正规做法
        # · NSRunningApplication.activate…    从「当前进程」角度激活，覆盖面更广
        # （老的 activateIgnoringOtherApps_ 在 macOS 26 上已废弃且常常无效）
        if hasattr(app, "activate"):
            app.activate()
        else:
            app.activateIgnoringOtherApps_(True)
        try:
            from AppKit import (NSRunningApplication,
                                NSApplicationActivateIgnoringOtherApps)
            NSRunningApplication.currentApplication().activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps)
        except Exception:
            pass

        # 第 3 步：把窗口设为 key window —— 这一步才真正让键盘事件送到窗口上
        count = 0
        for w in app.windows():
            try:
                w.makeKeyAndOrderFront_(None)
                count += 1
            except Exception:
                pass

        # 兜底诊断：NSApp.windows() 拿不到时，用 Quartz 按 PID 查系统级窗口列表，
        # 至少能判断「窗口到底存不存在」——这决定了下一步该往哪个方向修。
        if count == 0:
            try:
                import os as _os
                from Quartz import (CGWindowListCopyWindowInfo,
                                    kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
                infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly,
                                                   kCGNullWindowID)
                mine = [i for i in infos if i.get("kCGWindowOwnerPID") == _os.getpid()]
                if verbose:
                    names = [i.get("kCGWindowName") or "(无标题)" for i in mine]
                    print(f"  NSApp.windows() 为空；按 PID 查到系统级窗口 {len(mine)} 个：{names}")
                count = len(mine)
            except Exception as e:
                if verbose:
                    print(f"  （Quartz 兜底查询也失败：{e}）")

        if verbose:
            print(f"  抢焦点：已激活 App，处理了 {count} 个窗口")
        return count > 0
    except Exception as e:
        if verbose:
            print(f"  （抢焦点失败：{e}）")
        return False


# --------------------------------------------------------------------------
# 主程序
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None, help="摄像头设备号")
    ap.add_argument("--src", type=str, default=None, help="视频文件路径")
    ap.add_argument("--data", type=str, default=None,
                    help="关键点数据文件（JSON）—— 用它代替摄像头/视频，"
                         "走与实时识别完全相同的流程")
    ap.add_argument("--data-speed", type=float, default=1.0,
                    help="数据回放倍速，默认 1.0（按数据里的 fps 实时回放）")
    ap.add_argument("--data-calibrate", action="store_true",
                    help="数据回放时也做角度基线校准（默认不做，用配置里的固定门槛）")
    ap.add_argument("--list", action="store_true", help="列出可用摄像头后退出")
    ap.add_argument("--model", type=str, default=MODEL_PATH)
    ap.add_argument("--no-voice", action="store_true", help="关闭语音播报")
    ap.add_argument("--report", type=str, default=None, help="退出时保存 JSON 测试摘要")
    ap.add_argument("--control-file", type=str, default=None,
                    help="UI 控制文件（支持 reset / stop 命令）")
    ap.add_argument("--action", type=str, default="pushup", help="configs/ 下的动作名（不含 .json）")
    ap.add_argument("--lo-drop", type=float, default=LO_DROP,
                    help="下蹲门槛 = 站立基线 - 该值（默认 15°；调小更敏感、调大更迟钝）")
    # ---- 训练管理（任务书模块 7 训练组与间歇 / 8 历史与目标 / 10 多用户）----
    ap.add_argument("--user", type=str, default=None,
                    help="用户名；数据按 data/users/<用户名>/ 分开存（不传则用「默认用户」）")
    ap.add_argument("--sets", type=int, default=0,
                    help="分几组（0 = 自由训练不分组；设了就会在组间提醒休息）")
    ap.add_argument("--reps-per-set", type=int, default=10, help="每组目标次数")
    ap.add_argument("--rest", type=float, default=30.0, help="组间休息秒数")
    ap.add_argument("--no-history", action="store_true", help="本次不写入训练历史")
    args = ap.parse_args()

    if args.list:
        cams = probe_cameras()
        if not cams:
            print("没找到可用摄像头。若用连续互通相机，先在 Mac 上打开一次"
                  "「照片亭」把 iPhone 摄像头唤醒，再运行本程序。")
        for i, w, h in cams:
            print(f"  设备号 {i}: {w}x{h}")
        return

    # 加载动作配置（新增动作 = 加一份 JSON，不改代码）
    cfg_path = os.path.join(CONFIG_DIR, f"{args.action}.json")
    if not os.path.exists(cfg_path):
        print(f"找不到动作配置：{cfg_path}")
        print(f"{CONFIG_DIR}/ 下现有：")
        for f in sorted(os.listdir(CONFIG_DIR)):
            print(f"  {f}")
        return
    action = load_action(cfg_path)
    print(f"动作：{action.name}（{action.id}），信号类型 {action.signal_type}")

    # ---- 训练管理：用户档案 + 分组间歇 + 历史 + 目标（任务书模块 7/8/10）----
    # 纯逻辑 + JSON 存储，不依赖摄像头，所以能独立自动化测试（见 test_training_manager.py）
    from training_manager import SetManager, UserStore, History, Goals
    store = UserStore()
    user = store.switch_user(args.user) if args.user else store.current_user()
    # 报告里的「数据来源」要能一眼看出这次跑的是什么
    src_label = (os.path.basename(args.data) if args.data
                 else (args.src if args.src else str(source)))
    history = History(store, user)
    goals = Goals(store, user)
    setman = SetManager(args.sets, args.reps_per_set, args.rest) if args.sets > 0 else None

    goal = goals.get_goal(args.action)
    done_today = history.today_reps(args.action)
    line = f"  用户：{user}"
    if goal:
        line += f"　今日目标 {goal} 次（已完成 {done_today}，还差 {max(0, goal - done_today)}）"
    elif done_today:
        line += f"　今日已完成 {done_today} 次"
    print(line)
    if setman is not None:
        print(f"  分组：{setman.total_sets} 组 × {setman.reps_per_set} 次，"
              f"组间休息 {int(args.rest)} 秒")

    # 选输入源：关键点数据 > 视频文件 > 摄像头
    data_source = None
    if args.data:
        try:
            data_source = KeypointSource(args.data, speed=args.data_speed)
        except Exception as e:
            print(f"读取数据文件失败：{e}")
            return
        source = None
        print(f"  输入源：关键点数据文件 {os.path.basename(args.data)}")
        print(f"  数据名称：{data_source.name}")
        print(f"  数据规模：{data_source.total} 帧 / {data_source.fps:g}fps / "
              f"{data_source.total / data_source.fps:.1f} 秒")
        if data_source.speed != 1.0:
            print(f"  ⚠ 回放倍速 {data_source.speed:g}× —— 注意：防抖参数（enter_hold / "
                  f"min_interval）是按**秒**算的，")
            print("    加速回放会让两次动作在时间轴上挤得太近，计数可能少于实时。"
                  "要复核真实计数请用默认倍速 1.0。")
    elif args.src:
        source = args.src
    elif args.cam is not None:
        source = args.cam
    else:
        cams = probe_cameras()
        if not cams:
            print("没找到可用摄像头，试试 --list 或 --cam 0/1/2")
            return
        source = cams[0][0]
        print(f"自动选用设备号 {source}（{cams[0][1]}x{cams[0][2]}）"
              f"，不对就用 --cam 手动指定")

    bus = ResultBus()
    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.LIVE_STREAM,   # 异步，不阻塞取帧
        num_poses=1,
        # 调高一点，减少「跟丢后还在输出幽灵骨架」的情况（另一道防线是 visibility 过滤）
        min_pose_detection_confidence=0.6,
        min_pose_presence_confidence=0.6,
        min_tracking_confidence=0.6,
        result_callback=bus.put,
    )

    fps_hist, t_prev = [], time.time()
    cam = None
    if data_source is None:
        cam = Camera(source)
        cam.start()
        time.sleep(0.4)                 # 等第一帧

    # WINDOW_NORMAL 让窗口可拖拽缩放，也更容易拿到键盘焦点（默认 AUTOSIZE 会锁死尺寸）
    cv2.namedWindow("realtime pose", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("realtime pose", 960, 540)

    last_say = 0.0                      # 语音节流：同一提示 2 秒内不重复念
    last_count = 0                      # 上次计数，用于「刚数上一个」时语音报数
    got_first = False                   # 是否已出过画面（用来抢窗口焦点）
    # macOS 上命令行启动的 OpenCV 窗口**默认拿不到键盘焦点**，q / r 就没反应。
    # 只「抢一次」不够：那一下如果恰好被别的窗口（比如测试控制台）抢走，
    # 之后就再没机会了。所以改成：出画面后几秒内多试几次，直到用户真的按下过键。
    got_first_key = False               # 用户按下过任意键（说明焦点已经在画面上）
    focus_try_until = 0.0               # 在这个时刻之前持续尝试抢前台
    last_focus_try = 0.0
    # 启动后头 2 秒画面还在稳定（相机自动曝光、人还在站位），这期间 MediaPipe
    # 容易输出乱跳的关键点，会造成「凭空多计一次」→ 所以先不计数。
    warmup_until = time.time() + 2.0
    warmup_samples = []                 # 启动头 2 秒的信号采样（用来估算站立基线）
    baseline = None                     # 站立基线（自动校准结果）
    calib_done = False                  # 校准是否已判定完（成功或放弃）
    calibration_announced = False       # 「校准完成」只提示一次，不要一直挂在画面上
    quit_event = threading.Event()      # 终端里输入 q 回车 → 置位退出（不依赖窗口焦点）
    start_stdin_watcher(quit_event)
    shown_hits = []                     # 最近命中的错误（保持显示一会儿，免得只闪一帧看不清）
    shown_until = 0.0
    last_err_say = 0.0                  # 错误播报节流（独立于报数）
    last_cnt_say = 0.0                  # 报数节流
    last_logged_count = 0               # 上次打印过判定明细的计数（终端诊断用）
    no_person_frames = 0                # 连续多少帧没看到人（用来压醒目提示）
    person_frames = 0                   # **可信地**看到人的帧数（比 detected_frames 严格）
    total_frames = 0                    # UI/离线验收摘要
    detected_frames = 0
    error_counts = {}
    active_error_names = set()
    stopped_reason = "user"
    last_control_seq = None

    # MediaPipe 启动时可能尝试联网上报遥测，网络不通时会等一会儿才继续（见 CLAUDE.md）。
    # 这里提前说明，免得用户以为程序卡死了。
    # 数据回放时**跳过 MediaPipe 初始化** —— 关键点已经在数据里，不需要推理。
    # 顺带省掉那约 61 秒的遥测等待，回放几乎是瞬间启动的。
    if data_source is not None:
        print("数据回放模式：关键点直接来自数据文件，不经过摄像头与姿态模型。")
        print("  除了「点从哪来」，后面的流程与实时识别完全一致 ——")
        print("  画面骨架 / HUD 计数 / 质量提示 / 语音播报 / 分组间歇 / 报告，一样都不少。")
        model_ctx = contextlib.nullcontext(None)
    else:
        print("正在初始化姿态模型 …（首次启动可能要等十几秒到一分钟，请稍候）")
        model_ctx = vision.PoseLandmarker.create_from_options(options)
    t_init = time.time()
    with model_ctx as landmarker:
        print(f"  模型就绪，初始化用时 {time.time() - t_init:.0f} 秒\n")
        t0 = time.time()
        while True:
            # UI 与识别进程用一个很小的 JSON 文件通信。这样不依赖窗口焦点，
            # “清零/停止/重启”在 OpenCV 窗口没有获得键盘焦点时仍然有效。
            if args.control_file and os.path.exists(args.control_file):
                try:
                    with open(args.control_file, encoding="utf-8") as f:
                        control = json.load(f)
                    seq = control.get("seq")
                    if seq != last_control_seq:
                        last_control_seq = seq
                        command = control.get("command")
                        if command == "stop":
                            stopped_reason = "ui_stop"
                            print("\nUI 请求停止，正在生成测试摘要。", flush=True)
                            break
                        if command == "reset":
                            action.reset()
                            last_count = 0
                            last_logged_count = 0
                            shown_hits = []
                            shown_until = 0.0
                            total_frames = 0
                            detected_frames = 0
                            person_frames = 0
                            no_person_frames = 0
                            error_counts.clear()
                            active_error_names.clear()
                            print("\n已清零：次数、动作阶段和错误统计全部重置。", flush=True)
                except (OSError, ValueError, TypeError):
                    pass  # UI 正在替换文件的极短窗口，下一帧会重试

            # ---- 取帧：两条来源，后面完全共用同一套流程 ----
            # ① 关键点数据回放：点已经在数据里了，跳过摄像头与推理
            # ② 摄像头 / 视频：走原来的 MediaPipe 推理
            sig_txt = "--"
            count, stage, sig, hits, checks = 0, "ready", None, [], []
            conf = 0.0                      # 计数关键点的最低可信度
            person_ok = False               # 可信度够不够（不够就暂停计数）
            pts = None

            if data_source is not None:
                st, frame, pts, vis = data_source.read()
                if st == "eof":
                    stopped_reason = "eof"
                    print(f"\n数据回放完成（{data_source.total} 帧 / "
                          f"{data_source.elapsed:.1f} 秒），自动结束测试。")
                    break
                if st == "wait":
                    # 还没到下一帧的时刻 —— 保持真实时间轴（防抖参数按秒算）
                    if quit_event.is_set():
                        stopped_reason = "user"
                        break
                    if cv2.waitKey(4) & 0xFF == ord("q"):
                        stopped_reason = "user"
                        break
                    continue
                # person_ok / conf 在下面 if pts is not None 里统一算 ——
                # 数据回放也走同一套可信度判断，所以 visibility=0 的数据同样会被当作「没人」
                total_frames += 1
            else:
                frame = cam.read()
                if frame is None:
                    if cam.finished:
                        stopped_reason = "eof"
                        print("\n视频播放完成，自动结束测试。")
                        break
                    if cv2.waitKey(10) & 0xFF == ord("q"):
                        break
                    continue

                total_frames += 1
                frame = cv2.flip(frame, 1)          # 镜像，自己看着顺手
                h, w = frame.shape[:2]

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                landmarker.detect_async(mp_img, int((time.time() - t0) * 1000))

                res = bus.get()
                if res and res.pose_landmarks:
                    lm = res.pose_landmarks[0]
                    pts = [(int(p.x * w), int(p.y * h)) for p in lm]
                    # 关键点可信度：人没拍到 / 跟丢时 MediaPipe 会输出「幽灵骨架」，
                    # 计数和质量判定都必须先看这个，否则会凭空加数、凭空报警
                    vis = [p.visibility for p in lm]

            h, w = frame.shape[:2]
            if pts is not None:
                detected_frames += 1
                counter_idxs = set()
                for condition in (action.conditions or [{"points": action.signal_points}]):
                    counter_idxs.update(condition["points"])
                conf = min(vis[i] for i in counter_idxs)
                person_ok = conf >= action.min_visibility
                # detected_frames 只表示「模型吐了关键点」，但模型在看不到人时也会吐
                # 「幽灵骨架」（低可信度）。真正有意义的是「可信地看到人」的帧数，
                # 否则「画面里根本没人」会被算成检出率 100%，把问题掩盖掉。
                if person_ok:
                    person_frames += 1

                # ---- 站立基线自动校准 ----
                # 启动头 2 秒你应该是站着的，用这段时间信号的中位数当「站立基线」，
                # 再自动定门槛：下蹲门槛 = 基线-25°，还原线 = 基线-8°，
                # 「站起伸直」标准 = 基线-10°。换个人 / 换机位都不必回来改配置。
                # 注意：只对「角度类」动作有效；距离类（如开合跳的脚距/肩宽比值）
                # 单位不是度，用不了这套减法，所以直接跳过、用配置里的固定阈值。
                # 注意：自动校准的公式是「基线 − 偏移」，只适合「角度变小」的动作（如深蹲下蹲）。
                # 开合跳是「角度变大」（举手），套这个公式会把门槛设到站立值以下 ——
                # 站着就满足「手举起」，手机一晃就计数。所以配置里可以关掉校准。
                if not calib_done and person_ok:
                    # 数据回放时**默认不做基线校准**：校准假设「启动头 2 秒用户是站着的」，
                    # 但一段录好的数据未必从站立开始；倍速回放时那 2 秒还会覆盖整段数据，
                    # 采出来的基线完全是错的（实测采到 130°，把门槛带偏成 115°）。
                    # 何况配置里的阈值本来就是针对这段数据调的 —— 固定门槛才可预测。
                    if data_source is not None and not args.data_calibrate:
                        calib_done = True
                        print("  （数据回放：使用配置里的固定门槛，不做角度基线校准）")
                    elif not getattr(action, "calibrate", True) or action.signal_type != "angle":
                        calib_done = True
                        print(f"  （{action.name} 用配置里的固定门槛，不做角度基线校准）")
                    elif time.time() < warmup_until:
                        sample = action.signal(pts)
                        if sample is not None:
                            warmup_samples.append(sample)
                    elif len(warmup_samples) >= 8:
                        warmup_samples.sort()
                        baseline = warmup_samples[len(warmup_samples) // 2]
                        action.counter.lo = baseline - args.lo_drop
                        action.counter.hi = baseline - HI_DROP
                        for r in action.quality.rules:
                            # 只校准「用计数信号」的约束；带自己 signal 的约束
                            # （如开合跳的「腿没张开」用的是距离比值）不能被角度基线污染
                            if r.get("check") == "peak_min" and "signal" not in r:
                                r["min"] = baseline - STRAIGHT_DROP
                        calib_done = True
                        print(f"  自动校准：站立基线 {baseline:.0f}° → 下蹲门槛 "
                              f"{action.counter.lo:.0f}° / 还原线 {action.counter.hi:.0f}° / "
                              f"站直标准 {baseline - STRAIGHT_DROP:.0f}°")
                    elif time.time() > warmup_until + 4.0:
                        calib_done = True       # 采样太少（一直没拍全），放弃校准
                        print("  （站立基线采样不足，改用配置里的固定门槛）")

                # 骨架照画（可信度低时画成灰色，一眼看出「这是猜的」）
                skel_color = (0, 220, 180) if person_ok else (110, 110, 110)
                for a, b in SKELETON:
                    cv2.line(frame, pts[a], pts[b], skel_color, 2)
                for p in pts:
                    cv2.circle(frame, p, 3, (255, 255, 255), -1)

                # 配置驱动的判定：算信号 → 状态机计数 → 质量明细
                # ⚠ 数据回放**不做启动预热**：那 2 秒是给「摄像头自动曝光、用户走进
                # 画面」留的稳定期，数据里没有这些过程。而且预热按**墙上时间**算，
                # 会把数据开头的几秒整段吃掉 —— 实测一段 6 秒的数据被吃掉 2 秒，
                # 3 次动作只数出 2 次。
                if data_source is not None or time.time() >= warmup_until:
                    # ⚠ 数据回放必须用**数据时间**（elapsed），不能用墙上时间：
                    # 主循环一旦慢于数据帧率（画骨架 + 中文 HUD 都不便宜），节流器就会
                    # 连续「追帧」，而墙上时间几乎没推进 —— 于是 min_interval 这类
                    # 按秒的防抖判定全部失真，实测把 3 次动作数成了 2 次。
                    # 用数据时间还有个好处：同一份数据**结果完全可复现**，
                    # 和 pose_player.py 跑出来的结论一致。
                    _now = data_source.elapsed if data_source is not None else None
                    count, stage, sig, hits, checks = action.update(pts, vis, now=_now)
                else:
                    # 稳定期内只算信号拿来显示，不动状态机（避免凭空多计一次）
                    sig = action.signal(pts)
                    count, stage = action.counter.count, action.counter.stage
                if sig is not None:
                    sig_txt = f"{sig:5.1f}"

            # 帧率
            now = time.time()
            fps_hist.append(1.0 / max(now - t_prev, 1e-6))
            t_prev = now
            if len(fps_hist) > 30:
                fps_hist.pop(0)
            fps = sum(fps_hist) / len(fps_hist)

            # HUD（OpenCV 画不了中文，用英文；中文交给 say 语音念）
            cv2.rectangle(frame, (0, 0), (400, 152), (32, 32, 32), -1)
            cv2.putText(frame, f"REPS {count}", (12, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
            cv2.putText(frame, f"{action.id.upper():9s} {stage.upper():6s} sig {sig_txt}", (12, 68),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 220), 1)
            # 检测状态：可信度不够时明确写「PAUSED」，而不是默默加数
            det_txt = f"track {conf:.2f}  " + ("COUNTING" if person_ok else "PAUSED no-person")
            # 连续很多帧都看不到人 → 在画面正中压一条醒目提示。
            # 「计数一直是 0」最容易被当成程序坏了，其实多半是人没在画面里。
            if person_ok:
                no_person_frames = 0
            else:
                no_person_frames = no_person_frames + 1
            if no_person_frames >= 45:          # 约 1.5 秒
                frame = blit_cn(frame, "没检测到人 —— 请让全身进入画面",
                                (max(12, w // 2 - 260), h // 2 - 24), size=34,
                                color=(255, 255, 255), bg=(180, 40, 40))
                frame = blit_cn(frame, "需要退到 2.5~3 米外，注意光线别太暗",
                                (max(12, w // 2 - 230), h // 2 + 26), size=24,
                                color=(255, 226, 150), bg=(70, 30, 30))
            det_color = (120, 230, 120) if person_ok else (60, 60, 255)
            cv2.putText(frame, det_txt, (12, 92),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, det_color, 2)
            # 信息行：多条件动作显示各条件当前值；角度类动作显示站立基线 + 本轮最低点
            if action.conditions:
                # 注意：某帧关键点异常时信号会被丢弃成 None，这里必须处理，
                # 否则 f"{None:5.2f}" 会抛 TypeError，把整个主循环搞崩（画面「卡住」）
                vals = "  ".join("  -- " if v is None else f"{v:5.2f}"
                                 for v in action.last_values)
                info_txt = f"cond  {vals}"
            else:
                base_txt = f"{baseline:.0f}" if baseline else "calib.."
                low_txt = f"{action.depth_valley:.0f}" if action.depth_valley is not None else "--"
                info_txt = f"base {base_txt}  lowest {low_txt}"
            cv2.putText(frame, info_txt, (12, 116),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 120), 2)
            cv2.putText(frame, f"{fps:4.1f} fps", (12, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)

            # 先把「刚命中、要保持显示」的错误算出来：
            # on_rep 类约束只在计数那一帧命中，只闪一帧根本看不清 → 让结果挂 2 秒
            if hits:
                shown_hits = hits
                shown_until = now + 2.0
            elif now > shown_until:
                shown_hits = []
            current_error_names = {h["name"] for h in hits}
            for name in current_error_names - active_error_names:
                error_counts[name] = error_counts.get(name, 0) + 1
            active_error_names = current_error_names
            hit_map = {h["name"]: h for h in shown_hits}

            # 质量明细：显示「实测值 / 阈值」，一眼看出是照不全还是阈值太严
            #   OK 绿=达标   !! 红=不达标   ? 灰=点没拍全   -- 灰=本阶段不判
            y = 180
            hidden = False
            for c in checks:
                kept = hit_map.get(c["name"])
                if kept is not None:
                    # 刚命中、正在保持显示的错误（数值取命中那一刻的）
                    txt = (f"{c['name'].upper():18s} "
                           f"{_fmt_num(kept.get('value'))}/{_fmt_num(kept.get('limit'))}  !!")
                    color = (60, 60, 255)
                elif not c["visible"]:
                    hidden = True
                    txt = f"{c['name'].upper():18s}    ?   point hidden"
                    color = (150, 150, 150)
                elif not c["checked"]:
                    txt = f"{c['name'].upper():18s}   --   not this phase"
                    color = (150, 150, 150)
                elif c["ok"]:
                    txt = (f"{c['name'].upper():18s} "
                           f"{_fmt_num(c['value'])}/{_fmt_num(c['limit'])}  OK")
                    color = (120, 230, 120)
                else:
                    txt = (f"{c['name'].upper():18s} "
                           f"{_fmt_num(c['value'])}/{_fmt_num(c['limit'])}  !!")
                    color = (60, 60, 255)
                cv2.putText(frame, txt, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                y += 26

            if hidden:
                cv2.putText(frame, "! POINTS HIDDEN  ->  step back, keep whole body in frame",
                            (12, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 200, 255), 2)

            if shown_hits:
                banner = "   ".join("! " + (h["name"] or "?").upper() for h in shown_hits)
                cv2.putText(frame, banner, (12, y + 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 255), 3)

            # ---- 中文叠加：画面底部显示「动作 · 阶段 · 次数」和变形提示 ----
            # （cv2.putText 画不了中文，改用 PIL 渲染 + 缓存贴图）
            fh = frame.shape[0]
            stage_cn = {"ready": "准备", "active": "动作中"}.get(stage, stage)
            score_txt = ""
            if action.last_score is not None:
                score_txt = f" · {action.last_score:.0f} 分（{QualityChecker.grade(action.last_score)}）"
            frame = blit_cn(frame, f"{action.name} · {stage_cn} · {count} 次{score_txt}",
                            (12, fh - 100), size=26,
                            color=(190, 255, 210), bg=(24, 30, 26))

            # ---- 校准提示（很重要，之前只在终端打印，画面上看不到）----
            # 站立基线要靠**启动后的头 2 秒**采样，那段时间你必须站直别动。
            # 如果那时正在调机位或走进画面，基线就采错了 → 门槛被设到达不到的位置
            # → 表现就是「怎么做都不计数」。所以在画面上明确提示。
            if not calib_done:
                if person_ok:
                    left = max(0.0, warmup_until - time.time())
                    hint = (f"请站直别动 · 正在校准基线 {left:.1f} 秒"
                            if left > 0 else "正在校准基线…请站直别动")
                else:
                    hint = "请站到画面里 · 需要全身入镜才能校准"
                frame = blit_cn(frame, hint, (12, 74), size=28,
                                color=(30, 30, 30), bg=(255, 214, 102))
            elif baseline is not None and not calibration_announced:
                calibration_announced = True
                frame = blit_cn(frame, f"基线校准完成：站立 {baseline:.0f}°",
                                (12, 74), size=26,
                                color=(20, 40, 20), bg=(150, 230, 160))

            if shown_hits:
                # 只显示最高优先级的 1~2 条，避免文字太长铺满画面
                tips = "；".join(h["tip"] for h in shown_hits[:2])
                frame = blit_cn(frame, "⚠ " + tips, (12, fh - 54), size=30,
                                color=(255, 90, 90), bg=(64, 18, 18))

            # 循环进度：cycles_per_rep > 1 的动作（如「左右各一次才算一组」）
            # 要让用户知道「还差几个循环」，否则会以为程序没数上。
            if action.counter.cycles_per_rep > 1:
                done = action.counter.cycle_progress
                total = action.counter.cycles_per_rep
                frame = blit_cn(frame, f"本轮循环 {done}/{total}", (12, fh - 146), size=24,
                                color=(255, 226, 150), bg=(48, 42, 18))

            # 训练组进度（模块 7）：第几组 / 本组几次 / 休息倒计时
            if setman is not None:
                st = setman.status(now)
                if st["rest_remaining"] > 0:
                    grp = f"休息 {st['rest_remaining']:.0f} 秒 → 准备第 {st['current_set']} 组"
                elif st["finished"]:
                    grp = f"全部完成 · 共 {st['total_reps']} 次"
                else:
                    grp = (f"第 {st['current_set']}/{st['total_sets']} 组 · "
                           f"{st['reps_in_set']}/{st['reps_per_set']} 次")
                frame = blit_cn(frame, grp, (12, fh - 146), size=26,
                                color=(255, 235, 160), bg=(36, 32, 18))

            # 终端也打印每次计数的判定明细 —— HUD 看不清时可以直接把输出复制回来
            if count > last_logged_count:
                last_logged_count = count
                parts = [f"{c['name']}={_fmt_num(c['value'])}/{_fmt_num(c['limit'])}"
                         f"{'OK' if c['ok'] else '!!'}"
                         for c in checks if c.get("limit") is not None]
                print(f"  第 {count} 次： " + "   ".join(parts), flush=True)

            # ---- 训练组与间歇（模块 7）：组完成 / 休息结束 / 全部完成 ----
            if setman is not None:
                for ev in setman.on_rep(count, now):
                    print(f"  [训练] {ev['tip']}", flush=True)
                    if not args.no_voice:
                        say(ev["tip"])

            # 语音播报：报错优先。同一次动作既计数又报错时合并成一句
            # （两个 say 会互相打断）；报错与报数各有独立节流，避免错误提示被报数挤掉。
            if not args.no_voice and hits and now - last_err_say >= 1.5:
                tip = hits[0]["tip"]
                if count > last_count:
                    tip += f"，{count}"
                    last_count = count
                say(tip)
                last_err_say = now
            elif not args.no_voice and count > last_count and now - last_cnt_say >= 1.0:
                # 没有错误提示时才单独念数字（做动作时不用盯屏幕也知道数上了）
                say(str(count))
                last_cnt_say = now
                last_count = count

            # ---- 右上角：退出方式提示 ----
            # macOS 上命令行启动的 OpenCV 窗口默认没有键盘焦点，按 q 会「没反应」。
            # 用户不知道「点一下画面就好了」，所以直接把这句话写在画面上。
            # 一旦收到过任意按键，就说明焦点已经在窗口上，提示 15 秒后自动撤掉。
            if (not got_first_key) or (time.time() - t0 < 15.0):
                # 8 秒还没收到任何按键 → 说明键盘焦点多半没抢到，提示要更醒目
                # 8 秒还没收到任何按键 → 键盘焦点多半没抢到，这时给出**两条路**：
                # 点窗口（恢复窗口按键），或在终端里输入 q 回车（一定有效）
                stuck = (not got_first_key) and (time.time() - t0 > 8.0)
                lines = (["KEYBOARD NOT ACTIVE — type q + Enter in the terminal to quit"]
                         if stuck else
                         ["q / ESC = quit  (or type q + Enter in the terminal)",
                          "click the window if keys do nothing"])
                color = (60, 60, 255) if stuck else (235, 235, 235)
                for i, txt in enumerate(lines):
                    scale = 0.55 if i == 0 else 0.45
                    (tw, _th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
                    cv2.putText(frame, txt, (w - tw - 14, 26 + i * 22),
                                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1,
                                cv2.LINE_AA)

            cv2.imshow("realtime pose", frame)
            if not got_first:
                got_first = True
                cv2.waitKey(1)              # 先让窗口把第一帧画出来，再抢焦点
                ok = bring_window_to_front(verbose=True)
                if not ok:
                    print("  ⚠ 没能自动抢到键盘焦点 —— 请用鼠标点一下识别画面，"
                          "之后 q / r 就能用了。")
                focus_try_until = time.time() + 8.0
                last_focus_try = time.time()
            elif not got_first_key and time.time() < focus_try_until:
                # 还没收到过任何按键 → 焦点多半不在画面上，每隔 1.5 秒再拉一次
                if time.time() - last_focus_try >= 1.5:
                    last_focus_try = time.time()
                    bring_window_to_front()

            # 直接点窗口的 ✕ 关掉也要能退出（最符合直觉的方式）
            try:
                if cv2.getWindowProperty("realtime pose", cv2.WND_PROP_VISIBLE) < 1:
                    print("\n窗口已关闭，退出。")
                    break
            except cv2.error:
                break

            # 终端里输入 q 回车也能退出（不依赖窗口焦点，是最可靠的兜底）
            if quit_event.is_set():
                stopped_reason = "user"
                print("\n收到终端退出命令，结束测试。")
                break

            # q / ESC 退出，r 清零
            k = cv2.waitKey(1) & 0xFF
            if k != 255:                     # 255 表示这一轮没有按键
                got_first_key = True
            if k in (ord("q"), 27):
                stopped_reason = "user"
                print("\n收到退出键，结束测试。")
                break
            if k == ord("r"):
                action.reset()
                last_count = 0
                print("  已清零（计数与本轮判定状态）")

    if cam is not None:
        cam.stop()
    cv2.destroyAllWindows()
    summary = {
        "action": action.id,
        "action_name": action.name,
        "source": src_label,
        "reps": action.counter.count,
        "total_frames": total_frames,
        "detected_frames": detected_frames,
        "detection_rate": round(detected_frames / total_frames, 4) if total_frames else 0.0,
        # 可信地看到人的比例 —— 判断「画面里到底有没有人」要看这个。
        # detection_rate 只表示「模型吐了关键点」，人不在画面里时模型照样会吐
        # 「幽灵骨架」，检出率反而显示 100%，把真正的问题掩盖掉。
        "person_frames": person_frames,
        "person_rate": round(person_frames / total_frames, 4) if total_frames else 0.0,
        "errors": error_counts,
        "error_tips": {r.get("name"): r.get("tip", r.get("name"))
                       for r in action.quality.rules if r.get("name") in error_counts},
        "stopped_reason": stopped_reason,
        # 动作评分：最近一次动作完成时的 0~100 分
        "score": action.last_score,
        "grade": QualityChecker.grade(action.last_score),
    }
    # ---- 写入训练历史 + 结算今日目标（任务书模块 8）----
    # 跑离线视频属于「调参」而不是「训练」，所以那种情况默认不记进个人历史
    if not args.no_history and not args.src:
        try:
            history.add_session(
                action=action.id, reps=action.counter.count,
                sets=setman.total_sets if setman else None,
                errors=error_counts,
                duration_sec=time.time() - t0,
                source=str(source),
                score=action.last_score,
            )
            gp = goals.progress(action.id, history)
            summary["user"] = user
            summary["goal"] = gp
            if gp["target"]:
                mark = "已达成" if gp["reached"] else f"还差 {gp['remaining']} 次"
                print(f"  今日目标：{gp['done']}/{gp['target']}　{mark}")
            if action.last_score is not None:
                print(f"  动作评分：{action.last_score:.0f} 分"
                      f"（{QualityChecker.grade(action.last_score)}）")
            print(f"  已写入训练历史（用户：{user}）")
        except Exception as e:
            print(f"  （写训练历史失败，不影响本次结果：{e}）")

    print("测试摘要：" + json.dumps(summary, ensure_ascii=False), flush=True)
    if args.report:
        report_dir = os.path.dirname(os.path.abspath(args.report))
        os.makedirs(report_dir, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 窗口没抢到焦点时 q 按不动，终端里 Ctrl+C 随时能退，不依赖窗口焦点
        print("\n收到 Ctrl+C，退出。")
