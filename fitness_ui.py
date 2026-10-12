#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个动作的简易测试控制台。

识别画面沿用 realtime_pose.py 的 OpenCV 窗口；本窗口负责选择动作/输入、
启动与停止、显示日志和读取测试摘要。将姿态模型放在独立子进程里，即使底层
MediaPipe/Metal 初始化失败，控制台本身也不会一起崩溃。
"""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

# matplotlib 的字体缓存目录要指到可写位置（默认的 ~/.matplotlib 在这台机器上不可写，
# 会导致每次启动都重建缓存 + 刷警告）。必须在 import matplotlib 之前设置。
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib_cache"))

# 趋势图内嵌用的 matplotlib 画布。这里**只 import Figure + TkAgg 画布**，
# 不调用 pyplot 的 matplotlib.use() —— 否则会和 plot_trend.py 设的 Agg 后端打架。
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_TK_OK = True
except Exception:
    _MPL_TK_OK = False


ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "configs"
REFERENCE_DIR = ROOT / "captures/reference"
REFERENCE_EXTS = (".ogv", ".webm", ".mp4", ".mov", ".ogg", ".avi", ".mkv")
SOURCE_TYPES = ("摄像头", "选择本地视频", "内置参考视频")
PHONE_CAMERA_INDEX = 1
COMPUTER_CAMERA_INDEX = 0


# ══════════════════════════════════════════════════════════════════
# 视觉主题：配色 / 字体 / 卡片 / 悬停按钮
# ══════════════════════════════════════════════════════════════════
# 目标：让这个调试台看起来像「一个正经的小程序」，而不是脚本堆出来的对话框。
#
# tkinter 没有圆角和阴影，所以靠**配色层次 + 留白 + 字体层级**来营造现代感：
#   · 页面底色浅灰，功能区用纯白「卡片」浮在上面
#   · 卡片之间留足间距 —— 比画边框更能区分区块，也更干净
#   · 标题 / 说明 / 数值三种字号，一眼看出主次
BG         = "#eef1f5"      # 页面底色
CARD       = "#ffffff"      # 卡片底色
SOFT       = "#f7f9fb"      # 输入框等「凹下去」的区域
BORDER     = "#dfe4ea"      # 分隔线
TEXT       = "#1f2933"      # 主文字
MUTED      = "#7b8794"      # 次要说明文字
PRIMARY    = "#2f80ed"      # 主色（开始 / 强调）
PRIMARY_HI = "#5a9bf5"
SUCCESS    = "#27ae60"
SUCCESS_HI = "#3fc97a"
DANGER     = "#eb5757"
DANGER_HI  = "#f57b7b"
WARN       = "#f2c94c"
WARN_HI    = "#ffdd77"
GREY       = "#a8b2bd"      # 禁用态

F_TITLE = ("Helvetica", 22, "bold")
F_H2    = ("Helvetica", 14, "bold")
F_BODY  = ("Helvetica", 12)
F_SMALL = ("Helvetica", 11)
F_TINY  = ("Helvetica", 10)
F_NUM   = ("Helvetica", 26, "bold")
F_BTN   = ("Helvetica", 13, "bold")


def setup_style(root):
    """统一 ttk 控件外观。ttk 默认主题（macOS 的 aqua）不允许改背景色，
    所以切到 clam —— 它是「可换肤」的经典主题，能配合我们的配色。"""
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=CARD, foreground=TEXT, font=F_BODY)
    st.configure("TFrame", background=CARD)
    st.configure("Page.TFrame", background=BG)
    st.configure("TLabel", background=CARD, foreground=TEXT, font=F_BODY)
    st.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=F_SMALL)
    st.configure("H2.TLabel", background=CARD, foreground=TEXT, font=F_H2)
    st.configure("Tiny.TLabel", background=CARD, foreground=MUTED, font=F_TINY)
    st.configure("TCheckbutton", background=CARD, foreground=TEXT, font=F_BODY)
    st.configure("TRadiobutton", background=CARD, foreground=TEXT, font=F_BODY)
    for name in ("TEntry", "TSpinbox", "TCombobox"):
        st.configure(name, fieldbackground=SOFT, background=SOFT,
                     bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                     foreground=TEXT, arrowcolor=MUTED, padding=5)
    st.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 6, 0, 0))
    st.configure("TNotebook.Tab", padding=(20, 9), font=F_BODY,
                 background="#dce3ea", foreground=MUTED, borderwidth=0)
    st.map("TNotebook.Tab",
           background=[("selected", CARD)], foreground=[("selected", PRIMARY)])
    st.configure("Trend.Horizontal.TProgressbar", troughcolor="#e7ecf2",
                 background=PRIMARY, borderwidth=0, thickness=12)
    return st


def card(parent, title=None, subtitle=None, pady=(0, 12)):
    """
    造一块「卡片」：白底 + 内边距，可选标题与说明。

    返回的是**内容区**（一个干净的 Frame），调用方在里面随便用 grid 或 pack。

    ⚠ 标题放在**独立子容器**里，不和内容区共用父容器 —— 因为 tkinter 规定
    「同一个容器不能混用 pack 和 grid」。早期版本把标题 pack 在返回的容器上，
    调用方一 grid 就报 `cannot use geometry manager grid ... already has slaves
    managed by pack`。

    **刻意不画边框** —— 现代界面靠留白和底色区分区块，加边框反而显得笨重
    （tkinter 也画不出圆角，硬加方框会更土）。
    """
    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="x", pady=pady)
    box = tk.Frame(outer, bg=CARD)
    box.pack(fill="x")
    pad = tk.Frame(box, bg=CARD, padx=18, pady=15)
    pad.pack(fill="x")
    if title or subtitle:
        head = tk.Frame(pad, bg=CARD)
        head.pack(fill="x", pady=(0, 12))
        if title:
            tk.Label(head, text=title, bg=CARD, fg=TEXT, font=F_H2).pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, bg=CARD, fg=MUTED, font=F_SMALL).pack(
                anchor="w", pady=(3, 0))
    body = tk.Frame(pad, bg=CARD)
    body.pack(fill="x")
    return body


def hover_btn(parent, text, command, bg=PRIMARY, hi=None, fg="white", **kw):
    """
    扁平 + 悬停变色的按钮。

    tkinter 默认按钮带立体边框（像 90 年代的对话框），这里全部压平，
    再用 <Enter>/<Leave> 做悬停反馈 —— 这是「像小程序」最明显的一步。
    """
    hi = hi or bg
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hi, activeforeground=fg,
                    disabledforeground="#f0f0f0",
                    relief="flat", bd=0, highlightthickness=0,
                    font=F_BTN, cursor="pointinghand", padx=18, pady=9, **kw)

    def _enter(_e=None):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=hi)

    def _leave(_e=None):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=bg)

    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", _leave)
    return btn


def set_btn_enabled(btn, enabled, base):
    """统一处理按钮启用/禁用（顺带把颜色切到灰，一眼看出能不能点）。"""
    btn.configure(state="normal" if enabled else "disabled",
                  bg=base if enabled else GREY, cursor="pointinghand" if enabled else "arrow")


def discover_actions(config_dir=None):
    """
    扫描 configs/*.json，返回 [(显示名, 动作id), ...]。

    这是「配置驱动」闭环的最后一环：**新增动作只要往 configs/ 丢一份 JSON**，
    界面会自动多出一个动作按钮，不需要改这里的代码。
    单个配置损坏时跳过它，而不是让整个界面起不来。
    """
    config_dir = Path(config_dir or CONFIG_DIR)
    out = []
    for p in sorted(config_dir.glob("*.json")):
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  （跳过无法解析的配置 {p.name}：{e}）")
            continue
        out.append((cfg.get("name") or p.stem, cfg.get("id") or p.stem))
    return out


def find_reference_video(action_id, ref_dir=None):
    """按动作 id 找内置参考视频 <id>_standard.*；找不到返回 None。"""
    ref_dir = Path(ref_dir or REFERENCE_DIR)
    for ext in REFERENCE_EXTS:
        p = ref_dir / f"{action_id}_standard{ext}"
        if p.is_file():
            return p
    return None


def build_command(action_id, source_type, source_value, voice, report_path,
                  control_path=None, user=None, sets=0, reps_per_set=10, rest=30.0):
    """生成参数列表；单独保留为纯函数，便于无 GUI 自动测试。"""
    cmd = [sys.executable, "-u", str(ROOT / "realtime_pose.py"),
           "--action", str(action_id), "--report", str(report_path)]
    if source_type == "摄像头":
        cmd += ["--cam", str(int(source_value))]
    else:
        cmd += ["--src", str(source_value)]
    if not voice:
        cmd.append("--no-voice")
    if control_path:
        cmd += ["--control-file", str(control_path)]
    # 训练管理（任务书模块 7 训练组 / 8 历史与目标 / 10 多用户）
    if user:
        cmd += ["--user", str(user)]
    if sets and int(sets) > 0:
        cmd += ["--sets", str(int(sets)),
                "--reps-per-set", str(int(reps_per_set)),
                "--rest", str(float(rest))]
    return cmd


def write_control_command(control_path, command):
    """原子写入 UI 命令，避免识别进程读到半份 JSON。"""
    control_path = Path(control_path)
    payload = {"seq": time.time_ns(), "command": command}
    tmp_path = control_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(control_path)


class FitnessTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("健身动作识别测试台")
        # 窗口尺寸按屏幕自适应：高度取屏幕的 86%（上限 1060），
        # 而不是写死 —— 写死的话高屏浪费、矮屏放不下最下面的趋势图。
        # 应用视觉主题（必须早于任何控件创建，否则先建的控件拿不到新样式）
        self.root.configure(bg=BG)
        setup_style(self.root)

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        win_w, win_h = 900, min(1060, max(620, int(sh * 0.86)))
        self.root.geometry(f"{win_w}x{win_h}+{max(0, (sw - win_w) // 2)}+{max(0, (sh - win_h) // 3)}")
        self.root.minsize(700, 480)
        # 启动瞬间短暂置顶，让用户注意到控制台在哪。
        # ⚠ **绝不能一直 topmost**：macOS 上 topmost 窗口永远压在所有普通窗口之上，
        #   摄像头画面、消息框、文件对话框都会被它挡住，用户根本点不到 ——
        #   这正是「点击提示出现在 UI 后面、摄像头画面也上不来」的根因。
        self._flash_topmost()
        self._last_wheel = 0.0          # 滚轮节流用
        self._scrollregion_pending = False
        self.process = None
        self.report_path = None
        self.control_path = None
        self.messages = queue.Queue()
        self.restart_pending = False

        # 动作列表来自 configs/ 目录扫描：新增动作 = 丢一份 JSON，界面自动多一个按钮
        self.actions = discover_actions()
        if not self.actions:
            raise RuntimeError(f"configs/ 下没有可用的动作配置：{CONFIG_DIR}")
        default_action = ("深蹲" if any(n == "深蹲" for n, _ in self.actions)
                          else self.actions[0][0])
        self.action_var = tk.StringVar(value=default_action)
        # 日常使用默认直接开摄像头；参考视频只是调试时的可选输入。
        self.source_type_var = tk.StringVar(value="摄像头")
        self.file_var = tk.StringVar()
        # 本项目已实测 iPhone 连续互通相机为设备 1、Mac 内置摄像头为设备 0。
        self.camera_var = tk.StringVar(value=str(PHONE_CAMERA_INDEX))
        self.custom_camera_var = tk.StringVar(value="2")
        self.voice_var = tk.BooleanVar(value=True)
        # ---- 训练管理（模块 7/8/10）----
        from training_manager import UserStore
        self.store = UserStore()
        self.user_var = tk.StringVar(value=self.store.current_user())
        self.group_on_var = tk.BooleanVar(value=False)
        self.sets_var = tk.StringVar(value="3")
        self.reps_per_set_var = tk.StringVar(value="10")
        self.rest_var = tk.StringVar(value="30")
        self.goal_var = tk.StringVar(value="0")
        self.goal_status_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="未设目标")
        self.top_errors_var = tk.StringVar(value="暂无训练记录")
        self._report_paths = []          # 报告列表当前显示的路径（与 Listbox 行一一对应）
        self.status_var = tk.StringVar(value="准备就绪")
        self.reps_var = tk.StringVar(value="0")
        self.score_var = tk.StringVar(value="—")
        self.rate_var = tk.StringVar(value="--")
        self.errors_var = tk.StringVar(value="暂无")

        # macOS 上「非活动窗口的第一次点击只激活窗口、不传给按钮」，
        # 而识别子进程启动会抢走焦点 → 表现就是「按钮不灵敏、要点两次」。
        # 解决：鼠标只要在控制台里移动，就把键盘焦点抢回来（每秒最多一次）。
        self._last_focus_grab = 0.0
        # ⚠ 这里**只绑 <Enter>，不绑 <Motion>**。
        # <Motion> 会在鼠标每移动一点时触发一次 Python 回调，快速划过时可达数百 Hz，
        # tkinter 的 Python 回调开销大 —— 实测会让整个界面滚动起来发卡。
        # <Enter> 只在鼠标进入窗口边界时触发一次，足够解决「第一次点击只激活窗口」的问题。
        self.root.bind("<Enter>", self._maybe_grab_focus, add="+")

        self._build()
        self._sync_source()
        self._sync_goal()
        self._refresh_stats()
        self._draw_trend()
        self.root.after(100, self._poll_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        # ---- 可滚动容器 ----
        # 界面内容比较长（测试设置 + 训练管理 + 按钮 + 结果 + 三个标签页），
        # 矮一点的屏幕上最下面的趋势图会被挤出可视区。这里给整个内容区加垂直滚动条。
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(shell, highlightthickness=0, bg=BG)
        vbar = ttk.Scrollbar(shell, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        outer = tk.Frame(self.canvas, bg=BG, padx=22, pady=18)
        self._canvas_win = self.canvas.create_window((0, 0), window=outer, anchor="nw")

        # 内容变高 → 更新可滚动范围；画布变宽 → 让内容跟着变宽（否则底部会出现横向滚动条）
        outer.bind("<Configure>", self._on_outer_configure)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self._canvas_win, width=e.width))
        self.canvas.configure(yscrollincrement=18)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_wheel_linux)

        # ══════════ 顶部标题 ══════════
        head = tk.Frame(outer, bg=BG)
        head.pack(fill="x", pady=(0, 16))
        tk.Label(head, text="健身动作识别测试台", bg=BG, fg=TEXT,
                 font=F_TITLE).pack(anchor="w")
        tk.Label(head, text="选好动作直接开始即可 —— 默认使用摄像头，内置参考视频仅用于调试。",
                 bg=BG, fg=MUTED, font=F_SMALL).pack(anchor="w", pady=(3, 0))

        # ══════════ 卡片 1：测试设置 ══════════
        form = card(outer, "测试设置", "动作的判定逻辑全部来自 configs/ 下的配置文件")
        form.columnconfigure(1, weight=1)

        tk.Label(form, text="动作", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 14), pady=(10, 0))
        action_frame = tk.Frame(form, bg=CARD)
        action_frame.grid(row=0, column=1, sticky="ew", pady=(10, 0))
        for col, (name, _aid) in enumerate(self.actions):
            action_frame.columnconfigure(col, weight=1, uniform="act")
            # indicatoron=False：把单选按钮画成「药丸按钮」，比小圆点更像 App。
            # 选中态用浅蓝底 —— tkinter 没法在选中时同时改字色，浅底黑字最稳妥。
            tk.Radiobutton(
                action_frame, text=name, variable=self.action_var, value=name,
                command=self._sync_source, indicatoron=False,
                bg=SOFT, fg=TEXT, selectcolor="#d6e8ff",
                activebackground="#d6e8ff", activeforeground=TEXT,
                font=F_BTN, relief="flat", bd=0, highlightthickness=0,
                padx=16, pady=10, cursor="pointinghand",
            ).grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))

        tk.Label(form, text="输入", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=1, column=0, sticky="w", padx=(0, 14), pady=(12, 0))
        source_frame = tk.Frame(form, bg=CARD)
        source_frame.grid(row=1, column=1, sticky="w", pady=(12, 0))
        for col, name in enumerate(SOURCE_TYPES):
            tk.Radiobutton(
                source_frame, text=name, variable=self.source_type_var, value=name,
                command=self._sync_source, bg=CARD, fg=TEXT, selectcolor=SOFT,
                activebackground=CARD, activeforeground=TEXT,
                font=F_BODY, relief="flat", bd=0, highlightthickness=0,
                cursor="pointinghand",
            ).grid(row=0, column=col, sticky="w", padx=(0, 18))

        tk.Label(form, text="视频/设备", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=2, column=0, sticky="w", padx=(0, 14), pady=(10, 0))
        self.file_entry = ttk.Entry(form, textvariable=self.file_var)
        self.file_entry.grid(row=2, column=1, sticky="ew", pady=(10, 0))
        self.browse_btn = ttk.Button(form, text="选择视频…", command=self._browse)
        self.browse_btn.grid(row=2, column=2, padx=(8, 0), pady=(10, 0))
        self.camera_frame = tk.Frame(form, bg=CARD)
        self.camera_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(10, 0))
        for text, val, pad in ((f"手机摄像头（设备 {PHONE_CAMERA_INDEX}，默认）", str(PHONE_CAMERA_INDEX), (0, 0)),
                               (f"电脑摄像头（设备 {COMPUTER_CAMERA_INDEX}）", str(COMPUTER_CAMERA_INDEX), (18, 0)),
                               ("其他编号", "custom", (18, 6))):
            tk.Radiobutton(self.camera_frame, text=text, variable=self.camera_var,
                           value=val, bg=CARD, fg=TEXT, selectcolor=SOFT,
                           activebackground=CARD, activeforeground=TEXT, font=F_BODY,
                           relief="flat", bd=0, highlightthickness=0,
                           cursor="pointinghand").pack(side="left", padx=pad)
        self.camera_box = ttk.Spinbox(self.camera_frame, from_=0, to=9, width=4,
                                      textvariable=self.custom_camera_var)
        self.camera_box.pack(side="left")

        ttk.Checkbutton(form, text="开启中文语音提醒和报数",
                        variable=self.voice_var).grid(row=3, column=1, sticky="w",
                                                      pady=(12, 0))

        # ══════════ 卡片 2：训练管理（模块 7 / 8 / 10）══════════
        train = card(outer, "训练管理", "多用户档案 · 分组间歇 · 每日目标 · 训练历史")
        train.columnconfigure(1, weight=1)

        tk.Label(train, text="用户", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 14), pady=(10, 0))
        self.user_box = ttk.Combobox(train, textvariable=self.user_var,
                                     values=self.store.list_users(), width=14)
        self.user_box.grid(row=0, column=1, sticky="w", pady=(10, 0))
        tk.Button(train, text="切换", command=self._switch_user, bg=SOFT, fg=TEXT,
                  activebackground="#e4eaf1", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="pointinghand").grid(
            row=0, column=2, sticky="w", padx=6, pady=(10, 0))
        tk.Button(train, text="新建用户…", command=self._new_user, bg=SOFT, fg=TEXT,
                  activebackground="#e4eaf1", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="pointinghand").grid(
            row=0, column=3, sticky="w", pady=(10, 0))
        tk.Button(train, text="删除用户…", command=self._delete_user, bg=SOFT, fg=DANGER,
                  activebackground="#ffe3e3", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="pointinghand").grid(
            row=0, column=4, sticky="w", padx=(6, 0), pady=(10, 0))
        tk.Label(train, textvariable=self.goal_status_var, bg=CARD, fg=PRIMARY,
                 font=F_SMALL).grid(row=0, column=5, sticky="w", padx=14, pady=(10, 0))

        tk.Label(train, text="分组", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=1, column=0, sticky="w", padx=(0, 14), pady=(12, 0))
        gframe = tk.Frame(train, bg=CARD)
        gframe.grid(row=1, column=1, columnspan=5, sticky="w", pady=(12, 0))
        ttk.Checkbutton(gframe, text="启用分组间歇", variable=self.group_on_var).pack(side="left")
        ttk.Spinbox(gframe, from_=1, to=20, width=4,
                    textvariable=self.sets_var).pack(side="left", padx=(12, 3))
        tk.Label(gframe, text="组 ×", bg=CARD, fg=TEXT).pack(side="left")
        ttk.Spinbox(gframe, from_=1, to=100, width=4,
                    textvariable=self.reps_per_set_var).pack(side="left", padx=(6, 3))
        tk.Label(gframe, text="次，组间休息", bg=CARD, fg=TEXT).pack(side="left")
        ttk.Spinbox(gframe, from_=0, to=600, width=5,
                    textvariable=self.rest_var).pack(side="left", padx=(6, 3))
        tk.Label(gframe, text="秒", bg=CARD, fg=TEXT).pack(side="left")

        tk.Label(train, text="每日目标", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=2, column=0, sticky="w", padx=(0, 14), pady=(12, 0))
        tframe = tk.Frame(train, bg=CARD)
        tframe.grid(row=2, column=1, columnspan=5, sticky="w", pady=(12, 0))
        ttk.Spinbox(tframe, from_=0, to=999, width=5,
                    textvariable=self.goal_var).pack(side="left")
        tk.Label(tframe, text="次", bg=CARD, fg=TEXT).pack(side="left", padx=(5, 12))
        tk.Button(tframe, text="保存目标", command=self._save_goal, bg=SOFT, fg=TEXT,
                  activebackground="#e4eaf1", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="pointinghand").pack(side="left")
        tk.Button(tframe, text="查看趋势图", command=self._show_trend, bg=SOFT, fg=PRIMARY,
                  activebackground="#e4eaf1", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="pointinghand").pack(
            side="left", padx=10)

        # ══════════ 主操作按钮 ══════════
        buttons = tk.Frame(outer, bg=BG)
        buttons.pack(fill="x", pady=(2, 14))
        self.start_btn = hover_btn(buttons, "▶  开始测试", self.start, PRIMARY, PRIMARY_HI)
        self.start_btn.pack(side="left")
        self.stop_btn = hover_btn(buttons, "■  停止", self.stop, DANGER, DANGER_HI)
        self.stop_btn.pack(side="left", padx=8)
        self.reset_btn = hover_btn(buttons, "↺  清零", self.reset, WARN, WARN_HI, fg="#3a2f00")
        self.reset_btn.pack(side="left", padx=8)
        self.restart_btn = hover_btn(buttons, "⟳  重新启动", self.restart, SUCCESS, SUCCESS_HI)
        self.restart_btn.pack(side="left", padx=8)
        for b, base in ((self.stop_btn, DANGER), (self.reset_btn, WARN),
                        (self.restart_btn, SUCCESS)):
            set_btn_enabled(b, False, base)
        tk.Label(buttons, textvariable=self.status_var, bg=BG, fg=MUTED,
                 font=F_SMALL).pack(side="right")

        # 鼠标点不到时仍有确定的操作入口：F5 开始、F6 停止、F7 清零、F8 重启。
        self.root.bind("<F5>", lambda _e: self.start())
        self.root.bind("<F6>", lambda _e: self.stop())
        self.root.bind("<F7>", lambda _e: self.reset())
        self.root.bind("<F8>", lambda _e: self.restart())
        self.root.bind("<Escape>", lambda _e: self.stop())

        # ══════════ 卡片 3：最近一次结果 ══════════
        res = card(outer, "最近一次测试结果")
        for col in range(4):
            res.columnconfigure(col, weight=1, uniform="res")
        for col, (label, var, color, font) in enumerate((
                ("次数", self.reps_var, TEXT, F_NUM),
                ("动作评分", self.score_var, "#b5651d", F_NUM),
                ("关键点检出率", self.rate_var, PRIMARY, ("Helvetica", 20, "bold")),
                ("错误事件", self.errors_var, DANGER, F_SMALL))):
            tk.Label(res, text=label, bg=CARD, fg=MUTED, font=F_SMALL).grid(
                row=0, column=col)
            tk.Label(res, textvariable=var, bg=CARD, fg=color, font=font,
                     wraplength=230, justify="center").grid(row=1, column=col, pady=(8, 2))

        # ══════════ 下方标签页：趋势图 / 历史统计 / 运行日志 ══════════
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="x")

        trend_tab = tk.Frame(notebook, bg=CARD, padx=10, pady=8)
        notebook.add(trend_tab, text="  训练趋势图  ")
        self.trend_note = tk.Label(trend_tab, text="", bg=CARD, fg=MUTED, font=F_SMALL)
        self.trend_note.pack(anchor="w", pady=(0, 4))
        if _MPL_TK_OK:
            self.trend_fig = Figure(figsize=(12.6, 3.3), dpi=92)
            self.trend_canvas = FigureCanvasTkAgg(self.trend_fig, master=trend_tab)
            # 固定高度（在可滚动容器里不能用 expand，否则高度会塌成一条线）；
            # 330px 刚好容得下三条子图的标题、刻度和图例。
            self.trend_canvas.get_tk_widget().configure(height=330)
            self.trend_canvas.get_tk_widget().pack(fill="x")
        else:
            self.trend_fig = None
            self.trend_canvas = None
            tk.Label(trend_tab, fg=DANGER, bg=CARD, font=F_BODY,
                     text="本机没有可用的 matplotlib Tk 后端，趋势图无法内嵌；\n"
                          "仍可用「查看趋势图」按钮另存为图片。").pack(pady=24)

        # ══════════ 标签页 2：历史与统计（全部只读本地文件，不需要摄像头）══════════
        stats = tk.Frame(notebook, bg=CARD, padx=14, pady=12)
        notebook.add(stats, text="  历史与统计  ")
        stats.columnconfigure(1, weight=1)

        tk.Label(stats, text="目标进度", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        self.goal_bar = ttk.Progressbar(stats, orient="horizontal", length=240,
                                        mode="determinate", maximum=100,
                                        style="Trend.Horizontal.TProgressbar")
        self.goal_bar.grid(row=0, column=1, sticky="w")
        tk.Label(stats, textvariable=self.progress_var, bg=CARD, fg=PRIMARY,
                 font=F_BODY).grid(row=0, column=2, sticky="w", padx=12)

        tk.Label(stats, text="最常犯的错", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=1, column=0, sticky="nw", pady=(12, 0))
        tk.Label(stats, textvariable=self.top_errors_var, bg=CARD, fg=DANGER,
                 font=F_BODY, wraplength=460, justify="left").grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(12, 0))

        tk.Label(stats, text="历史报告", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=2, column=0, sticky="nw", pady=(12, 0))
        list_frame = tk.Frame(stats, bg=CARD)
        list_frame.grid(row=2, column=1, sticky="ew", pady=(12, 0))
        self.report_list = tk.Listbox(
            list_frame, height=5, activestyle="none", font=("Menlo", 11),
            bg=SOFT, fg=TEXT, selectbackground="#d6e8ff", selectforeground=TEXT,
            relief="flat", bd=0, highlightthickness=0)
        self.report_list.pack(side="left", fill="x", expand=True)
        rscroll = ttk.Scrollbar(list_frame, orient="vertical",
                                command=self.report_list.yview)
        self.report_list.configure(yscrollcommand=rscroll.set)
        rscroll.pack(side="right", fill="y")
        rbtns = tk.Frame(stats, bg=CARD)
        rbtns.grid(row=2, column=2, sticky="nw", padx=12, pady=(12, 0))
        for label, cmd in (("刷新", self._refresh_stats),
                           ("查看详情", self._show_report_detail),
                           ("打开目录", self._open_reports_dir),
                           ("校验配置", self._validate_configs)):
            tk.Button(rbtns, text=label, command=cmd, bg=SOFT, fg=TEXT,
                      activebackground="#e4eaf1", font=F_SMALL, relief="flat", bd=0,
                      highlightthickness=0, padx=14, pady=5, width=9,
                      cursor="pointinghand").pack(pady=3)

        # ══════════ 标签页 3：运行日志（深色控制台，和浅色界面形成对比）══════════
        log_box = tk.Frame(notebook, bg=CARD, padx=10, pady=10)
        notebook.add(log_box, text="  运行日志  ")
        self.log = tk.Text(log_box, height=14, wrap="word", state="disabled",
                           background="#1c2128", foreground="#d7dde5",
                           insertbackground="white", relief="flat", bd=0,
                           highlightthickness=0, font=("Menlo", 11),
                           padx=12, pady=10)
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _msg(self, kind, title, message, **kw):
        """
        统一弹窗入口：总是带上 `parent=self.root`。

        macOS 上**不指定 parent 的消息框会跑到主窗口后面**，用户看到的现象是
        「点了按钮什么都没发生」。包一层可以保证以后新增的弹窗也不会漏掉 parent。
        `kind` 取 showinfo / showwarning / showerror / askyesno。
        """
        kw.setdefault("parent", self.root)
        return getattr(messagebox, kind)(title, message, **kw)

    # ---------------- 滚动 ----------------
    def _on_outer_configure(self, _event=None):
        """
        内容尺寸变化 → 更新可滚动范围。

        用 after_idle 合并连续事件：`bbox("all")` 相对慢，而布局过程中
        <Configure> 会被触发很多次，每次都算一遍会明显拖慢启动和重排。
        """
        if self._scrollregion_pending:
            return
        self._scrollregion_pending = True
        self.root.after_idle(self._update_scrollregion)

    def _update_scrollregion(self):
        self._scrollregion_pending = False
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_wheel(self, event):
        """
        鼠标滚轮滚动主内容区。

        两处优化（鼠标滚轮在触控板上会以很高的频率触发，逐个处理会卡）：
          · **节流**：16ms 内只响应一次（约 60fps 上限）
          · **放大步长**：一次滚 3 个单位，事件数直接降到 1/3
        只取 delta 的符号，规避各平台量纲差异。
        """
        now = time.time()
        if now - self._last_wheel < 0.016:
            return
        self._last_wheel = now
        try:
            self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        except tk.TclError:
            pass

    def _on_wheel_linux(self, event):
        """Linux 上滚轮是 Button-4 / Button-5。"""
        now = time.time()
        if now - self._last_wheel < 0.016:
            return
        self._last_wheel = now
        try:
            self.canvas.yview_scroll(-3 if event.num == 4 else 3, "units")
        except tk.TclError:
            pass

    def _scroll_to_log(self):
        """把视图滚到底部（看运行日志 / 校验结果时方便）。"""
        try:
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
        except tk.TclError:
            pass

    # ---------------- 内嵌趋势图 ----------------
    def _draw_trend(self):
        """
        把趋势图画到内嵌画布上。

        绘图逻辑直接复用 `plot_trend.build_axes()` —— 命令行脚本和界面上看到的是
        同一套代码画出来的，不会出现「改了脚本忘了界面」的不一致。
        """
        if not _MPL_TK_OK or self.trend_canvas is None:
            return
        from plot_trend import build_axes          # 顺便完成中文字体设置
        from training_manager import Goals, History

        user = self.store.current_user()
        hist = History(self.store, user)
        self.trend_fig.clear()
        axes = self.trend_fig.subplots(1, 3)

        if not hist.all_sessions():
            axes[0].text(0.5, 0.5, f"用户「{user}」还没有训练记录\n"
                                   f"用摄像头或参考视频跑一次就有了",
                         ha="center", va="center", fontsize=13, color="#888")
            axes[0].axis("off")
            for a in axes[1:]:
                a.axis("off")
            self.trend_note.config(text=f"当前用户：{user}　（暂无数据）")
        else:
            top = build_axes(self.trend_fig, axes, hist, Goals(self.store, user),
                             action=self.action_id())
            self.trend_note.config(
                text=f"当前用户：{user}　动作：{self.action_var.get()}　"
                     f"最常犯的错：{top}　（切换用户/动作会自动重画）")
        self.trend_fig.tight_layout(rect=(0, 0, 1, 0.93))
        self.trend_canvas.draw()

    # ---------------- 历史与统计（不依赖摄像头）----------------
    def _error_tip_map(self):
        """把「约束名 → 中文提示」收集起来，用于把英文错误名显示成中文。"""
        from pose_logic import load_action
        tips = {}
        for _name, aid in self.actions:
            try:
                act = load_action(CONFIG_DIR / f"{aid}.json")
                for rule in act.quality.rules:
                    tips[rule.get("name")] = rule.get("tip", rule.get("name"))
            except Exception:
                continue
        return tips

    def _refresh_stats(self):
        """刷新目标进度、最常犯的错、历史报告列表。全部只读本地 JSON。"""
        from training_manager import Goals, History
        user = self.store.current_user()
        aid = self.action_id()
        hist = History(self.store, user)

        # ① 今日目标进度
        prog = Goals(self.store, user).progress(aid, hist)
        if prog["target"]:
            self.goal_bar["value"] = prog["ratio"] * 100
            mark = "已达成 ✅" if prog["reached"] else f"还差 {prog['remaining']} 次"
            self.progress_var.set(f"{prog['done']}/{prog['target']} 次　{mark}")
        else:
            self.goal_bar["value"] = 0
            self.progress_var.set("未设目标")

        # ② 最常犯的错（按所有动作汇总，中文提示）
        errs = hist.error_summary()
        if errs:
            tips = self._error_tip_map()
            top = "、".join(f"{tips.get(k, k)} ×{v}" for k, v in list(errs.items())[:3])
            self.top_errors_var.set(top)
        else:
            self.top_errors_var.set("暂无训练记录（用视频或摄像头跑一次就有了）")

        # ③ 历史报告列表
        report_dir = ROOT / "captures/reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        found = sorted(report_dir.glob("*.json"), reverse=True)
        self._report_paths = [p for p in found if not p.name.startswith("control-")]
        self.report_list.delete(0, "end")
        shown = 0
        for p in self._report_paths:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "reps" not in d:            # 控制文件之类的跳过
                continue
            label = (f"{str(d.get('action_name') or d.get('action'))[:5]:　<5} "
                     f"{d.get('reps', 0):>3} 次　"
                     f"检出 {d.get('detection_rate', 0) * 100:>5.1f}%　{p.name[6:21]}")
            self.report_list.insert("end", label)
            shown += 1
            if shown >= 60:
                break

    def _show_report_detail(self):
        """把选中的报告读出来，用人能看懂的方式展示。"""
        sel = self.report_list.curselection()
        if not sel:
            self._msg("showinfo", "未选择", "先在列表里点一条历史报告。")
            return
        idx = sel[0]
        if idx >= len(self._report_paths):
            return
        p = self._report_paths[idx]
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            self._msg("showerror", "读取失败", f"{p.name}\n{e}")
            return
        lines = [
            f"文件　　{d.get('action_name')}（{d.get('action')}）　{p.name}",
            f"来源　　{d.get('source')}",
            f"次数　　{d.get('reps')}",
            f"帧数　　{d.get('total_frames')} 帧，检出关键点 "
            f"{d.get('detected_frames')} 帧（{d.get('detection_rate', 0) * 100:.1f}%）",
            f"结束　　{d.get('stopped_reason')}",
        ]
        if d.get("user"):
            lines.append(f"用户　　{d['user']}")
        if d.get("goal"):
            g = d["goal"]
            lines.append(f"目标　　{g.get('done')}/{g.get('target')}"
                         f"（{'已达成' if g.get('reached') else '未达成'}）")
        errs = d.get("errors") or {}
        if errs:
            tips = d.get("error_tips") or {}
            lines.append("")
            lines.append("错误事件：")
            for k, v in sorted(errs.items(), key=lambda kv: -kv[1]):
                lines.append(f"　　{tips.get(k, k)}　{v} 次")
        self._msg("showinfo", "报告详情", "\n".join(lines))

    def _validate_configs(self):
        """
        校验 configs/ 下所有动作配置，结果显示在日志区。

        这是「自定义动作」的第一道防线：写错关键点编号、阈值方向、check 名字
        这类问题在运行前就能发现，不用架好摄像头做完动作才发现不生效。
        """
        from validate_config import validate_file
        files = sorted(CONFIG_DIR.glob("*.json"))
        if not files:
            self._msg("showwarning", "没有配置", f"{CONFIG_DIR} 下没有 json 文件")
            return
        self._append_log("\n===== 动作配置校验 =====\n")
        total_err = total_warn = 0
        for p in files:
            rep = validate_file(p)
            total_err += len(rep.errors)
            total_warn += len(rep.warns)
            self._append_log(f"[{'通过' if rep.ok else '有问题'}] {p.name}\n")
            for e in rep.errors:
                self._append_log(f"    错误  {e}\n")
            for w in rep.warns:
                self._append_log(f"    警告  {w}\n")
        summary = f"共 {len(files)} 个配置，错误 {total_err} 条、警告 {total_warn} 条"
        self._append_log(summary + "\n")
        self.status_var.set(summary)
        if total_err:
            self._msg("showwarning", "配置有问题", summary + "\n详情见下方运行日志。")

    def _open_reports_dir(self):
        """在访达里打开报告目录。"""
        path = ROOT / "captures/reports"
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            elif sys.platform.startswith("win"):
                os.startfile(str(path))          # noqa: S606 (Windows only)
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._msg("showerror", "打开失败", str(e))

    # ---------------- 窗口焦点（解决 macOS 点击不灵敏）----------------
    def _flash_topmost(self, ms=900):
        """短暂置顶约 0.9 秒后自动取消：能提醒用户，又不会挡住其它窗口。"""
        try:
            self.root.attributes("-topmost", True)
            self.root.after(ms, lambda: self.root.attributes("-topmost", False))
        except tk.TclError:
            pass

    def _grab_focus(self):
        """
        把**键盘**焦点抢回控制台。

        ⚠ 这里**不调用 lift()**。lift 会把控制台抬到摄像头画面、消息框之上，
        用户就看不到识别窗口了。只抢键盘焦点不会改变窗口层级。
        """
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def _maybe_grab_focus(self, _event=None):
        """
        鼠标在控制台里活动时把键盘焦点抢回来。

        节流 3 秒，而且**只在本窗口确实没有键盘焦点时才抢** ——
        否则会不停和识别画面抢焦点，导致 q / r 按键在画面窗口里失灵。
        """
        # 识别运行期间一律不抢 —— 用户这时候要看识别画面做动作，
        # 控制台去抢焦点只会让两个窗口来回跳。
        if self.process is not None and self.process.poll() is None:
            return
        now = time.time()
        if now - self._last_focus_grab < 3.0:
            return
        self._last_focus_grab = now
        try:
            if self.root.focus_displayof() is None:
                self._grab_focus()
        except tk.TclError:
            pass

    # ---------------- 训练管理（模块 7/8/10）----------------
    def _refresh_users(self):
        self.user_box["values"] = self.store.list_users()

    def _switch_user(self):
        name = (self.user_var.get() or "").strip()
        if not name:
            return
        self.store.switch_user(name)
        self._refresh_users()
        self._sync_goal()
        self.status_var.set(f"已切换到用户「{name}」")

    def _new_user(self):
        name = simpledialog.askstring("新建用户", "输入用户名：", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        self.store.switch_user(name)
        self.user_var.set(name)
        self._refresh_users()
        self._sync_goal()
        self.status_var.set(f"已创建并切换到用户「{name}」")

    def _delete_user(self):
        """删除用户及其全部训练数据（二次确认，且不允许删掉最后一个用户）。"""
        name = (self.user_var.get() or "").strip()
        if not name:
            self._msg("showwarning", "未选择用户", "请先在下拉框里选择要删除的用户。")
            return
        if not self._msg("askyesno", "确认删除",
                         f"确定要删除用户「{name}」吗？\n\n"
                         f"该用户的档案、训练历史和目标都会被一起删除，且无法恢复。"):
            return
        ok, msg = self.store.delete_user(name)
        if not ok:
            self._msg("showwarning", "无法删除", msg)
            return
        # 删完切到当前仍然有效的用户（可能已经不是原来那个了）
        current = self.store.current_user()
        self.user_var.set(current)
        self._refresh_users()
        self._sync_goal()
        self.status_var.set(msg + f"，当前用户：{current}")

    def _sync_goal(self):
        """把「当前用户 + 当前动作」的今日目标与完成量显示出来。"""
        from training_manager import Goals, History
        user = self.store.current_user()
        action_id = self.action_id()
        goal = Goals(self.store, user).get_goal(action_id)
        done = History(self.store, user).today_reps(action_id)
        self.goal_var.set(str(goal))
        self.goal_status_var.set(
            f"今日已完成 {done} 次" + (f" / 目标 {goal}" if goal else "（未设目标）"))
        if hasattr(self, "report_list"):
            self._refresh_stats()       # 换用户/换动作后，进度条和报告列表一起刷新
            self._draw_trend()          # 趋势图也跟着重画

    def _save_goal(self):
        from training_manager import Goals
        try:
            value = int(float(self.goal_var.get() or 0))
        except ValueError:
            self._msg("showerror", "目标无效", "每日目标要填整数次数")
            return
        Goals(self.store, self.store.current_user()).set_goal(self.action_id(), value)
        self._sync_goal()
        self.status_var.set(f"已保存目标：每天 {value} 次")

    def _show_trend(self):
        """生成并弹出趋势图（调用 plot_trend.py）。"""
        from training_manager import History
        user = self.store.current_user()
        if not History(self.store, user).all_sessions():
            self._msg("showinfo", "暂无数据",
                                f"用户「{user}」还没有训练记录。\n先做一次训练再来看趋势。")
            return
        out = ROOT / "captures" / f"trend_{user}.png"
        try:
            subprocess.Popen([sys.executable, str(ROOT / "plot_trend.py"),
                              "--user", user, "--out", str(out)],
                             cwd=str(ROOT))
            self._append_log(f"$ 生成趋势图 -> {out}\n")
            self.status_var.set("正在生成趋势图…")
        except Exception as e:
            self._msg("showerror", "生成失败", str(e))

    def action_id(self):
        """当前选中动作的 id（对应 configs/<id>.json）。"""
        want = self.action_var.get()
        for name, aid in self.actions:
            if name == want:
                return aid
        return self.actions[0][1] if self.actions else "pushup"

    def _sync_source(self):
        source_type = self.source_type_var.get()
        camera = source_type == "摄像头"
        if source_type == "内置参考视频":
            vid = find_reference_video(self.action_id())
            self.file_var.set(str(vid) if vid else "")
        self.camera_frame.grid() if camera else self.camera_frame.grid_remove()
        self.file_entry.grid_remove() if camera else self.file_entry.grid()
        self.browse_btn.grid_remove() if camera else self.browse_btn.grid()
        self.browse_btn.configure(state="normal" if source_type == "选择本地视频" else "disabled")
        self.file_entry.configure(state="normal" if source_type == "选择本地视频" else "readonly")
        # 动作变了，今日目标/完成量也要跟着刷新
        if hasattr(self, "goal_status_var"):
            self._sync_goal()

    def _browse(self):
        path = filedialog.askopenfilename(parent=self.root, 
            title="选择动作视频",
            filetypes=[("视频文件", "*.mp4 *.mov *.avi *.mkv *.webm *.ogv *.ogg"),
                       ("所有文件", "*")],
        )
        if path:
            self.file_var.set(path)

    def _source_value(self):
        if self.source_type_var.get() == "摄像头":
            try:
                selected = self.camera_var.get()
                return int(self.custom_camera_var.get() if selected == "custom" else selected)
            except ValueError as exc:
                raise ValueError("摄像头设备号必须是整数") from exc
        path = Path(self.file_var.get()).expanduser()
        if not path.is_file():
            raise ValueError(f"找不到视频文件：{path}")
        return path

    def start(self):
        if self.process and self.process.poll() is None:
            return
        try:
            source_value = self._source_value()
        except ValueError as exc:
            self._msg("showerror", "无法开始", str(exc))
            return

        report_dir = ROOT / "captures/reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        aid = self.action_id()
        self.report_path = report_dir / f"{aid}-{stamp}.json"
        self.control_path = report_dir / f"control-{aid}-{stamp}.json"
        use_group = bool(self.group_on_var.get())
        cmd = build_command(
            aid, self.source_type_var.get(), source_value,
            self.voice_var.get(), self.report_path, self.control_path,
            user=self.store.current_user(),
            sets=(int(self.sets_var.get() or 0) if use_group else 0),
            reps_per_set=int(self.reps_per_set_var.get() or 10),
            rest=float(self.rest_var.get() or 0))
        self._append_log("\n$ " + " ".join(cmd) + "\n")
        try:
            self.process = subprocess.Popen(
                cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as exc:
            self._msg("showerror", "启动失败", str(exc))
            return

        # MediaPipe 0.10.35 启动时会尝试上传遥测，网络超时导致**卡约 61 秒**才出画面
        # （见 CLAUDE.md「mediapipe 版本坑」）。不提前说明的话很容易被当成卡死。
        self.status_var.set("启动中…首次约需 1 分钟（MediaPipe 初始化），画面出现前请稍候")
        self._append_log("[提示] MediaPipe 首次初始化约需 1 分钟 —— 它在尝试上传遥测并等网络超时。\n"
                         "       这段时间画面不会出现，**不是卡死**，请稍候。\n"
                         "[提示] 结束测试的三种方式：① 识别画面里按 q 或 ESC；"
                         "② 点识别窗口的关闭按钮；③ 点这里的「停止」。\n"
                         "       ⚠ 按 q 没反应时，先用鼠标点一下识别画面（macOS 上命令行窗口\n"
                         "         默认拿不到键盘焦点，点一下就有了）。\n")
        set_btn_enabled(self.start_btn, False, PRIMARY)
        set_btn_enabled(self.stop_btn, True, DANGER)
        set_btn_enabled(self.reset_btn, True, WARN)
        set_btn_enabled(self.restart_btn, True, SUCCESS)
        # 只闪一下置顶（同样不能持久，否则识别画面会被压住）
        self._flash_topmost()
        # ⚠ 识别期间**不要**抢焦点：识别窗口（realtime_pose）自己会抢前台，
        #   两边一起抢的结果就是「两个窗口来回乱跳」，用户根本看不清画面。
        #   识别结束后（_finished）再把焦点收回来给控制台。
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        proc = self.process
        if proc and proc.stdout:
            for line in proc.stdout:
                self.messages.put(("log", line))
        code = proc.wait() if proc else -1
        self.messages.put(("done", code))

    def stop(self):
        if self.process and self.process.poll() is None:
            self.status_var.set("正在停止…")
            self._send_command("stop")
            pid = self.process.pid
            self.root.after(2500, lambda: self._force_stop(pid))

    def reset(self):
        if self.process and self.process.poll() is None:
            self._send_command("reset")
            self.reps_var.set("0")
            self.rate_var.set("--")
            self.errors_var.set("暂无")
            self.status_var.set("已发送清零命令")

    def _send_command(self, command):
        if not self.control_path:
            return
        write_control_command(self.control_path, command)

    def _force_stop(self, pid):
        if self.process and self.process.pid == pid and self.process.poll() is None:
            self.process.terminate()

    def restart(self):
        if self.process and self.process.poll() is None:
            self.restart_pending = True
            self.stop()
        else:
            self.start()

    def _poll_messages(self):
        """
        消费子进程输出。

        这里必须**限量**：识别进程每秒会吐不少行，如果 while True 一直消费，
        主线程就被日志刷满，按钮点击明显迟钝（这就是「按键不灵敏」的主因之一）。
        每轮最多处理一批，剩下的留给下一轮，保证界面事件有机会被处理。
        """
        for _ in range(60):
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(value)
                match = re.search(r"第\s*(\d+)\s*次", value)
                if match:
                    self.reps_var.set(match.group(1))
            else:
                self._finished(value)
        self.root.after(80, self._poll_messages)

    def _finished(self, return_code):
        self.process = None
        set_btn_enabled(self.start_btn, True, PRIMARY)
        set_btn_enabled(self.stop_btn, False, DANGER)
        set_btn_enabled(self.reset_btn, False, WARN)
        set_btn_enabled(self.restart_btn, False, SUCCESS)
        if self.report_path and self.report_path.is_file():
            try:
                data = json.loads(self.report_path.read_text(encoding="utf-8"))
                self.reps_var.set(str(data.get("reps", 0)))
                score = data.get("score")
                self.score_var.set(
                    f"{score:.0f} 分" if isinstance(score, (int, float))
                    else "—（未评分）")
                self.rate_var.set(f"{data.get('detection_rate', 0) * 100:.1f}%")
                errors = data.get("errors") or {}
                tips = data.get("error_tips") or {}
                self.errors_var.set(
                    "、".join(f"{tips.get(k, k)}×{v}" for k, v in errors.items()) or "无"
                )
                self.status_var.set("测试完成" if return_code == 0 else f"异常结束（{return_code}）")
            except (OSError, ValueError) as exc:
                self.status_var.set(f"报告读取失败：{exc}")
        else:
            self.status_var.set("已停止" if return_code < 0 else f"未生成报告（{return_code}）")
        if hasattr(self, "report_list"):
            self._refresh_stats()       # 刚跑完：历史列表多一条，目标进度也要更新
            self._draw_trend()          # 趋势图立即反映新数据
        # 识别结束了，这时把焦点收回控制台（用户接下来要操作按钮）
        self.root.after(300, self._grab_focus)
        if self.restart_pending:
            self.restart_pending = False
            self.root.after(250, self.start)

    MAX_LOG_LINES = 1500        # 日志文本上限；超了砍掉最前面一段

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        # 文本无限增长会让 Text 重绘越来越慢，最终整个界面发卡
        try:
            lines = int(self.log.index("end-1c").split(".")[0])
            if lines > self.MAX_LOG_LINES:
                self.log.delete("1.0", f"{lines - self.MAX_LOG_LINES}.0")
        except (ValueError, tk.TclError):
            pass
        self.log.see("end")
        self.log.configure(state="disabled")

    def _close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("aqua")
    except tk.TclError:
        pass
    FitnessTestUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
