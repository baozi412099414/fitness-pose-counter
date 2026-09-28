#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练管理 —— 选题 11：健身动作计数与姿态纠正

对应任务书的三个模块：
   7. 训练组与间歇管理：N 组 × M 次/组，组间休息倒计时 + 语音提示
   8. 训练历史与目标  ：JSON 持久化 + 每日目标达成度 + 每周趋势
  10. 个人档案与多用户：多用户切换，数据按用户分目录存放

设计原则：
  · **纯逻辑 + 文件存储**，不依赖摄像头 / MediaPipe —— 因此可以完整自动化测试，
    也不会因为「没有素材」而卡住。
  · 时间一律由调用方传入（now 参数），测试里可以精确模拟时间流逝，不用 sleep。
  · 对外返回的都是普通 dict / list，方便塞进 JSON 报告或喂给 UI。

为什么训练组要单独做状态机：组与组之间的「休息」是一段**没有动作发生**的时间，
计数状态机在那段时间里是空转的；间歇管理要能独立地告诉用户「现在该休息 / 该继续」。
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timedelta


# ══════════════════════════════════════════════════════════════
# 模块 7：训练组与间歇管理
# ══════════════════════════════════════════════════════════════
class SetManager:
    """
    把「总次数」切成若干组，并管理组间休息。

    典型用法（在计数循环里）：
        sets = SetManager(sets=3, reps_per_set=10, rest_seconds=30)
        ...
        for ev in sets.on_rep(count, now):
            say(ev["tip"])            # 组完成 / 休息结束 / 全部完成
        if sets.rest_remaining(now) > 0:
            hud 显示倒计时

    事件类型：
        set_done  某组做满（带组号）
        rest_end  休息结束，该开始下一组
        all_done  所有组完成
    """

    def __init__(self, sets=3, reps_per_set=10, rest_seconds=30.0):
        self.total_sets = max(1, int(sets))
        self.reps_per_set = max(1, int(reps_per_set))
        self.rest_seconds = max(0.0, float(rest_seconds))

        self.current_set = 1          # 正在做第几组（从 1 开始）
        self.reps_in_set = 0          # 本组已完成次数
        self.total_reps = 0           # 累计次数
        self.rest_until = 0.0         # 休息结束的时间戳（0 = 不在休息）
        self.finished = False
        self._last_seen = 0           # 上一次看到的「总计数」，用来识别新增

    # ----------------------------------------------------------
    def on_rep(self, count, now=None):
        """
        喂入「当前总计数」（realtime_pose 的 count），返回本次产生的事件列表。

        传总数而不是「+1」，是为了和外部计数器解耦：外部清零时这里也能跟着对齐。
        """
        now = time.time() if now is None else now
        events = []

        # 休息刚结束就先发一个提醒，且不把休息期间的计数算进来
        if self.rest_until and now >= self.rest_until:
            self.rest_until = 0.0
            events.append({"type": "rest_end", "set": self.current_set,
                           "tip": f"休息结束，开始第 {self.current_set} 组"})
            self._last_seen = count
            return events

        if self.rest_until:            # 还在休息，忽略计数
            self._last_seen = count
            return events

        if self.finished:
            self._last_seen = count
            return events

        delta = max(0, int(count) - self._last_seen)
        self._last_seen = int(count)
        if delta == 0:
            return events

        self.reps_in_set += delta
        self.total_reps += delta

        # 可能一次喂进来好多次（比如离线视频跑得比 UI 刷新快），要能连跳
        while self.reps_in_set >= self.reps_per_set and not self.finished:
            self.reps_in_set -= self.reps_per_set
            if self.current_set >= self.total_sets:
                self.finished = True
                events.append({"type": "all_done", "total_reps": self.total_reps,
                               "tip": f"全部完成，共 {self.total_reps} 次"})
                self.reps_in_set = 0
                break
            events.append({"type": "set_done", "set": self.current_set,
                           "total_sets": self.total_sets,
                           "tip": f"第 {self.current_set} 组完成"})
            self.current_set += 1
            if self.rest_seconds > 0:
                self.rest_until = now + self.rest_seconds
                events.append({"type": "rest_start", "seconds": self.rest_seconds,
                               "tip": f"休息 {int(self.rest_seconds)} 秒"})
                break
        return events

    # ----------------------------------------------------------
    def rest_remaining(self, now=None):
        """还剩多少秒休息（不在休息返回 0）。"""
        now = time.time() if now is None else now
        return max(0.0, self.rest_until - now) if self.rest_until else 0.0

    def status(self, now=None):
        """给 HUD / UI 用的一份快照。"""
        now = time.time() if now is None else now
        return {
            "current_set": self.current_set,
            "total_sets": self.total_sets,
            "reps_in_set": self.reps_in_set,
            "reps_per_set": self.reps_per_set,
            "total_reps": self.total_reps,
            "rest_remaining": round(self.rest_remaining(now), 1),
            "finished": self.finished,
        }

    def reset(self):
        self.current_set = 1
        self.reps_in_set = 0
        self.total_reps = 0
        self.rest_until = 0.0
        self.finished = False
        self._last_seen = 0


