"""模块 9 测试 —— 视频回放与错误片段标记

对应模块 9「支持录像回放并标记动作变形时段」。诚实结论（证据写进用例 detail）：
· 关键点数据回放（--data）已实现：与实时识别共用同一条判定链路，可完整验证；
· 视频输入（--src）在 Camera 层可用：本机 squat_standard.webm 能被 OpenCV 打开并读出帧；
· 「录像」与「错误片段标记」**没有实现**（无 VideoWriter / 片段裁剪代码，报告只有错误次数）。
  `docs/开发历史.md:217` 记模块 9「已砍」，`CLAUDE.md:222` 同 —— 与代码扫描结果一致。
"""

import json
import os
import sys
import time

from harness import suite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
VIDEO = os.path.join(ROOT, "captures", "reference", "squat_standard.webm")


def _import_replay():
    """导入回放进程模块（会连带导入 cv2 / mediapipe）；失败时返回原因。"""
    try:
        import realtime_pose
        return realtime_pose, ""
    except Exception as e:                       # 缺依赖时不要让整个文件崩掉
        return None, "%s: %s" % (type(e).__name__, e)


def _scan(rel_path, *needles):
    """数一数某个项目文件里出现了多少次关键字（用来**验证**「没实现」的结论）。"""
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        text = f.read()
    return {n: text.count(n) for n in needles}


