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

from action_editor import (ANGLE_PARTS, CHECKS, PAIR_PARTS, SIGNALS, WHENS,
                           build_action_config, slugify_id, validate_and_save)
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
SOURCE_TYPES = ("摄像头", "选择本地视频", "内置参考视频", "关键点数据")
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
# ══════════════════════════════════════════════════════════════════
# 配色方案：靛蓝（Indigo）+ 琥珀金（Amber）强调
# 灵感：运动/效率类 App 的调性 —— 靛蓝沉稳专业，琥珀金点缀关键数据
# ══════════════════════════════════════════════════════════════════
BG         = "#f0f2f8"      # 页面底色（稍带靛蓝调的灰白）
CARD       = "#ffffff"      # 卡片底色
SOFT       = "#f5f6fa"      # 输入框等「凹下去」的区域
BORDER     = "#e2e4ee"      # 分隔线
TEXT       = "#1a1b26"      # 主文字（更深的墨色）
MUTED      = "#6b7280"      # 次要说明文字（Tailwind gray-500）
# —— 主色：靛蓝 Indigo ——
PRIMARY    = "#4F46E5"      # 主色 Indigo-600（开始 / 强调）
PRIMARY_HI = "#4338CA"      # Indigo-700（hover 按下态）
PRIMARY_SOFT = "#EEF2FF"    # Indigo-50（淡色底，用于标签 hover）
# —— 强调色：琥珀金 Amber ——
ACCENT     = "#F59E0B"      # Amber-500（强调数字 / 徽章）
ACCENT_HI  = "#D97706"      # Amber-600
# —— 语义色：更明快的 Tailwind 500 色 ——
SUCCESS    = "#10B981"      # Emerald-500
SUCCESS_HI = "#059669"      # Emerald-600
DANGER     = "#EF4444"      # Red-500
DANGER_HI  = "#DC2626"      # Red-600
WARN       = "#F59E0B"      # 和 ACCENT 统一（琥珀金即警告色）
WARN_HI    = "#D97706"
GREY       = "#9CA3AF"      # 禁用态 gray-400

# 字体族：macOS 上中文用 PingFang SC 最好看（Helvetica 的中文是回退字形，偏细偏挤）。
# 写上完整回退链，别的系统上也能正常显示。
def _pick_font(*names):
    import tkinter.font as tkfont
    try:
        avail = set(tkfont.families())
    except Exception:
        return names[0]
    for n in names:
        if n in avail:
            return n
    return names[0]


FAMILY = _pick_font("PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                    "Noto Sans CJK SC", "Helvetica")
F_TITLE = (FAMILY, 23, "bold")
F_H2    = (FAMILY, 14, "bold")
F_BODY  = (FAMILY, 12)
F_SMALL = (FAMILY, 11)
F_TINY  = (FAMILY, 10)
F_NUM   = (FAMILY, 27, "bold")
F_BTN   = (FAMILY, 13, "bold")


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
                 background="#e2e4ee", foreground=MUTED, borderwidth=0)
    st.map("TNotebook.Tab",
           background=[("selected", CARD)], foreground=[("selected", PRIMARY)])
    st.configure("Trend.Horizontal.TProgressbar", troughcolor="#e5e7f0",
                 background=PRIMARY, borderwidth=0, thickness=12)
    return st


def section_gap(parent, text=None):
    """
    区块之间的分隔：一条细线（可带小标题）。
    App 里常用这种「留白 + 一条极淡的线」来分 section，比粗边框干净得多。
    """
    box = tk.Frame(parent, bg=BG)
    box.pack(fill="x", pady=(2, 10))
    if text:
        tk.Label(box, text=text, bg=BG, fg=MUTED, font=F_TINY).pack(anchor="w", pady=(0, 4))
    tk.Frame(box, bg=BORDER, height=1).pack(fill="x")
    return box


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
                    font=F_BTN, cursor="hand2", padx=22, pady=11, **kw)

    def _enter(_e=None):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=hi)

    def _leave(_e=None):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=bg)

    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", _leave)
    return btn


# 动作 id → 图标。加新动作时没配图标也不影响（走默认的 •）
ACTION_ICONS = {
    "squat": "🏋️",
    "pushup": "💪",
    "jumping_jack": "🤸",
    "curl": "🦾",
}


def action_label(name, aid):
    """按钮上显示的文字：图标 + 中文名。"""
    return f"{ACTION_ICONS.get(aid, '•')}  {name}"


def paint_action_button(btn, selected):
    """
    手动给动作按钮上色，区分「选中 / 未选中」。

    ⚠ 不能只靠 `selectcolor` —— 在 clam 主题下它经常不生效，
    结果就是**点了和没点看起来一模一样**（用户实测反馈过）。
    所以这里用回调显式改背景/前景：选中 = 主色底白字，未选中 = 浅灰底深字。
    """
    if selected:
        btn.configure(bg=PRIMARY, fg="white", activebackground=PRIMARY_HI,
                      activeforeground="white")
    else:
        btn.configure(bg=SOFT, fg=MUTED, activebackground="#e5e7f0",
                      activeforeground=TEXT)


def set_btn_enabled(btn, enabled, base):
    """统一处理按钮启用/禁用（顺带把颜色切到灰，一眼看出能不能点）。"""
    btn.configure(state="normal" if enabled else "disabled",
                  bg=base if enabled else GREY, cursor="hand2" if enabled else "arrow")


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
    elif source_type == "关键点数据":
        # 关键点数据回放：走**和摄像头完全一样**的流程（HUD 计数 / 质量提示 /
        # 语音 / 训练历史 / 报告），只是关键点来自文件而不是推理。
        cmd += ["--data", str(source_value)]
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