# ══════════════════════════════════════════════════════════════
# 模块 10：个人档案与多用户
# ══════════════════════════════════════════════════════════════
class UserStore:
    """
    多用户管理：数据按 `data/users/<用户名>/` 分目录存放。

    目录结构：
        data/users/
          ├── 王文景/
          │     ├── profile.json    档案（名字、创建时间、身高体重可选）
          │     ├── history.json    训练历史
          │     └── goals.json      每日目标
          └── current.json          当前用户（全局一个）
    """

    def __init__(self, root=None):
        # 数据根目录：优先用传进来的，其次环境变量 FITNESS_DATA_DIR，
        # 最后才是默认的 data/users —— 测试里用环境变量隔离，不会污染真实数据。
        root = root or os.environ.get("FITNESS_DATA_DIR") or "data/users"
        self.root = str(root)
        os.makedirs(self.root, exist_ok=True)
        self._marker = os.path.join(self.root, "current.json")

    # ---------------- 用户 ----------------
    def list_users(self):
        if not os.path.isdir(self.root):
            return []
        return sorted(
            d for d in os.listdir(self.root)
            if os.path.isdir(os.path.join(self.root, d))
        )

    def create_user(self, name, height_cm=None, weight_kg=None):
        """创建用户（已存在就直接返回，不覆盖历史）。"""
        name = (name or "").strip()
        if not name:
            raise ValueError("用户名不能为空")
        d = self.user_dir(name)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "profile.json")
        if not os.path.exists(p):
            self._write_json(p, {
                "name": name,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "height_cm": height_cm,
                "weight_kg": weight_kg,
            })
        return self.profile(name)

    def profile(self, name):
        return self._read_json(os.path.join(self.user_dir(name), "profile.json"), {})

    def current_user(self, default="默认用户"):
        """当前用户；没有就自动建一个「默认用户」，保证程序永远有可用档案。"""
        cur = self._read_json(self._marker, {}).get("name")
        if cur and os.path.isdir(self.user_dir(cur)):
            return cur
        return self.create_user(default)["name"]

    def switch_user(self, name):
        self.create_user(name)
        self._write_json(self._marker, {"name": name})
        return name

    def delete_user(self, name):
        """
        删除用户及其**全部数据**（档案 / 历史 / 目标），不可恢复。

        返回 (是否删除成功, 说明文字)。两条保护规则：
          · 不允许删掉最后一个用户 —— 否则程序没有可用档案，`current_user()` 又要重建。
          · 删掉的正好是当前用户时，自动切到剩下任意一个用户，避免指向已删除目录。
        """
        name = (name or "").strip()
        if not name:
            return False, "用户名为空"
        users = self.list_users()
        if name not in users:
            return False, f"用户「{name}」不存在"
        if len(users) <= 1:
            return False, "只剩一个用户，不能删除（否则没有可用档案）"

        was_current = (self.current_user_or_none() == name)
        shutil.rmtree(self.user_dir(name), ignore_errors=True)

        if was_current:
            remaining = self.list_users()
            if remaining:
                self._write_json(self._marker, {"name": remaining[0]})
        return True, f"已删除用户「{name}」及其训练数据"

    def current_user_or_none(self):
        """当前用户名；没有或指向已删除目录时返回 None（不自动建用户）。"""
        cur = self._read_json(self._marker, {}).get("name")
        if cur and os.path.isdir(self.user_dir(cur)):
            return cur
        return None

    def user_dir(self, name):
        return os.path.join(self.root, str(name))

    # ---------------- 文件 ----------------
    @staticmethod
    def _read_json(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write_json(path, data):
        """原子写：先写临时文件再 replace，避免中途崩溃留下半个 JSON。"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


# ══════════════════════════════════════════════════════════════
# 模块 8：训练历史
# ══════════════════════════════════════════════════════════════
class History:
    """训练历史：追加记录 + 按天/周统计。"""

    def __init__(self, store: UserStore, user=None):
        self.store = store
        self.user = user or store.current_user()

    def _path(self):
        return os.path.join(self.store.user_dir(self.user), "history.json")

    def all_sessions(self):
        return self.store._read_json(self._path(), [])

    def add_session(self, action, reps, sets=None, errors=None,
                    duration_sec=None, source=None, when=None, score=None):
        """
        记一次训练。返回写入的那条记录。

        参数都保持宽松：`errors` 直接收 realtime_pose 报告里的那种
        `{"low_back": 6, ...}` 字典。
        `when` 可以指定时间（datetime），用于补录历史 / 造演示数据 / 测试。
        """
        when = when or datetime.now()
        rec = {
            "time": when.isoformat(timespec="seconds"),
            "date": when.strftime("%Y-%m-%d"),
            "action": action,
            "reps": int(reps),
            "sets": sets,
            "errors": errors or {},
            "duration_sec": round(float(duration_sec), 1) if duration_sec else None,
            "source": source,
            # 动作评分（0~100）；老记录可能没有这个字段，读取方要能容忍
            "score": round(float(score), 1) if score is not None else None,
        }
        data = self.all_sessions()
        data.append(rec)
        self.store._write_json(self._path(), data)
        return rec

    def sessions(self, action=None, since=None, until=None):
        """按动作 / 日期过滤。since/until 传 'YYYY-MM-DD'。"""
        out = []
        for r in self.all_sessions():
            if action and r.get("action") != action:
                continue
            d = r.get("date", "")
            if since and d < since:
                continue
            if until and d > until:
                continue
            out.append(r)
        return out

    def reps_on(self, date, action=None):
        """某一天（'YYYY-MM-DD'）的总次数。"""
        return sum(r["reps"] for r in self.sessions(action=action, since=date, until=date))

    def today_reps(self, action=None, now=None):
        d = (now or datetime.now()).strftime("%Y-%m-%d")
        return self.reps_on(d, action)

    def weekly_trend(self, action=None, weeks=4, now=None):
        """
        最近 N 周的总次数，返回 [{"week_start": "YYYY-MM-DD", "reps": N}, ...]
        （从最早的一周排到最近，方便直接画趋势图）
        """
        now = now or datetime.now()
        this_monday = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        out = []
        for i in range(weeks - 1, -1, -1):
            start = this_monday - timedelta(weeks=i)
            end = start + timedelta(days=6)
            reps = sum(r["reps"] for r in self.sessions(
                action=action,
                since=start.strftime("%Y-%m-%d"),
                until=end.strftime("%Y-%m-%d")))
            out.append({"week_start": start.strftime("%Y-%m-%d"), "reps": reps})
        return out

    def score_trend(self, action=None, days=14, now=None):
        """
        最近 N 天的**平均评分**，返回 [{"date": "YYYY-MM-DD", "score": 82.5 或 None}, ...]。
        没有分数的那些天返回 None（而不是 0），画图时自然断开，不会误导成「那天很差」。
        """
        now = now or datetime.now()
        out = []
        for i in range(days - 1, -1, -1):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            vals = [r["score"] for r in self.sessions(action=action, since=d, until=d)
                    if r.get("score") is not None]
            out.append({"date": d,
                        "score": round(sum(vals) / len(vals), 1) if vals else None})
        return out

    def avg_score(self, action=None, days=7, now=None):
        """最近 N 天的平均评分（没有数据返回 None）。"""
        vals = [x["score"] for x in self.score_trend(action, days, now) if x["score"] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def error_summary(self, action=None):
        """把所有记录里的错误统计合并，用于「我最常犯的错是什么」。"""
        agg = {}
        for r in self.sessions(action=action):
            for k, v in (r.get("errors") or {}).items():
                agg[k] = agg.get(k, 0) + int(v)
        return dict(sorted(agg.items(), key=lambda kv: -kv[1]))


# ══════════════════════════════════════════════════════════════
# 模块 8（续）：训练目标
# ══════════════════════════════════════════════════════════════
class Goals:
    """
    每日目标（按动作设）。存成 `{"pushup": 50, "squat": 60}`。
    单次性目标（例如「今晚做 30 个」）也支持：设成当天有效即可。
    """

    def __init__(self, store: UserStore, user=None):
        self.store = store
        self.user = user or store.current_user()

    def _path(self):
        return os.path.join(self.store.user_dir(self.user), "goals.json")

    def all_goals(self):
        return self.store._read_json(self._path(), {})

    def set_goal(self, action, daily_reps):
        g = self.all_goals()
        g[action] = int(daily_reps)
        self.store._write_json(self._path(), g)
        return g[action]

    def get_goal(self, action):
        return int(self.all_goals().get(action, 0) or 0)

    def clear_goal(self, action):
        g = self.all_goals()
        g.pop(action, None)
        self.store._write_json(self._path(), g)

    def progress(self, action, history: History, now=None):
        """
        返回今日达成情况：
        {"action", "done", "target", "ratio", "reached", "remaining"}
        `target` 为 0 表示没设目标，此时 ratio 记 0、reached 记 False。
        """
        done = history.today_reps(action, now=now)
        target = self.get_goal(action)
        ratio = (done / target) if target else 0.0
        return {
            "action": action,
            "done": done,
            "target": target,
            "ratio": round(min(ratio, 1.0), 3),
            "reached": bool(target) and done >= target,
            "remaining": max(0, target - done),
        }

    def all_progress(self, history: History, now=None):
        return {a: self.progress(a, history, now=now) for a in self.all_goals()}