@suite("模块 09 · 视频回放与错误片段标记")
def _run(t):
    os.chdir(ROOT)                 # pose_player 用相对路径读 configs/*.json
    from pose_player import DataError, load_data, play

    tmp = t.tmpdir()

    # ---------------- 数据回放走完整流程 ----------------
    t.section("数据回放：squat_standard.json 走完整判定流程")
    data = load_data(os.path.join(SAMPLES, "squat_standard.json"))
    res = play("squat", data)
    t.check("squat_standard.json 回放 → 3 次 / 得分 78.2±0.2（良好）/ 无错误（与 samples/README.md 一致）",
            res["reps"] == 3 and abs(res["score"] - 78.2) <= 0.2
            and res["grade"] == "良好" and res["errors"] == {},
            "实际：次数=%d 得分=%r 等级=%s 错误=%s 帧数=%d fps=%g"
            % (res["reps"], res["score"], res["grade"], res["errors"],
               res["frames"], res["fps"]))
    frames = [d["frame"] for d in res["reps_detail"]]
    times = [d["time"] for d in res["reps_detail"]]
    t.check("回放时间轴按 fps 推进：180 帧 / 30fps = 6.0 秒，计数落在帧 51/111/171，"
            "时刻 = 帧号/fps = 1.7/3.7/5.7 秒",
            abs(res["duration"] - 6.0) < 1e-9 and frames == [51, 111, 171]
            and all(abs(tm - fr / res["fps"]) < 1e-3 for tm, fr in zip(times, frames)),
            "实际：时长=%r 帧号=%r 时刻=%r" % (res["duration"], frames, times))

    # ---------------- KeypointSource 的时间轴 ----------------
    t.section("回放数据源的时间轴（与墙上时间无关）")
    rp, err = _import_replay()
    if rp is None:
        t.check("数据回放的时间轴按 fps 算（elapsed = 帧号/fps）", True,
                "本机缺 cv2/mediapipe，这一项未实测：%s" % err)
    else:
        ks = rp.KeypointSource(os.path.join(SAMPLES, "squat_standard.json"))
        ks.i = 1
        t.check("KeypointSource.elapsed = i / fps：i=1、fps=30 → 0.033 秒（不会随等待变长而漂移）",
                ks.fps == 30.0 and abs(ks.elapsed - 1.0 / 30.0) < 1e-9,
                "实际：fps=%r elapsed=%r 预期=%r" % (ks.fps, ks.elapsed, 1.0 / ks.fps))
        ks.i = 0
        st1 = ks.read()[0]                       # 首帧：立刻给
        st2 = ks.read()[0]                       # 还没到下一帧的时刻
        ks._next_at = 0.0                        # 直接到点，免得测试真的等 1/30 秒
        st3 = ks.read()[0]
        ks.i = ks.total                          # 读完
        st4 = ks.read()[0]
        t.check("KeypointSource 按数据 fps 恒速吐帧：frame → wait → frame → eof（靠 wait 保住真实时间轴）",
                (st1, st2, st3, st4) == ("frame", "wait", "frame", "eof"),
                "实际状态序列=%r" % ((st1, st2, st3, st4),))

    # ---------------- 视频文件输入 ----------------
    t.section("视频文件输入（--src 走的 Camera 分支）")
    if rp is None:
        t.check("视频文件输入：参考视频能被 Camera 打开并读出帧", True,
                "本机缺 cv2/mediapipe，视频链路未实测：%s" % err)
    elif not os.path.isfile(VIDEO):
        t.check("视频文件输入：本机无视频素材，视频链路未实测", True,
                "未找到 captures/reference/squat_standard.webm")
    else:
        cam, frame, vfps, msg = None, None, 0.0, ""
        try:
            cam = rp.Camera(VIDEO)
            vfps = cam.cap.get(rp.cv2.CAP_PROP_FPS)
            cam.start()
            for _ in range(40):                  # 最多等 2 秒，等线程读到第一帧
                frame = cam.read()
                if frame is not None:
                    break
                time.sleep(0.05)
        except Exception as e:
            msg = "%s: %s" % (type(e).__name__, e)
        finally:
            if cam is not None:
                cam.stop()
        t.check("captures/reference/squat_standard.webm 能被 Camera 打开并读出画面"
                "（视频链路在 Camera 层实测，未跑完整 GUI 主循环）",
                frame is not None and 20 < vfps < 40,
                "实际：画面=%r 源帧率=%r 异常=%r" % (None if frame is None else frame.shape, vfps, msg))

    ok, msg = (rp is None), "本机缺 cv2/mediapipe，未实测" if rp is None else "没有抛异常"
    try:
        if rp:
            rp.Camera(os.path.join(tmp, "不存在的视频.mp4"))
            ok, msg = False, "没有抛异常"
    except RuntimeError as e:
        ok, msg = "打不开视频源" in str(e), str(e)
    except Exception as e:
        ok, msg = False, "%s: %s" % (type(e).__name__, e)
    t.check("给一个不存在的视频路径：抛「打不开视频源：…」这类人话 RuntimeError，而不是裸堆栈",
            ok, "实际：%s" % msg)

    # ---------------- 坏数据文件的错误提示 ----------------
    t.section("坏数据文件：要给「第几帧/哪里不对」的人话提示，而不是 Traceback")
    with open(os.path.join(SAMPLES, "squat_standard.json"), encoding="utf-8") as f:
        base = json.load(f)
    seq = [0]

    def bad_case(name, keyword, obj=None, raw=None):
        seq[0] += 1
        path = os.path.join(tmp, "bad_%d.json" % seq[0])
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(obj, ensure_ascii=False))
        try:
            load_data(path)
            kind, msg = None, "没有抛异常"
        except DataError as e:
            kind, msg = "DataError", str(e)
        except Exception as e:
            kind, msg = type(e).__name__, str(e)
        t.check(name, kind == "DataError" and keyword in msg, "实际：%s: %s" % (kind, msg))

    bad_case("空 frames → 提示「至少要有一帧」", "frames 是空的", dict(base, frames=[]))
    bad_case("坐标数与 points 不符 → 提示「第 0 帧有 11 个坐标，但 points 声明了 12 个」", "个坐标", dict(base, frames=[base["frames"][0][:-1]] + base["frames"][1:]))
    bad_case("关键点编号越界（40）→ 提示「points 里有非法编号」（合法范围 0~32）", "非法编号", dict(base, points=base["points"] + [40]))
    bad_case("fps=0 → 提示「fps 必须是正数」", "fps 必须是正数", dict(base, fps=0))
    bad_case("坏 JSON → 提示「不是合法 JSON」+ 行列号", "不是合法 JSON", raw='{ "frames": [ 这不是合法 JSON')
    bad_case("坐标不是数字（\"abc\"）→ 提示「第 0 帧第 0 个坐标应该是 [x, y]」", "应该是 [x, y]", dict(base, frames=[["abc"] + base["frames"][0][1:]] + base["frames"][1:]))

    # ---------------- 录像与错误片段标记：诚实评估 ----------------
    t.section("录像与错误片段标记：查代码确认实现状态")
    rp_hits = _scan("realtime_pose.py", "VideoWriter", "VideoWriter_fourcc", "imwrite",
                    "片段", "clip")
    ui_hits = _scan("fitness_ui.py", "VideoWriter", "VideoWriter_fourcc", "imwrite",
                    "片段", "clip")
    t.check("录像与错误片段标记：当前未实现（已知缺口）—— realtime_pose.py / fitness_ui.py "
            "里找不到 VideoWriter / 片段裁剪代码",
            all(v == 0 for v in rp_hits.values()) and all(v == 0 for v in ui_hits.values()),
            "扫描结果 realtime_pose.py=%r fitness_ui.py=%r。唯一录像代码在诊断工具 "
            "camera_check.py:251-252（手动按 v 录原始画面到 captures/，不是自动录训练）；"
            "docs/开发历史.md:217 记「模块 9 已砍」，CLAUDE.md:222 同。"
            % (rp_hits, ui_hits))
    rp_log = _scan("realtime_pose.py", "hits_log", "error_counts", '"errors": error_counts')
    pp_log = _scan("pose_player.py", "hits_log")
    t.check("错误片段标记：实时链路只有错误「次数」（realtime_pose.py:1123），没有时间戳或片段；"
            "带时间戳的错误记录只在 pose_player.py 的文本日志（hits_log = rep/frame/time/errors）",
            rp_log["hits_log"] == 0 and rp_log["error_counts"] > 0
            and rp_log['"errors": error_counts'] == 1 and pp_log["hits_log"] == 3,
            "扫描结果 realtime_pose.py=%r pose_player.py=%r" % (rp_log, pp_log))


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
