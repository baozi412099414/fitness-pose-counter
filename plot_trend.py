#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练趋势图 —— 选题 11：健身动作计数与姿态纠正（任务书模块 8：训练历史与目标）

把 `data/users/<用户>/history.json` 里的训练记录画成图：
    左图：最近 N 周每周总次数（柱状）+ 每周目标线
    右图：最近 14 天每日次数（折线）+ 每日目标线
底部另附「最常犯的错误」排行，方便看出该纠正哪个动作环节。

用法：
    .venv/bin/python plot_trend.py                                # 默认用户、全部动作
    .venv/bin/python plot_trend.py --user 王文景 --action squat
    .venv/bin/python plot_trend.py --out captures/trend.png --no-show
"""

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

import matplotlib
if "--no-show" in sys.argv or not os.environ.get("DISPLAY"):
    # 没有图形环境（或明确要求不弹窗）时用 Agg，只存文件
    try:
        matplotlib.use("Agg")
    except Exception:
        pass
import matplotlib.pyplot as plt
from matplotlib import font_manager

from training_manager import UserStore, History, Goals

# 中文字体：不设置的话图上中文会变成方框
for _name in ("STHeiti", "Heiti TC", "Hiragino Sans GB", "PingFang SC",
              "Arial Unicode MS", "Songti SC"):
    try:
        font_manager.findfont(_name, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [_name]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False      # 负号正常显示


def daily_series(hist, action, days=14, now=None):
    """最近 N 天的每日次数，返回 (日期列表, 次数列表)。"""
    now = now or datetime.now()
    x, y = [], []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        x.append(d[5:])                          # 只显示 MM-DD
        y.append(hist.reps_on(d, action=action))
    return x, y


def plot(user, action=None, weeks=8, days=14, out=None, show=True):
    store = UserStore()
    hist = History(store, user)
    goals = Goals(store, user)

    sessions = hist.sessions(action=action)
    if not sessions:
        print(f"用户「{user}」下没有{'该动作的' if action else ''}训练记录，先跑一次训练吧。")
        return None

    weekly = hist.weekly_trend(action=action, weeks=weeks)
    wk_labels = [w["week_start"][5:] for w in weekly]
    wk_values = [w["reps"] for w in weekly]

    d_labels, d_values = daily_series(hist, action, days=days)

    # 目标线：按动作设的目标（不区分动作时取各动作目标之和作参考）
    if action:
        daily_goal = goals.get_goal(action)
    else:
        allg = goals.all_goals()
        daily_goal = sum(allg.values()) if allg else 0

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    # ---- 左：每周次数 ----
    ax = axes[0]
    bars = ax.bar(wk_labels, wk_values, color="#4C9F70", width=0.6)
    ax.set_title(f"每周训练次数（最近 {weeks} 周）", fontsize=13)
    ax.set_ylabel("次数")
    ax.grid(axis="y", alpha=0.3)
    if daily_goal:
        ax.axhline(daily_goal * 7, color="#E07A5F", linestyle="--", linewidth=1.4,
                   label=f"周目标 {daily_goal * 7}")
        ax.legend()
    for b, v in zip(bars, wk_values):
        if v:
            ax.text(b.get_x() + b.get_width() / 2, v, str(v),
                    ha="center", va="bottom", fontsize=9)

    # ---- 右：每日次数 ----
    ax = axes[1]
    ax.plot(d_labels, d_values, marker="o", color="#3D7EA6", linewidth=2)
    ax.set_title(f"每日训练次数（最近 {days} 天）", fontsize=13)
    ax.set_ylabel("次数")
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=60, labelsize=8)
    if daily_goal:
        ax.axhline(daily_goal, color="#E07A5F", linestyle="--", linewidth=1.4,
                   label=f"每日目标 {daily_goal}")
        ax.legend()

    # ---- 标题 + 最常犯的错 ----
    total = sum(v for v in d_values)
    errs = hist.error_summary(action=action)
    top = "、".join(f"{k}×{v}" for k, v in list(errs.items())[:3]) or "无记录"
    fig.suptitle(f"训练趋势 —— 用户：{user}　动作：{action or '全部'}　"
                 f"（近期共 {total} 次；最常出现的提示：{top}）", fontsize=13)

    fig.tight_layout(rect=(0, 0, 1, 0.94))

    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        fig.savefig(out, dpi=130)
        print(f"已保存趋势图：{out}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None, help="用户名（不传用当前用户）")
    ap.add_argument("--action", default=None, help="只看某个动作（squat/pushup/jumping_jack）")
    ap.add_argument("--weeks", type=int, default=8, help="周趋势显示多少周")
    ap.add_argument("--days", type=int, default=14, help="日趋势显示多少天")
    ap.add_argument("--out", default=None, help="保存图片路径（不传则只弹窗）")
    ap.add_argument("--no-show", action="store_true", help="不弹窗，只保存")
    args = ap.parse_args()

    store = UserStore()
    user = args.user or store.current_user()
    print(f"用户：{user}　可用动作记录：" +
          (", ".join(f"{a}×{len(hist_sessions)}" for a, hist_sessions in
                     ((a, History(store, user).sessions(action=a))
                      for a in {s['action'] for s in History(store, user).all_sessions()}))
           or "（暂无）"))
    plot(user, args.action, weeks=args.weeks, days=args.days,
         out=args.out, show=not args.no_show)


if __name__ == "__main__":
    main()
