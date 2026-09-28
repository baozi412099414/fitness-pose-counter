#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练趋势图 —— 选题 11：健身动作计数与姿态纠正（任务书模块 8：训练历史与目标）

把 `data/users/<用户>/history.json` 里的训练记录画成三张图：
    左：最近 N 周每周总次数（柱状）+ 周目标线
    中：最近 N 天每日次数（折线）+ 每日目标线
    右：最近 N 天**每日平均动作评分**（折线）+ 及格线 60 / 良好线 85

【两处共用同一套绘图逻辑】
`build_axes()` 被两个地方调用：
  · 本文件的命令行入口（用 pyplot 建 figure）
  · `fitness_ui.py` 的内嵌画布（用 matplotlib 的 Figure + TkAgg 后端）
抽出来的原因很实际：如果两边各画各的，改了一处忘了另一处就会不一致。

用法：
    .venv/bin/python plot_trend.py                                # 默认用户、全部动作
    .venv/bin/python plot_trend.py --user 王文景 --action squat
    .venv/bin/python plot_trend.py --out captures/trend.png --no-show
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

# matplotlib 默认把字体缓存写到 ~/.matplotlib；这台机器上该目录不可写，
# 于是**每次启动都要重建字体缓存**（慢）并刷一堆警告。
# 指到项目内的目录，缓存持久化，启动也干净。
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".matplotlib_cache"))

import matplotlib

# 没有图形环境（或在容器里跑测试）时用 Agg，只存文件不弹窗。
# 注意必须在 import pyplot **之前**决定后端。
if "--no-show" in sys.argv or not os.environ.get("DISPLAY"):
    try:
        matplotlib.use("Agg")
    except Exception:
        pass

import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib import font_manager                  # noqa: E402

from training_manager import UserStore, History, Goals   # noqa: E402

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
    """最近 N 天的每日次数，返回 (日期标签列表, 次数列表)。"""
    now = now or datetime.now()
    x, y = [], []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        x.append(d[5:])                          # 只显示 MM-DD
        y.append(hist.reps_on(d, action=action))
    return x, y


def build_axes(fig, axes, hist, goals, action=None, weeks=8, days=14):
    """
    把三张子图都画到给定的 `axes` 上，并设置总标题。

    `axes` 需要是长度 ≥ 3 的序列。命令行脚本和 UI 内嵌画布都调这个函数，
    保证两处呈现完全一致。返回「最常犯的错」文本，方便调用方另外展示。
    """
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

    # ---- 图一：每周次数 ----
    ax = axes[0]
    bars = ax.bar(wk_labels, wk_values, color="#4C9F70", width=0.6)
    ax.set_title(f"每周训练次数（最近 {weeks} 周）", fontsize=12)
    ax.set_ylabel("次数")
    ax.grid(axis="y", alpha=0.3)
    if daily_goal:
        ax.axhline(daily_goal * 7, color="#E07A5F", linestyle="--", linewidth=1.4,
                   label=f"周目标 {daily_goal * 7}")
        ax.legend(fontsize=9)
    for b, v in zip(bars, wk_values):
        if v:
            ax.text(b.get_x() + b.get_width() / 2, v, str(v),
                    ha="center", va="bottom", fontsize=8)

    # ---- 图二：每日次数 ----
    ax = axes[1]
    ax.plot(d_labels, d_values, marker="o", color="#3D7EA6", linewidth=2, markersize=4)
    ax.set_title(f"每日训练次数（最近 {days} 天）", fontsize=12)
    ax.set_ylabel("次数")
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=60, labelsize=7)
    if daily_goal:
        ax.axhline(daily_goal, color="#E07A5F", linestyle="--", linewidth=1.4,
                   label=f"每日目标 {daily_goal}")
        ax.legend(fontsize=9)

    # ---- 图三：每日平均动作评分（0~100）----
    ax = axes[2]
    st = hist.score_trend(action=action, days=days)
    sx = [t["date"][5:] for t in st]
    sy = [t["score"] for t in st]
    # 没有数据的点保持 None —— matplotlib 会自动断开，正好表示「那天没练」，
    # 比补 0 分诚实得多（补 0 会看起来像「那天做得极差」）。
    ax.plot(sx, sy, marker="o", color="#B5651D", linewidth=2, markersize=4)
    ax.axhline(60, color="#E07A5F", linestyle="--", linewidth=1.3, label="及格线 60")
    ax.axhline(85, color="#4C9F70", linestyle=":", linewidth=1.3, label="良好线 85")
    ax.set_ylim(0, 105)
    ax.set_title(f"每日动作评分（最近 {days} 天）", fontsize=12)
    ax.set_ylabel("评分")
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=60, labelsize=7)
    ax.legend(fontsize=9, loc="lower right")

    # ---- 总标题：把关键结论直接写上去 ----
    total = sum(v for v in d_values)
    errs = hist.error_summary(action=action)
    top = "、".join(f"{k}×{v}" for k, v in list(errs.items())[:3]) or "无记录"
    avg = hist.avg_score(action=action, days=days)
    avg_txt = f"；近期平均评分 {avg} 分" if avg is not None else ""
    fig.suptitle(f"训练趋势 —— 用户：{hist.user}　动作：{action or '全部'}　"
                 f"（近期共 {total} 次{avg_txt}；最常出现的提示：{top}）", fontsize=12)
    return top


def make_figure(hist, goals, action=None, weeks=8, days=14, figsize=(17.5, 4.6)):
    """命令行用：新建一个完整 figure（UI 内嵌不用这个，它自己管 Figure）。"""
    fig, axes = plt.subplots(1, 3, figsize=figsize)
    build_axes(fig, axes, hist, goals, action=action, weeks=weeks, days=days)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def plot(user, action=None, weeks=8, days=14, out=None, show=True):
    """命令行入口：画图 + 可选保存 / 弹窗。返回图片路径（没数据时返回 None）。"""
    store = UserStore()
    hist = History(store, user)
    if not hist.all_sessions():
        print(f"用户「{user}」下还没有训练记录，先跑一次训练吧。")
        return None

    fig = make_figure(hist, Goals(store, user), action, weeks, days)

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
    hist = History(store, user)
    actions = sorted({s["action"] for s in hist.all_sessions()})
    print(f"用户：{user}　可用动作记录：" +
          ("、".join(f"{a}×{len(hist.sessions(action=a))}" for a in actions) or "（暂无）"))
    plot(user, args.action, weeks=args.weeks, days=args.days,
         out=args.out, show=not args.no_show)


if __name__ == "__main__":
    main()
