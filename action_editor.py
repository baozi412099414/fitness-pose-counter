#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动作编辑器：在界面上填表新建/修改一个动作，**不用碰 JSON**

【为什么要有这个】
「新增动作只需写一份配置、不必改代码」是本选题的核心考点。但让使用者
（尤其是非程序员）直接去写 JSON 有个现实门槛：

  · 关键点编号是 0~32 的数字，「左膝是 25 还是 26」根本记不住；
  · `lo` / `hi` / `first` 这些字段名不知道什么意思；
  · 阈值方向写反了也不报错，只是「怎么都不计数」。

所以这里做两件事：
  ① **把关键点编号翻译成人话** —— 选「左膝角（髋-膝-踝）」，程序自己填 23,25,27；
  ② **把字段名翻译成人话** —— 「信号降到多少算开始」而不是「lo 阈值」。

界面表单在 fitness_ui.py 里（`ActionEditor`），本文件只放**纯数据与纯函数**，
这样能脱离图形界面做自动化测试。
"""

import json
import re
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# 关键点编号 → 可用于「测量部位」的人体组合
# ══════════════════════════════════════════════════════════════════
# 每个预设给出友好的中文名和对应的关键点编号，使用者从下拉框里选就行。
# 编号来自 MediaPipe Pose 的 33 点标准（左/右成对：11/12、13/14 …）。

# ---- 三点组合：用来量「关节角度」----
ANGLE_PARTS = {
    "左肘角（肩-肘-腕）": [11, 13, 15],
    "右肘角（肩-肘-腕）": [12, 14, 16],
    "左膝角（髋-膝-踝）": [23, 25, 27],
    "右膝角（髋-膝-踝）": [24, 26, 28],
    "左肩角（肘-肩-髋）": [13, 11, 23],
    "右肩角（肘-肩-髋）": [14, 12, 24],
    "左髋角（肩-髋-膝）": [11, 23, 25],
    "右髋角（肩-髋-膝）": [12, 24, 26],
    "左踝角（膝-踝-趾）": [25, 27, 31],
    "右踝角（膝-踝-趾）": [26, 28, 32],
    "躯干-左大腿夹角": [11, 23, 25],
    "躯干-右大腿夹角": [12, 24, 26],
}

# ---- 两点组合：用来量距离 / 水平差 / 竖直差 / 倾角 ----
PAIR_PARTS = {
    "左右肩（肩宽）": [11, 12],
    "左右髋（髋宽）": [23, 24],
    "左右膝（膝距）": [25, 26],
    "左右脚踝（脚距）": [27, 28],
    "左脚踝→左膝（小腿）": [27, 25],
    "左脚踝→左脚尖（脚掌）": [27, 31],
    "左肩→左髋（躯干）": [11, 23],
    "左髋→左膝（大腿）": [23, 25],
    "左肩→左肘（上臂）": [11, 13],
    "左肘→左腕（前臂）": [13, 15],
    "左手腕→左肩": [15, 11],
    "右手腕→右肩": [16, 12],
    "左脚踝→左髋（腿全长）": [27, 23],
}

# ══════════════════════════════════════════════════════════════════
# 信号类型：把内部名称翻译成使用者能懂的话
# ══════════════════════════════════════════════════════════════════
# (内部 signal 名, 界面显示名, 用三点还是两点, 单位提示, 一句话解释)
SIGNALS = [
    ("angle", "关节角度（三点夹角）", 3, "度",
     "最稳，优先用。完全伸直是 180°，弯到最紧接近 0°"),
    ("tilt", "倾斜角度（相对竖直）", 2, "度",
     "两点连线偏离竖直方向多少度。不受「人站多远」影响"),
    ("tilts", "倾斜角度（带方向）", 2, "度",
     "同上，但能区分「偏前」和「偏后」（自动按人的朝向翻正）"),
    ("distance", "两点距离", 2, "倍肩宽",
     "两点直线距离。记得选一把稳定的「尺子」做归一化"),
    ("dx", "水平距离（不分左右）", 2, "倍肩宽",
     "两点水平方向差多少。适合量「双脚张开多宽」"),
    ("dxs", "水平距离（分前后）", 2, "倍肩宽",
     "带符号：正值表示第一个点在后。适合判断「膝是否超过脚尖」"),
    ("dy", "竖直距离", 2, "倍肩宽",
     "两点竖直方向差多少。适合量「手抬多高」"),
]

# 判定类型 → 界面显示名
CHECKS = {
    "collinear": "身体是否绷直（三点共线度）",
    "angle_min": "角度不能小于",
    "angle_max": "角度不能大于",
    "peak_min": "本轮最大角度不能小于",
    "peak_max": "本轮最大角度不能大于",
    "valley_max": "本轮最小角度不能大于",
    "valley_min": "本轮最小角度不能小于",
}

# 判定时机 → 界面显示名
WHENS = {
    "any": "全程实时判（如「塌腰了」）",
    "on_rep": "动作做完那一下判（如「蹲得够不够深」）",
    "ready": "只在准备姿势时判",
    "active": "只在动作过程中判",
}


def slugify_id(name, existing=None):
    """
    从中文名生成一个合法的 id（文件名要用）。

    中文没法直接当文件名，所以用拼音首字母很麻烦 —— 这里改用
    「用英文/数字就保留，中文就按顺序编号」的策略，并保证不与已有 id 冲突。
    """
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", (name or "").strip()).strip("_").lower()
    existing = set(existing or [])
    # 中文名（或被过滤成空、或只剩数字）→ 用通用前缀，靠序号区分。
    # 界面里 id 那一栏本来就能手填，所以这里只要保证「不冲突、是合法文件名」即可。
    if not base or base.isdigit():
        base = "action"
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def build_action_config(name, aid, signal, points, start_th, end_th, first_lo=True,
                        cycles=1, camera_side="正面", calibrate=False,
                        depth_check=None, depth_th=None, depth_tip=None,
                        straight_check=None, straight_th=None, straight_tip=None):
    """
    把界面上填的值拼成一份**合法的动作配置**（就是 configs/*.json 的结构）。

    参数用的是「人话」：
      · start_th  信号降到/升到这个值 → 开始算一个动作
      · end_th    回到这个值 → 这个动作完成，计 1 次
      · first_lo  True = 信号先变小（如深蹲下蹲）；False = 先变大（如开合跳举手）

    返回 dict，可直接 json.dump 写进 configs/。
    """
    lo, hi = (start_th, end_th) if first_lo else (end_th, start_th)
    cfg = {
        "id": aid,
        "name": name,
        "camera_side": camera_side,
        "calibrate": bool(calibrate),
        "counter": {
            "signal": signal,
            "points": list(points),
            "lo": float(lo),
            "hi": float(hi),
            "first": "lo" if first_lo else "hi",
            "enter_hold": 0.06,
            "exit_hold": 0.06,
            "min_active_duration": 0.2,
            "min_interval": 0.4,
            "cycles_per_rep": max(1, int(cycles)),
        },
        "quality": [],
    }
    # 归一化基准：距离类信号必须有「尺子」，默认用肩宽；角度类不需要
    if signal in ("distance", "dx", "dxs", "dy"):
        cfg["counter"]["unit_points"] = [11, 12]

    q = cfg["quality"]
    # 「动作幅度够不够」：用周期谷值判 —— 一趟动作里信号最小到过哪里。
    # 注意阈值要设在**起始阈值之内**（更严格），否则永远触发不了。
    if depth_check and depth_th is not None:
        q.append({
            "name": "not_enough_range",
            "check": "valley_max" if first_lo else "peak_min",
            "max" if first_lo else "min": float(depth_th),
            "when": "on_rep", "priority": 80,
            "tip": depth_tip or "动作幅度不够，再做大一点",
        })
    # 「有没有回到起始位置」：用周期峰值判
    if straight_check and straight_th is not None:
        q.append({
            "name": "not_returned",
            "check": "peak_min" if first_lo else "valley_max",
            "min" if first_lo else "max": float(straight_th),
            "when": "on_rep", "priority": 60,
            "tip": straight_tip or "要回到起始姿势，别停在半路",
        })
    return cfg


def validate_and_save(cfg, config_dir):
    """
    先静态校验、再落盘。返回 (是否成功, 提示信息, 保存路径)。

    **必须先校验再写** —— 写进去一份错配置，界面一刷新就会多出一个
    「怎么都不计数」的动作，用户很难联想到是自己某个字段填错了。
    """
    import validate_config

    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"{cfg['id']}.json"

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    rep = validate_config.validate_file(str(tmp))
    if rep.errors:
        tmp.unlink(missing_ok=True)
        return False, "配置有问题，没有保存：\n\n" + "\n".join(f"· {e}" for e in rep.errors), None

    tmp.replace(path)
    # 提示里用实际路径（测试会传临时目录，硬编码 configs/ 会误导）
    msg = f"已保存到 {path}"
    if rep.warns:
        msg += "\n\n提示（不影响使用）：\n" + "\n".join(f"· {w}" for w in rep.warns)
    return True, msg, path