class ActionEditor(tk.Toplevel):
    """
    新建动作的表单窗口 —— **完全不碰 JSON**。

    设计上只做一件事：把「配置字段」翻译成「人话」。
      · 关键点编号（23,25,27）→ 下拉选「左膝角（髋-膝-踝）」
      · lo / hi              → 「信号降到多少算开始 / 回到多少算完成」
      · when / check         → 「什么时候判 / 判什么」

    保存前**先跑一遍配置校验器**，有错就拒绝保存并说明原因 ——
    否则界面里会多出一个「怎么都不计数」的动作，用户很难联想到是字段写错了。
    """

    def __init__(self, master, existing_ids, on_saved):
        super().__init__(master)
        self.title("新建动作")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)
        self.on_saved = on_saved
        self.existing_ids = list(existing_ids)
        self._user_edited_id = False

        # 表单内容比较长（三块卡片 + 提示），小屏上会顶出屏幕、够不到「保存」。
        # 所以：**底部按钮固定在窗口下方，中间内容区单独滚动** ——
        # 这样无论屏幕多矮，保存/取消永远在眼前。
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"620x{min(720, int(sh * 0.82))}")

        bottom = tk.Frame(self, bg=BG, padx=20, pady=12)
        bottom.pack(side="bottom", fill="x")

        shell = tk.Frame(self, bg=BG)
        shell.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set, yscrollincrement=20)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        pad = tk.Frame(canvas, bg=BG, padx=20, pady=16)
        win = canvas.create_window((0, 0), window=pad, anchor="nw")
        pad.bind("<Configure>",
                 lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        # 滚轮只在这个窗口里生效，且做 16ms 节流（高频事件别直接怼 Python）
        self._wheel_ts = 0.0

        def _wheel(e):
            now = time.time()
            if now - self._wheel_ts < 0.016:
                return
            self._wheel_ts = now
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind("<MouseWheel>", _wheel)
        self._canvas = canvas

        tk.Label(pad, text="新建动作", bg=BG, fg=TEXT, font=F_TITLE).pack(anchor="w")
        tk.Label(pad, text="填完保存即可 —— 动作列表会自动多出一个，和内置动作一样能测。",
                 bg=BG, fg=MUTED, font=F_SMALL).pack(anchor="w", pady=(2, 12))

        # ── 基本信息 ──
        base = card(pad, "① 基本信息", pady=(0, 10))
        base.columnconfigure(1, weight=1)

        tk.Label(base, text="动作名称", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(2, 6))
        self.name_var = tk.StringVar()
        ent = ttk.Entry(base, textvariable=self.name_var, width=26)
        ent.grid(row=0, column=1, sticky="ew", pady=(2, 6))
        self.name_var.trace_add("write", self._on_name)

        tk.Label(base, text="动作 id", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        self.id_var = tk.StringVar()
        ttk.Entry(base, textvariable=self.id_var, width=26).grid(
            row=1, column=1, sticky="ew", pady=6)
        self.id_var.trace_add("write", lambda *_: setattr(self, "_user_edited_id", True))
        tk.Label(base, text="（文件名，英文/数字；留空自动生成）", bg=CARD, fg=MUTED,
                 font=F_TINY).grid(row=2, column=1, sticky="w")

        tk.Label(base, text="拍摄机位", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=(6, 2))
        self.side_var = tk.StringVar(value="正面")
        sf = tk.Frame(base, bg=CARD)
        sf.grid(row=3, column=1, sticky="w", pady=(6, 2))
        for s in ("正面", "侧"):
            tk.Radiobutton(sf, text=s, variable=self.side_var, value=s, bg=CARD,
                           fg=TEXT, selectcolor=SOFT, activebackground=CARD,
                           font=F_BODY, relief="flat", bd=0,
                           highlightthickness=0).pack(side="left", padx=(0, 16))

        # ── 计数规则 ──
        cnt = card(pad, "② 怎么算一次", pady=(0, 10))
        cnt.columnconfigure(1, weight=1)

        tk.Label(cnt, text="判定信号", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(2, 6))
        self.sig_var = tk.StringVar(value=SIGNALS[0][1])
        cb = ttk.Combobox(cnt, textvariable=self.sig_var, state="readonly", width=24,
                          values=[s[1] for s in SIGNALS])
        cb.grid(row=0, column=1, sticky="ew", pady=(2, 6))
        cb.bind("<<ComboboxSelected>>", self._on_signal)
        self.sig_hint = tk.Label(cnt, text="", bg=CARD, fg=MUTED, font=F_TINY,
                                 wraplength=430, justify="left")
        self.sig_hint.grid(row=1, column=1, sticky="w")

        tk.Label(cnt, text="测量部位", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=(6, 6))
        self.part_var = tk.StringVar()
        self.part_cb = ttk.Combobox(cnt, textvariable=self.part_var, state="readonly", width=24)
        self.part_cb.grid(row=2, column=1, sticky="ew", pady=(6, 6))
        self.pts_label = tk.Label(cnt, text="", bg=CARD, fg=MUTED, font=F_TINY)
        self.pts_label.grid(row=3, column=1, sticky="w")
        self.part_cb.bind("<<ComboboxSelected>>", lambda _e: self._show_points())

        tk.Label(cnt, text="计数方向", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=4, column=0, sticky="w", padx=(0, 12), pady=(6, 2))
        self.dir_var = tk.StringVar(value="先变小")
        df = tk.Frame(cnt, bg=CARD)
        df.grid(row=4, column=1, sticky="w", pady=(6, 2))
        for s in ("先变小", "先变大"):
            tk.Radiobutton(df, text=s, variable=self.dir_var, value=s, bg=CARD,
                           fg=TEXT, selectcolor=SOFT, activebackground=CARD,
                           font=F_BODY, relief="flat", bd=0, highlightthickness=0,
                           command=self._update_words).pack(side="left", padx=(0, 16))

        self.start_lbl = tk.Label(cnt, text="", bg=CARD, fg=MUTED, font=F_SMALL)
        self.start_lbl.grid(row=5, column=0, sticky="w", padx=(0, 12), pady=(6, 6))
        self.start_var = tk.StringVar(value="90")
        ttk.Spinbox(cnt, from_=-999, to=999, increment=1, width=10,
                    textvariable=self.start_var).grid(row=5, column=1, sticky="w", pady=(6, 6))

        self.end_lbl = tk.Label(cnt, text="", bg=CARD, fg=MUTED, font=F_SMALL)
        self.end_lbl.grid(row=6, column=0, sticky="w", padx=(0, 12), pady=6)
        self.end_var = tk.StringVar(value="150")
        ttk.Spinbox(cnt, from_=-999, to=999, increment=1, width=10,
                    textvariable=self.end_var).grid(row=6, column=1, sticky="w", pady=6)

        tk.Label(cnt, text="循环次数", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=7, column=0, sticky="w", padx=(0, 12), pady=(6, 2))
        cyc = tk.Frame(cnt, bg=CARD)
        cyc.grid(row=7, column=1, sticky="w", pady=(6, 2))
        self.cyc_var = tk.StringVar(value="1")
        ttk.Spinbox(cyc, from_=1, to=10, width=6,
                    textvariable=self.cyc_var).pack(side="left")
        tk.Label(cyc, text="个完整往返算 1 次", bg=CARD, fg=MUTED,
                 font=F_TINY).pack(side="left", padx=6)

        self.calib_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cnt, text="启用站立基线自动校准（只适合「站立姿势就是动作起始姿势」的动作）",
                        variable=self.calib_var).grid(
            row=8, column=1, sticky="w", pady=(8, 2))

        # ── 质量要求 ──
        q = card(pad, "③ 质量要求（可选：不合格时提示什么）", pady=(0, 10))
        q.columnconfigure(1, weight=1)

        self.depth_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(q, text="动作幅度要够 —— 信号至少要到达",
                        variable=self.depth_on).grid(row=0, column=0, sticky="w", pady=4)
        self.depth_th = tk.StringVar(value="110")
        ttk.Spinbox(q, from_=-999, to=999, width=10,
                    textvariable=self.depth_th).grid(row=0, column=1, sticky="w", pady=4)
        self.depth_tip = tk.StringVar(value="动作幅度不够，再做大一点")
        ttk.Entry(q, textvariable=self.depth_tip, width=30).grid(
            row=1, column=1, sticky="ew", pady=(0, 6))
        tk.Label(q, text="提示语", bg=CARD, fg=MUTED, font=F_TINY).grid(
            row=1, column=0, sticky="w")

        self.back_on = tk.BooleanVar(value=True)
        ttk.Checkbutton(q, text="要回到起始位置 —— 信号至少要回到",
                        variable=self.back_on).grid(row=2, column=0, sticky="w", pady=4)
        self.back_th = tk.StringVar(value="165")
        ttk.Spinbox(q, from_=-999, to=999, width=10,
                    textvariable=self.back_th).grid(row=2, column=1, sticky="w", pady=4)
        self.back_tip = tk.StringVar(value="要回到起始姿势，别停在半路")
        ttk.Entry(q, textvariable=self.back_tip, width=30).grid(
            row=3, column=1, sticky="ew", pady=(0, 6))
        tk.Label(q, text="提示语", bg=CARD, fg=MUTED, font=F_TINY).grid(
            row=3, column=0, sticky="w")

        tk.Label(pad, text="提示：数值不用一次填准 —— 先用参考数据或摄像头试一次，"
                           "看终端打印的实测值再回来改。",
                 bg=BG, fg=MUTED, font=F_TINY, wraplength=460,
                 justify="left").pack(anchor="w", pady=(2, 10))

        # ── 按钮（固定在窗口底部，不随内容滚动）──
        btns = bottom
        hover_btn(btns, "保存动作", self._save, SUCCESS, SUCCESS_HI).pack(side="left")
        tk.Button(btns, text="取消", command=self._close_editor, bg=SOFT, fg=TEXT,
                  activebackground="#e5e7f0", font=F_BTN, relief="flat", bd=0,
                  highlightthickness=0, padx=18, pady=9,
                  cursor="hand2").pack(side="left", padx=8)
        tk.Label(btns, text="保存前会自动校验配置", bg=BG, fg=MUTED,
                 font=F_TINY).pack(side="right")

        self._on_signal()
        self._update_words()
        self.update_idletasks()
        # 居中到父窗口，并保证不超出屏幕
        try:
            w, h = 620, min(720, int(sh * 0.82))
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = max(20, master.winfo_rooty() + 40)
            x = max(0, min(x, sw - w))
            y = max(0, min(y, sh - h - 40))
            self.geometry(f"{w}x{h}+{x}+{y}")
        except tk.TclError:
            pass
        # ⚠ 必须接管关闭事件：点窗口的 X 也要释放 grab。
        # 之前只有「保存」那条路径释放，用户直接关窗的话 grab 会一直握着，
        # **主界面所有按钮就全点不动了**（表现为「点开始测试没反应」）。
        self.protocol("WM_DELETE_WINDOW", self._close_editor)
        self.grab_set()
        ent.focus_set()

    def _close_editor(self):
        """关闭表单：先释放 grab 再销毁，保证主界面恢复可点。"""
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    # ---------- 联动 ----------
    def _on_name(self, *_a):
        if not self._user_edited_id:
            self.id_var.set(slugify_id(self.name_var.get(), self.existing_ids))

    def _signal(self):
        name = self.sig_var.get()
        return next((s for s in SIGNALS if s[1] == name), SIGNALS[0])

    def _on_signal(self, *_a):
        sig, label, arity, unit, hint = self._signal()
        self.sig_hint.config(text=f"{hint}（单位：{unit}）")
        parts = ANGLE_PARTS if arity == 3 else PAIR_PARTS
        keys = list(parts)
        self.part_cb.configure(values=keys)
        if self.part_var.get() not in keys:
            self.part_var.set(keys[0])
        self.pts_label.config(text=f"关键点编号：{parts[self.part_var.get()]}"
                                   f"（程序自动填，不用记）")
        self._update_words()

    def _show_points(self):
        sig, label, arity, unit, hint = self._signal()
        parts = ANGLE_PARTS if arity == 3 else PAIR_PARTS
        self.pts_label.config(text=f"关键点编号：{parts[self.part_var.get()]}"
                                   f"（程序自动填，不用记）")

    def _update_words(self):
        """把「起始/还原阈值」的措辞跟着计数方向变，避免用户填反。"""
        down = self.dir_var.get() == "先变小"
        sig, label, arity, unit, hint = self._signal()
        u = "" if unit == "倍肩宽" else "°"
        if down:
            self.start_lbl.config(text=f"信号降到多少算开始（{unit}）")
            self.end_lbl.config(text=f"回到多少算完成（{unit}）")
        else:
            self.start_lbl.config(text=f"信号升到多少算开始（{unit}）")
            self.end_lbl.config(text=f"回到多少算完成（{unit}）")

    # ---------- 保存 ----------
    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("还差一点", "请先填「动作名称」", parent=self)
            return
        aid = (self.id_var.get().strip() or slugify_id(name, self.existing_ids))
        if aid in self.existing_ids:
            messagebox.showwarning("id 重复",
                                   f"已经有叫「{aid}」的动作了，换一个 id。", parent=self)
            return
        if aid != slugify_id(aid):
            messagebox.showwarning("id 不合法",
                                   "id 只能用英文字母、数字和下划线。", parent=self)
            return
        sig, label, arity, unit, hint = self._signal()
        parts = ANGLE_PARTS if arity == 3 else PAIR_PARTS
        try:
            start_th = float(self.start_var.get())
            end_th = float(self.end_var.get())
            cycles = int(self.cyc_var.get())
            depth_th = float(self.depth_th.get()) if self.depth_on.get() else None
            back_th = float(self.back_th.get()) if self.back_on.get() else None
        except (TypeError, ValueError):
            messagebox.showwarning("数值填错了", "阈值和循环次数都要填数字。", parent=self)
            return

        first_lo = self.dir_var.get() == "先变小"
        # 方向相关的合法性：先变小的动作，起始阈值必须低于还原阈值，否则永远进不了动作
        if first_lo and not (start_th < end_th):
            messagebox.showwarning("阈值方向反了",
                                   "「先变小」的动作：开始阈值要小于完成阈值。\n"
                                   f"现在填的是 开始 {start_th:g} / 完成 {end_th:g}。",
                                   parent=self)
            return
        if (not first_lo) and not (start_th > end_th):
            messagebox.showwarning("阈值方向反了",
                                   "「先变大」的动作：开始阈值要大于完成阈值。\n"
                                   f"现在填的是 开始 {start_th:g} / 完成 {end_th:g}。",
                                   parent=self)
            return

        cfg = build_action_config(
            name=name, aid=aid, signal=sig, points=parts[self.part_var.get()],
            start_th=start_th, end_th=end_th, first_lo=first_lo, cycles=cycles,
            camera_side=self.side_var.get(), calibrate=self.calib_var.get(),
            depth_check=self.depth_on.get(), depth_th=depth_th,
            depth_tip=self.depth_tip.get().strip() or None,
            straight_check=self.back_on.get(), straight_th=back_th,
            straight_tip=self.back_tip.get().strip() or None,
        )
        ok, msg, path = validate_and_save(cfg, ROOT / "configs")
        if not ok:
            messagebox.showerror("保存失败", msg, parent=self)
            return
        self._close_editor()
        self.on_saved(cfg, msg)


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

        # ══════════ App 顶栏：返回 + 标题 + 状态徽章 ══════════
        head = tk.Frame(outer, bg=BG)
        head.pack(fill="x", pady=(0, 16))

        # 右侧状态徽章（运行时会变色，见 _set_badge）
        self.badge = tk.Label(head, text="●  空闲", bg="#D1FAE5", fg=SUCCESS,
                              font=F_BTN, padx=16, pady=7)
        self.badge.pack(side="right", anchor="ne")

        # 左侧：返回按钮（子页才显示）+ 图标 + 标题
        left = tk.Frame(head, bg=BG)
        left.pack(side="left", anchor="w")

        self.back_btn = tk.Button(left, text="←  返回", command=lambda: self._show_page("home"),
                                  bg=SOFT, fg=TEXT, activebackground="#e5e7f0",
                                  font=F_SMALL, relief="flat", bd=0,
                                  highlightthickness=0, padx=14, pady=7,
                                  cursor="hand2")

        self.head_icon = tk.Label(left, text="🏋️", bg=BG, font=(FAMILY, 30))
        self.head_icon.pack(side="left", padx=(0, 10))
        titles = tk.Frame(left, bg=BG)
        titles.pack(side="left", anchor="w")
        self.head_title = tk.Label(titles, text="健身动作识别", bg=BG, fg=TEXT,
                                   font=F_TITLE)
        self.head_title.pack(anchor="w")
        self.head_sub = tk.Label(titles, text="点一个功能开始", bg=BG, fg=MUTED,
                                 font=F_SMALL)
        self.head_sub.pack(anchor="w", pady=(2, 0))

        # ══════════ 页面容器：每个功能一页，一次只显示一页 ══════════
        self.page_host = tk.Frame(outer, bg=BG)
        self.page_host.pack(fill="both", expand=True)
        self.pages = {}
        for _name in ("home", "test", "data", "actions", "log"):
            _f = tk.Frame(self.page_host, bg=BG)
            self.pages[_name] = _f

        # ══════════ 测试页 ══════════
        page = self.pages["test"]

        # ---- 卡片 1：测试设置 ----
        form = card(page, "⚙️  测试设置", "动作的判定逻辑全部来自 configs/ 下的配置文件")
        form.columnconfigure(1, weight=1)

        tk.Label(form, text="动作", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="nw", padx=(0, 14), pady=(10, 0))
        action_area = tk.Frame(form, bg=CARD)
        action_area.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(10, 0))
        action_area.columnconfigure(0, weight=1)
        self._action_area = action_area          # 新建动作后要往里重建按钮

        # 动作按钮**自动换行**：动作数量由 configs/ 决定，用户随时可能加，
        # 横排一行迟早挤爆（4 个就已经很挤了）。这里按每行 PER_ROW 个排，
        # 行数随动作数量自适应 —— 加动作时界面不用改，也不会把按钮压扁。
        PER_ROW = 3
        self._action_buttons = {}
        for i, (name, _aid) in enumerate(self.actions):
            r, c = divmod(i, PER_ROW)
            # indicatoron=False：把单选按钮画成「药丸按钮」，比小圆点更像 App。
            # 选中态用浅蓝底 —— tkinter 没法在选中时同时改字色，浅底黑字最稳妥。
            btn = tk.Radiobutton(
                action_area, text=action_label(name, _aid), variable=self.action_var,
                value=name,
                command=self._on_action_click, indicatoron=False,
                bg=SOFT, fg=MUTED, selectcolor=SOFT,
                activebackground="#e5e7f0", activeforeground=TEXT,
                font=F_BTN, relief="flat", bd=0, highlightthickness=0,
                padx=16, pady=9, cursor="hand2",
            )
            btn.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 8, 0),
                     pady=(0 if r == 0 else 8, 0))
            self._action_buttons[name] = btn
        for c in range(PER_ROW):
            action_area.columnconfigure(c, weight=1, uniform="act")
        self._paint_actions()          # 启动时就把选中项标出来

        # 加动作的入口直接放在动作区旁边 —— 用户最需要它的时候就在眼前
        add_row = tk.Frame(form, bg=CARD)
        add_row.grid(row=0, column=3, sticky="ne", padx=(10, 0), pady=(10, 0))
        tk.Button(add_row, text="＋ 新建动作", command=self._new_action,
                  bg="#EEF2FF", fg=PRIMARY, activebackground="#E0E7FF",
                  font=F_SMALL, relief="flat", bd=0, highlightthickness=0,
                  padx=14, pady=6, cursor="hand2").pack(fill="x")
        tk.Button(add_row, text="校验配置", command=self._validate_configs,
                  bg=SOFT, fg=TEXT, activebackground="#e5e7f0",
                  font=F_SMALL, relief="flat", bd=0, highlightthickness=0,
                  padx=14, pady=6, cursor="hand2").pack(fill="x", pady=(6, 0))

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
                cursor="hand2",
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
                           cursor="hand2").pack(side="left", padx=pad)
        self.camera_box = ttk.Spinbox(self.camera_frame, from_=0, to=9, width=4,
                                      textvariable=self.custom_camera_var)
        self.camera_box.pack(side="left")

        ttk.Checkbutton(form, text="开启中文语音提醒和报数",
                        variable=self.voice_var).grid(row=3, column=1, sticky="w",
                                                      pady=(12, 0))

        # ══════════ 卡片 2：训练管理（模块 7 / 8 / 10）══════════
        train = card(page, "🎯  训练管理", "多用户档案 · 分组间歇 · 每日目标 · 训练历史")
        train.columnconfigure(1, weight=1)

        tk.Label(train, text="用户", bg=CARD, fg=MUTED, font=F_SMALL).grid(
            row=0, column=0, sticky="w", padx=(0, 14), pady=(10, 0))
        self.user_box = ttk.Combobox(train, textvariable=self.user_var,
                                     values=self.store.list_users(), width=14)
        self.user_box.grid(row=0, column=1, sticky="w", pady=(10, 0))
        tk.Button(train, text="切换", command=self._switch_user, bg=SOFT, fg=TEXT,
                  activebackground="#e5e7f0", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="hand2").grid(
            row=0, column=2, sticky="w", padx=6, pady=(10, 0))
        tk.Button(train, text="新建用户…", command=self._new_user, bg=SOFT, fg=TEXT,
                  activebackground="#e5e7f0", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="hand2").grid(
            row=0, column=3, sticky="w", pady=(10, 0))
        tk.Button(train, text="删除用户…", command=self._delete_user, bg=SOFT, fg=DANGER,
                  activebackground="#FEE2E2", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="hand2").grid(
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
                  activebackground="#e5e7f0", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="hand2").pack(side="left")
        tk.Button(tframe, text="查看趋势图", command=self._show_trend, bg=SOFT, fg=PRIMARY,
                  activebackground="#e5e7f0", font=F_SMALL, relief="flat", bd=0,
                  highlightthickness=0, padx=14, pady=5, cursor="hand2").pack(
            side="left", padx=10)

        # ══════════ 主操作按钮 ══════════
        section_gap(page, "操作")
        buttons = tk.Frame(page, bg=BG)
        buttons.pack(fill="x", pady=(2, 14))
        self.start_btn = hover_btn(buttons, "▶  开始测试", self.start, PRIMARY, PRIMARY_HI)
        self.start_btn.pack(side="left")
        self.stop_btn = hover_btn(buttons, "■  停止", self.stop, DANGER, DANGER_HI)
        self.stop_btn.pack(side="left", padx=8)
        self.reset_btn = hover_btn(buttons, "↺  清零", self.reset, WARN, WARN_HI, fg="#78350F")
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
        res = card(page, "📊  最近一次测试结果")
        for col in range(4):
            res.columnconfigure(col, weight=1, uniform="res")
        for col, (icon, label, var, color, font) in enumerate((
                ("🔢", "完成次数", self.reps_var, TEXT, F_NUM),
                ("⭐", "动作评分", self.score_var, ACCENT, F_NUM),
                ("👁", "关键点检出率", self.rate_var, PRIMARY, ("Helvetica", 20, "bold")),
                ("⚠", "错误事件", self.errors_var, DANGER, F_SMALL))):
            tk.Label(res, text=f"{icon} {label}", bg=CARD, fg=MUTED, font=F_SMALL).grid(
                row=0, column=col)
            tk.Label(res, textvariable=var, bg=CARD, fg=color, font=font,
                     wraplength=230, justify="center").grid(row=1, column=col, pady=(10, 2))

        # ══════════ 数据页：趋势图 + 历史统计 ══════════
        dp = self.pages["data"]
        notebook = ttk.Notebook(dp)
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
            bg=SOFT, fg=TEXT, selectbackground="#E0E7FF", selectforeground=TEXT,
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
                      activebackground="#e5e7f0", font=F_SMALL, relief="flat", bd=0,
                      highlightthickness=0, padx=14, pady=5, width=9,
                      cursor="hand2").pack(pady=3)

        # ══════════ 日志页（独立一页，不再是标签页）══════════
        lp = self.pages["log"]
        log_box = tk.Frame(lp, bg=CARD, padx=10, pady=10)
        log_box.pack(fill="both", expand=True)
        self.log = tk.Text(log_box, height=24, wrap="word", state="disabled",
                           background="#1c2128", foreground="#d7dde5",
                           insertbackground="white", relief="flat", bd=0,
                           highlightthickness=0, font=("Menlo", 11),
                           padx=14, pady=12)
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # ══════════ 动作管理页 ══════════
        ap = self.pages["actions"]
        acard = card(ap, "⚙️  动作管理", "动作列表由 configs/ 目录自动生成")
        self._action_admin_area = acard      # 这里列出所有动作（可选中/新建）
        tk.Button(acard, text="＋  新建动作（填表即可，不用写 JSON）",
                  command=self._new_action, bg="#EEF2FF", fg=PRIMARY,
                  activebackground="#E0E7FF", font=F_BTN, relief="flat", bd=0,
                  highlightthickness=0, padx=20, pady=12,
                  cursor="hand2").pack(fill="x", pady=(6, 4))
        tk.Button(acard, text="校验全部配置", command=self._validate_configs,
                  bg=SOFT, fg=TEXT, activebackground="#e5e7f0", font=F_SMALL,
                  relief="flat", bd=0, highlightthickness=0, padx=16, pady=8,
                  cursor="hand2").pack(fill="x", pady=(4, 0))
        self._rebuild_admin_list()

        # ══════════ 首页：四个大功能卡片 ══════════
        hp = self.pages["home"]
        intro = tk.Frame(hp, bg=BG)
        intro.pack(fill="x", pady=(4, 14))
        tk.Label(intro, text="选择要做什么", bg=BG, fg=TEXT, font=F_H2).pack(anchor="w")
        tk.Label(intro, text="动作判定全部由配置驱动 —— 加动作只需在「动作管理」里填张表",
                 bg=BG, fg=MUTED, font=F_SMALL).pack(anchor="w", pady=(3, 0))

        grid = tk.Frame(hp, bg=BG)
        grid.pack(fill="both", expand=True)
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform="tile")
        tiles = [
            ("▶", "开始测试", "选动作与输入方式，开始计数和姿态纠正", "test", PRIMARY),
            ("📊", "训练数据", "趋势图、历史记录、目标进度、错误排行", "data", "#6366F1"),
            ("⚙️", "动作管理", "查看现有动作、新建自定义动作、校验配置", "actions", SUCCESS),
            ("📝", "运行日志", "识别过程的完整输出（排错看这里）", "log", "#475569"),
        ]
        for i, (icon, title, desc, page_name, color) in enumerate(tiles):
            r, c = divmod(i, 2)
            tile = tk.Frame(grid, bg=CARD, cursor="hand2")
            tile.grid(row=r, column=c, sticky="nsew",
                      padx=(0 if c == 0 else 10, 0), pady=(0 if r == 0 else 10, 0))
            inner = tk.Frame(tile, bg=CARD, padx=20, pady=18)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=icon, bg=CARD, fg=color,
                     font=(FAMILY, 30)).pack(anchor="w")
            tk.Label(inner, text=title, bg=CARD, fg=TEXT, font=F_H2).pack(
                anchor="w", pady=(6, 2))
            tk.Label(inner, text=desc, bg=CARD, fg=MUTED, font=F_SMALL,
                     wraplength=260, justify="left").pack(anchor="w")
            # 整块卡片都能点（含里面的文字），点哪儿都算
            for w in (tile, inner, *inner.winfo_children()):
                w.bind("<Button-1>", lambda _e, p=page_name: self._show_page(p))
            tile.bind("<Enter>", lambda _e, f=tile, b=inner: (
                f.configure(bg="#EEF2FF"), b.configure(bg="#EEF2FF")))
            tile.bind("<Leave>", lambda _e, f=tile, b=inner: (
                f.configure(bg=CARD), b.configure(bg=CARD)))

        self._show_page("home")

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
            self.status_var.set("先在下面列表里点一条历史报告，再点「查看详情」")
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

    # 每个页面的顶栏文案：(图标, 标题, 副标题)
    PAGE_TITLES = {
        "home": ("🏋️", "健身动作识别", "点一个功能开始"),
        "test": ("▶", "开始测试", "选动作与输入方式，开始计数和姿态纠正"),
        "data": ("📊", "训练数据", "趋势图、历史记录、目标进度"),
        "actions": ("⚙️", "动作管理", "查看与新建动作 —— 加动作不用改代码"),
        "log": ("📝", "运行日志", "识别过程的完整输出，排错看这里"),
    }

    def _show_page(self, name):
        """
        切换页面：一次只显示一页。

        这样每个界面都只有一件事，不会像原来那样把
        「设置 + 训练管理 + 按钮 + 结果 + 三张图表」全堆在一屏，
        按钮小、点不准。
        """
        if not hasattr(self, "pages") or name not in self.pages:
            return
        for k, f in self.pages.items():
            if k == name:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()
        icon, title, sub = self.PAGE_TITLES.get(name, ("•", name, ""))
        self.head_icon.configure(text=icon)
        self.head_title.configure(text=title)
        self.head_sub.configure(text=sub)
        if name == "home":
            self.back_btn.pack_forget()
        else:
            self.back_btn.pack(side="left", padx=(0, 12), before=self.head_icon)
        self.current_page = name
        self._on_outer_configure()
        if name == "data" and getattr(self, "trend_canvas", None) is not None:
            self.root.after(60, self._draw_trend)   # 页面刚显示时尺寸才算得准
        if name == "actions":
            self._rebuild_admin_list()

    def _rebuild_admin_list(self):
        """动作管理页里列出所有动作（每次新建/删除后重建）。"""
        area = getattr(self, "_action_admin_area", None)
        if area is None:
            return
        for w in getattr(self, "_admin_rows", []):
            w.destroy()
        self._admin_rows = []
        for name, aid in self.actions:
            row = tk.Frame(area, bg=SOFT, padx=12, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=action_label(name, aid), bg=SOFT, fg=TEXT,
                     font=F_BODY).pack(side="left")
            tk.Label(row, text=f"configs/{aid}.json", bg=SOFT, fg=MUTED,
                     font=F_TINY).pack(side="right")
            self._admin_rows.append(row)

    def _set_badge(self, text, fg, bg):
        """更新右上角状态徽章（空闲 = 绿、运行中 = 蓝、异常 = 红）。"""
        if hasattr(self, "badge"):
            self.badge.configure(text=text, fg=fg, bg=bg)

    def _paint_actions(self):
        """按当前选中项重画所有动作按钮（选中 = 主色底白字，未选中 = 浅灰底）。"""
        cur = self.action_var.get()
        for name, btn in getattr(self, "_action_buttons", {}).items():
            paint_action_button(btn, name == cur)

    def _on_action_click(self):
        """点动作按钮：先更新配色，再同步输入源。"""
        self._paint_actions()
        self._sync_source()

    def _new_action(self):
        """打开「新建动作」表单 —— 填完保存即可，全程不碰 JSON。"""
        ActionEditor(self.root, self.existing_ids(),
                     on_saved=self._on_action_saved)

    def existing_ids(self):
        return [aid for _n, aid in self.actions]

    def _on_action_saved(self, cfg, msg):
        """表单保存成功 → 刷新动作列表并选中新动作。"""
        self._reload_actions(select=cfg["name"])
        self._flash_topmost()
        # 不弹窗 —— 保存成功后动作按钮已经出现在眼前，弹窗只会挡路
        self.status_var.set("动作已添加，可以直接选了开始测试")

    def _reload_actions(self, select=None):
        """
        重新扫描 configs/ 并重建动作按钮。

        有了它，「新建动作」保存后**不用重启界面** —— 按钮立刻就位。
        按钮排布逻辑与 _build 里保持一致（每行 3 个、自动换行）。
        """
        self.actions = discover_actions()
        for b in getattr(self, "_action_buttons", {}).values():
            b.destroy()
        self._action_buttons = {}
        area = getattr(self, "_action_area", None)
        if area is None:
            return
        for c in range(3):
            area.columnconfigure(c, weight=1, uniform="act")
        for i, (name, _aid) in enumerate(self.actions):
            r, c = divmod(i, 3)
            btn = tk.Radiobutton(
                area, text=action_label(name, _aid), variable=self.action_var, value=name,
                command=self._on_action_click, indicatoron=False,
                bg=SOFT, fg=MUTED, selectcolor=SOFT,
                activebackground="#e5e7f0", activeforeground=TEXT,
                font=F_BTN, relief="flat", bd=0, highlightthickness=0,
                padx=16, pady=9, cursor="hand2")
            btn.grid(row=r, column=c, sticky="ew",
                     padx=(0 if c == 0 else 8, 0), pady=(0 if r == 0 else 8, 0))
            self._action_buttons[name] = btn
        if select and select in self._action_buttons:
            self.action_var.set(select)
        self._paint_actions()
        self._sync_source()
        self._rebuild_admin_list()
        self._on_outer_configure()

    def _open_configs_dir(self):
        """打开 configs/ 目录 —— 自定义动作就是往里放一份 JSON。"""
        cfg = ROOT / "configs"
        cfg.mkdir(exist_ok=True)
        guide = ROOT / "自定义动作指南.md"
        n = len([p for p in cfg.glob("*.json")])
        self._msg("showinfo", "新建动作 = 加一份 JSON 配置",
                  f"动作列表是自动扫描 configs/ 目录生成的，现在有 {n} 份配置。\n\n"
                  f"新增一个动作只需：\n"
                  f"  1. 在打开的目录里复制一份现成的 JSON（比如 squat.json）\n"
                  f"  2. 改 id / name、判定用的关键点、关节角度信号、上下阈值\n"
                  f"  3. 回到本界面点「校验配置」检查有没有写错\n"
                  f"  4. 重启本界面 —— 动作按钮会自动多出来\n\n"
                  f"全程不需要改任何代码。\n"
                  f"字段说明见项目里的《自定义动作指南.md》"
                  + (f"（已找到：{guide.name}）" if guide.is_file() else ""))
        try:
            subprocess.Popen(["open", str(cfg)])
        except Exception:
            pass

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
        editable = source_type in ("选择本地视频", "关键点数据")
        if source_type == "内置参考视频":
            vid = find_reference_video(self.action_id())
            self.file_var.set(str(vid) if vid else "")
        elif source_type == "关键点数据":
            # 默认指向 samples/ 里的示例，省得用户空着手不知道填什么
            cur = Path(self.file_var.get()).expanduser()
            if not cur.is_file() or cur.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                demo = ROOT / "samples" / "squat_minimal.json"
                self.file_var.set(str(demo) if demo.is_file() else "")
        self.camera_frame.grid() if camera else self.camera_frame.grid_remove()
        self.file_entry.grid_remove() if camera else self.file_entry.grid()
        self.browse_btn.grid_remove() if camera else self.browse_btn.grid()
        self.browse_btn.configure(state="normal" if editable else "disabled")
        self.file_entry.configure(state="normal" if editable else "readonly")
        # 动作变了，今日目标/完成量也要跟着刷新
        if hasattr(self, "goal_status_var"):
            self._sync_goal()

    def _browse(self):
        if self.source_type_var.get() == "关键点数据":
            path = filedialog.askopenfilename(
                parent=self.root, title="选择关键点数据文件（JSON）",
                initialdir=str(ROOT / "samples") if (ROOT / "samples").is_dir() else str(ROOT),
                filetypes=[("关键点数据", "*.json"), ("所有文件", "*.*")])
            if path:
                self.file_var.set(path)
            return
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
        if self.source_type_var.get() == "关键点数据":
            if not path.is_file():
                raise ValueError(f"找不到关键点数据文件：{path}\n"
                                 f"可以先试 samples/squat_minimal.json")
            return path
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
        self._set_badge("●  运行中", PRIMARY, "#EEF2FF")
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
        if return_code == 0:
            self._set_badge("●  完成", SUCCESS, "#D1FAE5")
        else:
            self._set_badge("●  已停止", MUTED, BG)
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

                # ⚠ 检出率为 0 是最容易被误解成「程序坏了」的情况：
                # 画面明明在动（帧数在涨），但模型一帧都没看到人，于是计数永远是 0。
                # 这时必须**明确说清是什么问题**，否则用户会反复重试还以为功能没做好。
                # 判断「画面里有没有人」要用 person_rate（可信地看到人的比例），
                # 不能用 detection_rate —— 后者只表示「模型吐了关键点」，
                # 人不在画面里时模型照样会吐「幽灵骨架」，检出率反而显示 100%。
                rate = float(data.get("person_rate", data.get("detection_rate")) or 0)
                frames = int(data.get("total_frames") or 0)
                # ⚠ 这里**不弹窗** —— 弹窗会打断操作，而且用户已经明确说过不想要。
                # 改成状态栏一行 + 日志里的原因说明，信息一样给到，但不挡路。
                if frames and rate <= 0.001:
                    self.status_var.set(
                        f"完成，但没检测到人（{frames} 帧，检出率 0%）—— 见运行日志")
                    self._append_log(
                        "\n⚠ 本次一帧都没检测到人（检出率 0%）。\n"
                        "   这不是程序故障：画面里没有人，计数只能是 0。\n"
                        "   按这几点检查一遍：\n"
                        "     1. 全身是否入镜（需要退到 2.5~3 米外）\n"
                        "     2. 光线是否够亮（太暗或逆光都检测不到）\n"
                        "     3. 摄像头是否选对了（可切「电脑摄像头」试试）\n"
                        "     4. 识别画面里有没有骨架线 —— 没有就说明确实没识别到人\n")
                elif frames and rate < 0.3:
                    self.status_var.set(f"完成，检出率偏低（{rate*100:.0f}%）")
                    self._append_log(
                        f"\n⚠ 检出率偏低（{rate*100:.0f}%）—— 人体经常不在画面里或拍不全，"
                        f"计数会被暂停。建议调整机位让全身稳定入镜。\n")
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
