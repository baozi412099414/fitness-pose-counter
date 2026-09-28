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
SOURCE_TYPES = ("内置参考视频", "选择本地视频", "摄像头")


def build_command(action_name, source_type, source_value, voice, report_path):
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
    return cmd


class FitnessTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("健身动作识别测试台")
        self.root.geometry("820x650")
        self.root.minsize(720, 560)
        self.process = None
        self.report_path = None
        self.messages = queue.Queue()
        self.restart_pending = False

        self.action_var = tk.StringVar(value="深蹲")
        self.source_type_var = tk.StringVar(value="内置参考视频")
        self.file_var = tk.StringVar()
        self.camera_var = tk.StringVar(value="0")
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
        ttk.Label(outer, text="分别选择俯卧撑、深蹲或开合跳；识别画面会在独立窗口显示。",
                  foreground="#555").pack(anchor="w", pady=(4, 16))

        form = ttk.LabelFrame(outer, text="测试设置", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="动作").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        action = ttk.Combobox(form, textvariable=self.action_var,
                              values=tuple(ACTION_IDS), state="readonly", width=18)
        action.grid(row=0, column=1, sticky="w", pady=6)
        action.bind("<<ComboboxSelected>>", lambda _e: self._sync_source())

        ttk.Label(form, text="输入").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        source = ttk.Combobox(form, textvariable=self.source_type_var,
                              values=SOURCE_TYPES, state="readonly", width=18)
        source.grid(row=1, column=1, sticky="w", pady=6)
        source.bind("<<ComboboxSelected>>", lambda _e: self._sync_source())

        ttk.Label(form, text="视频/设备").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.file_entry = ttk.Entry(form, textvariable=self.file_var)
        self.file_entry.grid(row=2, column=1, sticky="ew", pady=6)
        self.browse_btn = ttk.Button(form, text="选择视频…", command=self._browse)
        self.browse_btn.grid(row=2, column=2, padx=(8, 0), pady=6)
        self.camera_box = ttk.Spinbox(form, from_=0, to=9, width=6,
                                      textvariable=self.camera_var)
        self.camera_box.grid(row=2, column=1, sticky="w", pady=6)

        ttk.Checkbutton(form, text="开启中文语音提醒和报数",
                        variable=self.voice_var).grid(row=3, column=1, sticky="w", pady=6)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=14)
        self.start_btn = ttk.Button(buttons, text="开始测试", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="停止", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.restart_btn = ttk.Button(buttons, text="清零并重启", command=self.restart,
                                      state="disabled")
        self.restart_btn.pack(side="left")
        ttk.Label(buttons, textvariable=self.status_var).pack(side="right")

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
        elif camera:
            self.file_var.set("")
        self.camera_box.grid() if camera else self.camera_box.grid_remove()
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
                return int(self.camera_var.get())
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
        cmd = build_command(self.action_var.get(), self.source_type_var.get(), source_value,
                            self.voice_var.get(), self.report_path)
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
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.restart_btn.configure(state="normal")
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
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.restart_btn.configure(state="disabled")
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
