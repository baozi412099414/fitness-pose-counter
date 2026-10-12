#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键点数据回放测试 —— 用**你自己提供的姿态数据**测试动作判定

【这个工具解决什么问题】
你手上有一组关键点数据（从视频里提取的、别人标注的、或者手工构造的），
想知道「某个动作配置在这组数据上表现如何」—— 数了几次、判定准不准、扣分扣在哪。

这个工具就是干这个的：**读数据 → 逐帧喂给动作解释器 → 出报告**。
全程不需要摄像头，也不需要重新做动作。

【数据格式（JSON）】

最简形式：只给你关心的关键点
```json
{
  "fps": 30,
  "points": [23, 25, 27],
  "frames": [
    [[300, 200], [310, 400], [300, 600]],
    [[300, 205], [315, 405], [300, 605]]
  ]
}
```
`frames` 里每一帧的坐标顺序，和 `points` 一一对应（上面第 0 个坐标是 23 号点即左髋）。

完整形式：给全部 33 个关键点（此时 `points` 可以省略）
```json
{
  "fps": 30,
  "frames": [
    [[x0, y0], [x1, y1], ... , [x32, y32]],
    ...
  ]
}
```

可选字段：
  · `visibility`：可见度。给一个数（所有帧所有点都用它），
    或者给 `frames` 等长的数组（每帧一个数）。默认 1.0。
    设为 0 可以用来模拟「关键点被遮挡」的情形。
  · `name` / `note`：随便写的备注，只用于报告显示。

【用法】
    .venv/bin/python pose_player.py --action squat --data my_data.json
    .venv/bin/python pose_player.py --action squat --data my_data.json --verbose
    .venv/bin/python pose_player.py --data my_data.json            # 动作从数据里读
    .venv/bin/python pose_player.py --action squat --data my_data.json --json out.json
