#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个动作的简易测试控制台。

识别画面沿用 realtime_pose.py 的 OpenCV 窗口；本窗口负责选择动作/输入、
启动与停止、显示日志和读取测试摘要。将姿态模型放在独立子进程里，即使底层
MediaPipe/Metal 初始化失败，控制台本身也不会一起崩溃。
"""

import json
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent
ACTION_IDS = {"俯卧撑": "pushup", "深蹲": "squat", "开合跳": "jumping_jack"}
REFERENCE_VIDEOS = {
    "俯卧撑": ROOT / "captures/reference/pushup_standard.ogv",
    "深蹲": ROOT / "captures/reference/squat_standard.webm",
    "开合跳": ROOT / "captures/reference/jumping_jack_standard.ogg",
}
SOURCE_TYPES = ("摄像头", "选择本地视频", "内置参考视频")
PHONE_CAMERA_INDEX = 1
COMPUTER_CAMERA_INDEX = 0


def build_command(action_name, source_type, source_value, voice, report_path,
                  control_path=None):
    """生成参数列表；单独保留为纯函数，便于无 GUI 自动测试。"""
    action_id = ACTION_IDS[action_name]
    cmd = [sys.executable, "-u", str(ROOT / "realtime_pose.py"),
           "--action", action_id, "--report", str(report_path)]
    if source_type == "摄像头":
        cmd += ["--cam", str(int(source_value))]
    else:
        cmd += ["--src", str(source_value)]
    if not voice:
        cmd.append("--no-voice")
    if control_path:
        cmd += ["--control-file", str(control_path)]
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

        self.action_var = tk.StringVar(value="深蹲")
        # 日常使用默认直接开摄像头；参考视频只是调试时的可选输入。
        self.source_type_var = tk.StringVar(value="摄像头")
        self.file_var = tk.StringVar()
        # 本项目已实测 iPhone 连续互通相机为设备 1、Mac 内置摄像头为设备 0。
        self.camera_var = tk.StringVar(value=str(PHONE_CAMERA_INDEX))
        self.custom_camera_var = tk.StringVar(value="2")
        self.voice_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="准备就绪")
        self.reps_var = tk.StringVar(value="0")
        self.rate_var = tk.StringVar(value="--")
        self.errors_var = tk.StringVar(value="暂无")

        self._build()
        self._sync_source()
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
        for col, name in enumerate(ACTION_IDS):
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

        log_box = ttk.LabelFrame(outer, text="运行日志", padding=8)
        log_box.pack(fill="both", expand=True)
        self.log = tk.Text(log_box, height=13, wrap="word", state="disabled",
                           background="#151515", foreground="#e7e7e7",
                           insertbackground="white")
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _sync_source(self):
        source_type = self.source_type_var.get()
        camera = source_type == "摄像头"
        if source_type == "内置参考视频":
            self.file_var.set(str(REFERENCE_VIDEOS[self.action_var.get()]))
        self.camera_frame.grid() if camera else self.camera_frame.grid_remove()
        self.file_entry.grid_remove() if camera else self.file_entry.grid()
        self.browse_btn.grid_remove() if camera else self.browse_btn.grid()
        self.browse_btn.configure(state="normal" if source_type == "选择本地视频" else "disabled")
        self.file_entry.configure(state="normal" if source_type == "选择本地视频" else "readonly")

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
        self.report_path = report_dir / f"{ACTION_IDS[self.action_var.get()]}-{stamp}.json"
        self.control_path = report_dir / f"control-{ACTION_IDS[self.action_var.get()]}-{stamp}.json"
        cmd = build_command(self.action_var.get(), self.source_type_var.get(), source_value,
                            self.voice_var.get(), self.report_path, self.control_path)
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
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "log":
                    self._append_log(value)
                    match = re.search(r"第\s*(\d+)\s*次", value)
                    if match:
                        self.reps_var.set(match.group(1))
                else:
                    self._finished(value)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)

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
        if self.restart_pending:
            self.restart_pending = False
            self.root.after(250, self.start)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
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
