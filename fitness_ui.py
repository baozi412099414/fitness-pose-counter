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


ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "configs"
REFERENCE_DIR = ROOT / "captures/reference"
REFERENCE_EXTS = (".ogv", ".webm", ".mp4", ".mov", ".ogg", ".avi", ".mkv")
SOURCE_TYPES = ("摄像头", "选择本地视频", "内置参考视频")
PHONE_CAMERA_INDEX = 1
COMPUTER_CAMERA_INDEX = 0


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
        self.root.geometry("820x690")
        self.root.minsize(720, 560)
        # 识别窗口启动后可能抢走 macOS 前台焦点；测试控制台必须仍可点击。
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
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
        self.rate_var = tk.StringVar(value="--")
        self.errors_var = tk.StringVar(value="暂无")

        # macOS 上「非活动窗口的第一次点击只激活窗口、不传给按钮」，
        # 而识别子进程启动会抢走焦点 → 表现就是「按钮不灵敏、要点两次」。
        # 解决：鼠标只要在控制台里移动，就把键盘焦点抢回来（每秒最多一次）。
        self._last_focus_grab = 0.0
        self.root.bind("<Motion>", self._maybe_grab_focus, add="+")
        self.root.bind("<Enter>", self._maybe_grab_focus, add="+")

        self._build()
        self._sync_source()
        self._sync_goal()
        self._refresh_stats()
        self.root.after(100, self._poll_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="健身动作识别测试台",
                  font=("Helvetica", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="选择动作后直接开始即可；默认使用摄像头，参考视频仅用于调试。",
                  foreground="#555").pack(anchor="w", pady=(4, 16))

        form = ttk.LabelFrame(outer, text="测试设置", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="动作").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        action_frame = ttk.Frame(form)
        action_frame.grid(row=0, column=1, columnspan=3, sticky="ew", pady=6)
        for col, (name, _aid) in enumerate(self.actions):
            action_frame.columnconfigure(col, weight=1)
            tk.Radiobutton(
                action_frame, text=name, variable=self.action_var, value=name,
                command=self._sync_source, indicatoron=False, padx=18, pady=8,
                selectcolor="#bfe3ff",
            ).grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))

        ttk.Label(form, text="输入").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        source_frame = ttk.Frame(form)
        source_frame.grid(row=1, column=1, columnspan=3, sticky="w", pady=6)
        for col, name in enumerate(SOURCE_TYPES):
            tk.Radiobutton(
                source_frame, text=name, variable=self.source_type_var, value=name,
                command=self._sync_source,
            ).grid(row=0, column=col, sticky="w", padx=(0, 14))

        ttk.Label(form, text="视频/设备").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.file_entry = ttk.Entry(form, textvariable=self.file_var)
        self.file_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
        self.browse_btn = ttk.Button(form, text="选择视频…", command=self._browse)
        self.browse_btn.grid(row=2, column=3, padx=(8, 0), pady=6)
        self.camera_frame = ttk.Frame(form)
        self.camera_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=6)
        tk.Radiobutton(self.camera_frame,
                       text=f"手机摄像头（设备 {PHONE_CAMERA_INDEX}，默认）",
                       variable=self.camera_var,
                       value=str(PHONE_CAMERA_INDEX)).pack(side="left")
        tk.Radiobutton(self.camera_frame,
                       text=f"电脑摄像头（设备 {COMPUTER_CAMERA_INDEX}）",
                       variable=self.camera_var,
                       value=str(COMPUTER_CAMERA_INDEX)).pack(side="left", padx=(12, 0))
        tk.Radiobutton(self.camera_frame, text="其他编号",
                       variable=self.camera_var, value="custom").pack(side="left", padx=(12, 4))
        self.camera_box = ttk.Spinbox(self.camera_frame, from_=0, to=9, width=4,
                                      textvariable=self.custom_camera_var)
        self.camera_box.pack(side="left")

        ttk.Checkbutton(form, text="开启中文语音提醒和报数",
                        variable=self.voice_var).grid(row=3, column=1, columnspan=3,
                                                      sticky="w", pady=6)

        # ---- 训练管理（任务书模块 7 训练组 / 8 历史与目标 / 10 多用户）----
        train = ttk.LabelFrame(outer, text="训练管理（多用户 · 分组间歇 · 目标）", padding=12)
        train.pack(fill="x", pady=(12, 0))

        ttk.Label(train, text="用户").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.user_box = ttk.Combobox(train, textvariable=self.user_var,
                                     values=self.store.list_users(), width=14)
        self.user_box.grid(row=0, column=1, sticky="w", pady=5)
        ttk.Button(train, text="切换", width=6, command=self._switch_user).grid(
            row=0, column=2, sticky="w", padx=6, pady=5)
        ttk.Button(train, text="新建用户…", width=11, command=self._new_user).grid(
            row=0, column=3, sticky="w", pady=5)
        ttk.Button(train, text="删除用户…", width=11, command=self._delete_user).grid(
            row=0, column=4, sticky="w", padx=(6, 0), pady=5)
        ttk.Label(train, textvariable=self.goal_status_var,
                  foreground="#2f80ed").grid(row=0, column=5, sticky="w", padx=12, pady=5)

        ttk.Label(train, text="分组").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        gframe = ttk.Frame(train)
        gframe.grid(row=1, column=1, columnspan=4, sticky="w", pady=5)
        ttk.Checkbutton(gframe, text="启用分组间歇", variable=self.group_on_var).pack(side="left")
        ttk.Spinbox(gframe, from_=1, to=20, width=4,
                    textvariable=self.sets_var).pack(side="left", padx=(10, 2))
        ttk.Label(gframe, text="组 ×").pack(side="left")
        ttk.Spinbox(gframe, from_=1, to=100, width=4,
                    textvariable=self.reps_per_set_var).pack(side="left", padx=(6, 2))
        ttk.Label(gframe, text="次，组间休息").pack(side="left")
        ttk.Spinbox(gframe, from_=0, to=600, width=5,
                    textvariable=self.rest_var).pack(side="left", padx=(6, 2))
        ttk.Label(gframe, text="秒").pack(side="left")

        ttk.Label(train, text="每日目标").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        tframe = ttk.Frame(train)
        tframe.grid(row=2, column=1, columnspan=4, sticky="w", pady=5)
        ttk.Spinbox(tframe, from_=0, to=999, width=5,
                    textvariable=self.goal_var).pack(side="left")
        ttk.Label(tframe, text="次").pack(side="left", padx=(4, 10))
        ttk.Button(tframe, text="保存目标", width=10,
                   command=self._save_goal).pack(side="left")
        ttk.Button(tframe, text="查看趋势图", width=12,
                   command=self._show_trend).pack(side="left", padx=10)

        buttons = tk.Frame(outer)
        buttons.pack(fill="x", pady=14)
        button_style = {
            "font": ("Helvetica", 14, "bold"), "width": 9, "height": 2,
            "relief": "raised", "bd": 2, "highlightthickness": 1,
            "takefocus": True,
        }
        self.start_btn = tk.Button(buttons, text="开始测试", command=self.start,
                                   bg="#2f80ed", fg="white", activebackground="#56a0ff",
                                   **button_style)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = tk.Button(buttons, text="停止", command=self.stop,
                                  bg="#eb5757", fg="white", activebackground="#ff7777",
                                  state="disabled", **button_style)
        self.stop_btn.pack(side="left", padx=8)
        self.reset_btn = tk.Button(buttons, text="清零", command=self.reset,
                                   bg="#f2c94c", fg="#222", activebackground="#ffe27a",
                                   state="disabled", **button_style)
        self.reset_btn.pack(side="left", padx=8)
        self.restart_btn = tk.Button(buttons, text="重新启动", command=self.restart,
                                     bg="#27ae60", fg="white", activebackground="#49d17b",
                                     state="disabled", **button_style)
        self.restart_btn.pack(side="left", padx=8)
        ttk.Label(buttons, textvariable=self.status_var).pack(side="right")

        # 鼠标点不到时仍有确定的操作入口：F5 开始、F6 停止、F7 清零、F8 重启。
        self.root.bind("<F5>", lambda _e: self.start())
        self.root.bind("<F6>", lambda _e: self.stop())
        self.root.bind("<F7>", lambda _e: self.reset())
        self.root.bind("<F8>", lambda _e: self.restart())
        self.root.bind("<Escape>", lambda _e: self.stop())

        result = ttk.LabelFrame(outer, text="最近一次测试结果", padding=12)
        result.pack(fill="x", pady=(0, 12))
        for col in range(3):
            result.columnconfigure(col, weight=1)
        ttk.Label(result, text="次数", foreground="#666").grid(row=0, column=0)
        ttk.Label(result, text="关键点检出率", foreground="#666").grid(row=0, column=1)
        ttk.Label(result, text="错误事件", foreground="#666").grid(row=0, column=2)
        ttk.Label(result, textvariable=self.reps_var,
                  font=("Helvetica", 20, "bold")).grid(row=1, column=0, pady=5)
        ttk.Label(result, textvariable=self.rate_var,
                  font=("Helvetica", 16, "bold")).grid(row=1, column=1, pady=5)
        ttk.Label(result, textvariable=self.errors_var, wraplength=260,
                  justify="center").grid(row=1, column=2, pady=5)

        # ---- 历史与统计：全部只读本地文件，不需要摄像头 ----
        stats = ttk.LabelFrame(outer, text="历史与统计（不依赖摄像头）", padding=12)
        stats.pack(fill="x", pady=(0, 12))
        stats.columnconfigure(1, weight=1)

        ttk.Label(stats, text="目标进度").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.goal_bar = ttk.Progressbar(stats, orient="horizontal", length=220,
                                        mode="determinate", maximum=100)
        self.goal_bar.grid(row=0, column=1, sticky="w")
        ttk.Label(stats, textvariable=self.progress_var,
                  foreground="#2f80ed").grid(row=0, column=2, sticky="w", padx=10)

        ttk.Label(stats, text="最常犯的错").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(stats, textvariable=self.top_errors_var, wraplength=440,
                  foreground="#c0392b", justify="left").grid(
            row=1, column=1, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(stats, text="历史报告").grid(row=2, column=0, sticky="nw", pady=(8, 0))
        list_frame = ttk.Frame(stats)
        list_frame.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        self.report_list = tk.Listbox(list_frame, height=5, activestyle="dotbox",
                                      font=("Menlo", 10))
        self.report_list.pack(side="left", fill="x", expand=True)
        rscroll = ttk.Scrollbar(list_frame, orient="vertical",
                                command=self.report_list.yview)
        self.report_list.configure(yscrollcommand=rscroll.set)
        rscroll.pack(side="right", fill="y")
        rbtns = ttk.Frame(stats)
        rbtns.grid(row=2, column=2, sticky="nw", padx=10, pady=(8, 0))
        ttk.Button(rbtns, text="刷新", width=10,
                   command=self._refresh_stats).pack(pady=2)
        ttk.Button(rbtns, text="查看详情", width=10,
                   command=self._show_report_detail).pack(pady=2)
        ttk.Button(rbtns, text="打开目录", width=10,
                   command=self._open_reports_dir).pack(pady=2)
        ttk.Button(rbtns, text="校验配置", width=10,
                   command=self._validate_configs).pack(pady=2)

        log_box = ttk.LabelFrame(outer, text="运行日志", padding=8)
        log_box.pack(fill="both", expand=True)
        self.log = tk.Text(log_box, height=13, wrap="word", state="disabled",
                           background="#151515", foreground="#e7e7e7",
                           insertbackground="white")
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

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
            messagebox.showinfo("未选择", "先在列表里点一条历史报告。")
            return
        idx = sel[0]
        if idx >= len(self._report_paths):
            return
        p = self._report_paths[idx]
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("读取失败", f"{p.name}\n{e}")
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
        messagebox.showinfo("报告详情", "\n".join(lines))

    def _validate_configs(self):
        """
        校验 configs/ 下所有动作配置，结果显示在日志区。

        这是「自定义动作」的第一道防线：写错关键点编号、阈值方向、check 名字
        这类问题在运行前就能发现，不用架好摄像头做完动作才发现不生效。
        """
        from validate_config import validate_file
        files = sorted(CONFIG_DIR.glob("*.json"))
        if not files:
            messagebox.showwarning("没有配置", f"{CONFIG_DIR} 下没有 json 文件")
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
            messagebox.showwarning("配置有问题", summary + "\n详情见下方运行日志。")

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
            messagebox.showerror("打开失败", str(e))

    # ---------------- 窗口焦点（解决 macOS 点击不灵敏）----------------
    def _grab_focus(self):
        """把键盘焦点抢回控制台；抢不到也不影响功能。"""
        try:
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _maybe_grab_focus(self, _event=None):
        """鼠标在控制台里活动时抢焦点，节流到每秒一次，避免过于频繁。"""
        now = time.time()
        if now - self._last_focus_grab < 1.0:
            return
        self._last_focus_grab = now
        self._grab_focus()

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
            messagebox.showwarning("未选择用户", "请先在下拉框里选择要删除的用户。")
            return
        if not messagebox.askyesno(
                "确认删除",
                f"确定要删除用户「{name}」吗？\n\n"
                f"该用户的档案、训练历史和目标都会被一起删除，且无法恢复。"):
            return
        ok, msg = self.store.delete_user(name)
        if not ok:
            messagebox.showwarning("无法删除", msg)
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

    def _save_goal(self):
        from training_manager import Goals
        try:
            value = int(float(self.goal_var.get() or 0))
        except ValueError:
            messagebox.showerror("目标无效", "每日目标要填整数次数")
            return
        Goals(self.store, self.store.current_user()).set_goal(self.action_id(), value)
        self._sync_goal()
        self.status_var.set(f"已保存目标：每天 {value} 次")

    def _show_trend(self):
        """生成并弹出趋势图（调用 plot_trend.py）。"""
        from training_manager import History
        user = self.store.current_user()
        if not History(self.store, user).all_sessions():
            messagebox.showinfo("暂无数据",
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
            messagebox.showerror("生成失败", str(e))

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
        path = filedialog.askopenfilename(
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
            messagebox.showerror("无法开始", str(exc))
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
            messagebox.showerror("启动失败", str(exc))
            return

        self.status_var.set("运行中")
        self.start_btn.configure(state="disabled", relief="sunken")
        self.stop_btn.configure(state="normal", relief="raised")
        self.reset_btn.configure(state="normal", relief="raised")
        self.restart_btn.configure(state="normal", relief="raised")
        self.root.lift()
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        # 识别窗口启动后会抢走键盘焦点，隔一会儿把控制台抢回来，
        # 否则 macOS 上按钮要点两次才生效（第一次只用来激活窗口）。
        self.root.after(1200, self._grab_focus)
        self.root.after(2800, self._grab_focus)
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
        self.start_btn.configure(state="normal", relief="raised")
        self.stop_btn.configure(state="disabled", relief="sunken")
        self.reset_btn.configure(state="disabled", relief="sunken")
        self.restart_btn.configure(state="disabled", relief="sunken")
        if self.report_path and self.report_path.is_file():
            try:
                data = json.loads(self.report_path.read_text(encoding="utf-8"))
                self.reps_var.set(str(data.get("reps", 0)))
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