"""

import argparse
import json
import os
import sys

from pose_logic import QualityChecker, load_action

# 常用关键点编号 → 中文名（报告里显示用）
LANDMARK_CN = {
    0: "鼻子", 11: "左肩", 12: "右肩", 13: "左肘", 14: "右肘", 15: "左腕", 16: "右腕",
    23: "左髋", 24: "右髋", 25: "左膝", 26: "右膝", 27: "左踝", 28: "右踝",
    29: "左脚跟", 30: "右脚跟", 31: "左脚尖", 32: "右脚尖",
}


class DataError(Exception):
    """数据文件本身有问题时抛出，带上人能看懂的原因。"""


def load_data(path):
    """
    读关键点数据，返回 dict：
      fps, action（可能为空）, name/note, frames（每帧 33 个点）, vis（每帧 33 个可见度）

    ⚠ 这里刻意做了**很多校验** —— 数据是用户自己提供的，格式出错是常态，
    报错要能直接指出「第几帧、第几个点、哪里不对」，而不是抛个 IndexError。
    """
    if not os.path.exists(path):
        raise DataError(f"找不到数据文件：{path}")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise DataError(f"不是合法 JSON：第 {e.lineno} 行第 {e.colno} 列 —— {e.msg}") from None

    if not isinstance(raw, dict):
        raise DataError("数据文件的根节点必须是一个对象 {}")
    frames_raw = raw.get("frames")
    if not isinstance(frames_raw, list) or not frames_raw:
        raise DataError("缺少 frames，或者 frames 是空的（至少要有一帧）")

    fps = float(raw.get("fps", 30.0))
    if fps <= 0:
        raise DataError(f"fps 必须是正数，现在是 {fps}")

    idx = raw.get("points")
    if idx is not None:
        if not isinstance(idx, list) or not idx:
            raise DataError("points 必须是「关键点编号」的非空数组，例如 [23, 25, 27]")
        bad = [i for i in idx if not isinstance(i, int) or not 0 <= i <= 32]
        if bad:
            raise DataError(f"points 里有非法编号 {bad}（合法范围 0~32）")
        if len(set(idx)) != len(idx):
            raise DataError("points 里有重复的编号")
    else:
        idx = list(range(33))

    # ---- 逐帧解析 ----
    frames, vis_frames = [], []
    vis_raw = raw.get("visibility", 1.0)
    for fi, fr in enumerate(frames_raw):
        if not isinstance(fr, list) or len(fr) != len(idx):
            raise DataError(
                f"第 {fi} 帧有 {len(fr) if isinstance(fr, list) else '非数组'} 个坐标，"
                f"但 points 声明了 {len(idx)} 个关键点（{idx}）")
        pts = [(0, 0)] * 33                      # 没提供的点保持 (0,0)
        for k, xy in enumerate(fr):
            if (not isinstance(xy, (list, tuple))) or len(xy) != 2:
                raise DataError(f"第 {fi} 帧第 {k} 个坐标应该是 [x, y]，实际是 {xy!r}")
            try:
                pts[idx[k]] = (int(round(float(xy[0]))), int(round(float(xy[1]))))
            except (TypeError, ValueError):
                raise DataError(f"第 {fi} 帧第 {k} 个坐标不是数字：{xy!r}") from None
        frames.append(pts)

        if isinstance(vis_raw, list):
            if len(vis_raw) != len(frames_raw):
                raise DataError(f"visibility 有 {len(vis_raw)} 项，"
                                f"但 frames 有 {len(frames_raw)} 帧 —— 两者要么都给满，"
                                f"要么 visibility 直接给一个数")
            v = float(vis_raw[fi])
        else:
            v = float(vis_raw)
        # 只给提供的点设可见度，其余保持 0（表示「这帧没有这些点」）
        vis = [0.0] * 33
        for i in idx:
            vis[i] = v
        vis_frames.append(vis)

    return {
        "fps": fps, "action": raw.get("action"),
        "name": raw.get("name"), "note": raw.get("note"),
        "points": idx, "frames": frames, "vis": vis_frames,
    }


def play(action_id, data, verbose=False, quiet=False):
    """
    把数据逐帧喂给动作解释器，返回统计结果。

    时间轴按 `fps` 推进 —— 这一点很重要：动作里的 `enter_hold` / `min_interval`
    都是**秒**，帧率给错的话防抖判定会整体偏掉。
    """
    action = load_action(f"configs/{action_id}.json")
    fps = data["fps"]
    errors, hits_log = {}, []
    last_count = 0
    detail = []

    for i, (pts, vis) in enumerate(zip(data["frames"], data["vis"])):
        t = i / fps
        count, stage, sig, hits, checks = action.update(pts, vis, now=t)
        if verbose:
            detail.append((i, t, sig, stage, count))
        if count > last_count:
            last_count = count
            names = [h["name"] for h in hits]
            hits_log.append({"rep": count, "frame": i, "time": round(t, 3),
                             "errors": names, "score": action.last_score})
            for n in names:
                errors[n] = errors.get(n, 0) + 1

    return {
        "action": action_id,
        "action_name": action.name,
        "reps": action.counter.count,
        "frames": len(data["frames"]),
        "duration": len(data["frames"]) / fps,
        "fps": fps,
        "score": action.last_score,
        "grade": QualityChecker.grade(action.last_score),
        "errors": errors,
        "error_tips": {r.get("name"): r.get("tip", r.get("name"))
                       for r in action.quality.rules if r.get("name") in errors},
        "reps_detail": hits_log,
        "_frame_detail": detail,
    }


def print_report(res, data, verbose=False):
    idx = data["points"]
    # 只给有中文名的点标名字（补齐 33 个点的中文名意义不大，反而更乱）
    ptxt = "、".join(f"{i}({LANDMARK_CN[i]})" if i in LANDMARK_CN else str(i) for i in idx[:6])
    if len(idx) > 6:
        ptxt += f" …共 {len(idx)} 个"

    print("═" * 72)
    print("关键点数据回放测试")
    print("═" * 72)
    if data.get("name"):
        print(f"  数据名称　{data['name']}")
    if data.get("note"):
        print(f"  备注　　　{data['note']}")
    print(f"  数据规模　{res['frames']} 帧 × {res['fps']:g}fps = {res['duration']:.2f} 秒")
    print(f"  包含关键点　{ptxt}")
    print(f"  测试动作　{res['action_name']}（{res['action']}）")
    print("─" * 72)
    print(f"  【计数】　{res['reps']} 次")
    if res["score"] is not None:
        print(f"  【评分】　{res['score']} 分（{res['grade']}）")
    else:
        print("  【评分】　—（没有完成任何一次动作，算不出分）")

    if res["errors"]:
        print("  【错误事件】")
        for name, n in sorted(res["errors"].items(), key=lambda kv: -kv[1]):
            tip = res["error_tips"].get(name, name)
            print(f"      {tip}　×{n}")
    else:
        print("  【错误事件】无")

    if res["reps_detail"]:
        print("─" * 72)
        print("  每次计数的判定结果：")
        for d in res["reps_detail"]:
            sc = f"{d['score']:.0f} 分" if d["score"] is not None else "—"
            errs = "、".join(res["error_tips"].get(e, e) for e in d["errors"]) or "全部合格"
            print(f"      第 {d['rep']} 次　帧 {d['frame']:>4}（t={d['time']:.2f}s）"
                  f"　{sc:>7}　{errs}")

    if verbose and res["_frame_detail"]:
        print("─" * 72)
        print("  逐帧信号（前 60 帧）：")
        for i, t, sig, stage, cnt in res["_frame_detail"][:60]:
            s = f"{sig:7.2f}" if sig is not None else "   --  "
            print(f"      帧 {i:>4}  t={t:6.3f}s  信号 {s}  阶段 {stage:6s}  计数 {cnt}")
    print("═" * 72)


def main():
    ap = argparse.ArgumentParser(
        description="用你自己提供的关键点数据测试动作判定（不需要摄像头）")
    ap.add_argument("--action", help="动作 id（不填则从数据文件的 action 字段读）")
    ap.add_argument("--data", required=True, help="数据文件（JSON）")
    ap.add_argument("--verbose", action="store_true", help="打印逐帧信号")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="把结果另存为 JSON（便于批量比对）")
    args = ap.parse_args()

    try:
        data = load_data(args.data)
    except DataError as e:
        print(f"❌ 数据文件有问题：{e}", file=sys.stderr)
        return 2

    action_id = args.action or data.get("action")
    if not action_id:
        print("❌ 没指定动作。请用 --action，或者在数据文件里写 \"action\": \"squat\"",
              file=sys.stderr)
        return 2
    if not os.path.exists(f"configs/{action_id}.json"):
        avail = sorted(f[:-5] for f in os.listdir("configs") if f.endswith(".json"))
        print(f"❌ 找不到动作配置 configs/{action_id}.json\n   可用的动作：{avail}",
              file=sys.stderr)
        return 2

    res = play(action_id, data, verbose=args.verbose)
    print_report(res, data, verbose=args.verbose)

    if args.json_out:
        out = {k: v for k, v in res.items() if not k.startswith("_")}
        out["data_file"] = os.path.basename(args.data)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"结果已保存：{args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
