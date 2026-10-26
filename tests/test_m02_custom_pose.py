"""模块 02 测试 —— 自定义健身姿势（界面填表 → 生成配置 → 解释器生效，全程不改代码）

对应《选题说明》第 11 题「功能模块」第 2 项。本文件验证核心主张：
新增一个动作 = 写一份配置，pose_logic.py 一行都不用改。所有写操作都只落在
t.tmpdir() 的临时目录，绝不碰项目真实的 configs/。
"""

import json
import math
import os
import sys

from harness import ROOT, suite
from action_editor import ANGLE_PARTS, build_action_config, slugify_id, validate_and_save
from pose_logic import load_action
from validate_config import validate_file

REAL_CONFIGS = os.path.join(ROOT, "configs")


def _curl_cfg(**over):
    """等价于在动作编辑器里填一张表：左肘角（肩-肘-腕），降到 130° 开始、回到 155° 计一次。"""
    kw = dict(name="测试弯举", aid="test_curl", signal="angle",
              points=ANGLE_PARTS["左肘角（肩-肘-腕）"],
              start_th=130, end_th=155, first_lo=True, cycles=1,
              depth_check=True, depth_th=80, depth_tip="手臂没弯到位，再往上举一点",
              straight_check=True, straight_th=165, straight_tip="放下时手臂要伸直")
    kw.update(over)
    return build_action_config(**kw)


def _write(t, cfg, filename=None):
    """写进临时目录，返回路径（默认 id.json，避免「文件名与 id 不符」的警告）。"""
    path = os.path.join(t.tmpdir(), filename or "%s.json" % cfg["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return path


def _errors_of(t, cfg):
    """写临时文件后跑静态校验，只取「错误」列表。"""
    return validate_file(_write(t, cfg, "bad.json")).errors


def _curl_pose(elbow_deg):
    """合成弯举姿态：左肘角 = elbow_deg（肩、肘、腕三点按该角度摆放）。"""
    p = [(300, 300)] * 33
    d = math.radians(180 - elbow_deg)
    elbow, wrist = (0.0, 1.0), (math.sin(d), 1.0 + math.cos(d))
    px = lambda v: (int(600 + v[0] * 100.0), int(200 + v[1] * 100.0))
    p[11] = p[12] = px((0.0, 0.0))
    p[13], p[15] = px(elbow), px(wrist)
    p[14], p[16] = px(elbow), (2 * 600 - px(wrist)[0], px(wrist)[1])
    p[23] = p[24] = (600, 700)
    return p


def _reps(cfg_path, n, top, bottom):
    """跑 n 次弯举（伸直 4 帧 → 弯起 8 帧 → 伸直 6 帧 @30fps）。
    时间轴必须自己给：用真实时钟会快于 enter_hold，状态机永远不迁移。"""
    a = load_action(cfg_path)
    seen, frame = set(), 0
    for _ in range(n):
        for pose in [_curl_pose(top)] * 4 + [_curl_pose(bottom)] * 8 + [_curl_pose(top)] * 6:
            count, stage, sig, hits, checks = a.update(pose, [1.0] * 33, now=frame / 30.0)
            seen.update(h["name"] for h in hits)
            frame += 1
    return a.counter.count, seen, a.last_score


@suite("模块 02 · 自定义健身姿势")
def _run(t):
    t.section("一、表单填表 → 生成配置")
    cfg = _curl_cfg()
    c = cfg["counter"]
    t.check("表单（左肘角/130°/155°/先变小）生成的 counter 段：signal=angle、points=[11,13,15]、"
            "lo=130、hi=155、first=lo",
            c["signal"] == "angle" and c["points"] == [11, 13, 15] and c["lo"] == 130.0
            and c["hi"] == 155.0 and c["first"] == "lo" and c["cycles_per_rep"] == 1,
            "counter=%s；自动生成 %d 条质量约束"
            % ({k: c[k] for k in ("signal", "points", "lo", "hi", "first")}, len(cfg["quality"])))
    rep = validate_file(_write(t, cfg))
    t.check("生成的配置通过 validate_config 静态校验：0 错误、0 警告",
            not rep.errors and not rep.warns, "错误=%s 警告=%s" % (rep.errors, rep.warns))

    t.section("二、写入临时 configs/ 与解释器往返")
    before = sorted(os.listdir(REAL_CONFIGS))
    ok, msg, path = validate_and_save(cfg, t.tmpdir())
    after = sorted(os.listdir(REAL_CONFIGS))
    t.check("validate_and_save 只写进临时目录：保存成功、文件在那边、真实 configs/ 前后清单不变",
            ok and path and os.path.exists(path) and os.path.dirname(path) != REAL_CONFIGS
            and before == after,
            "返回=%s；真实 configs/ %s" % (msg.splitlines()[0] if msg else "-",
                                        "未变 %s" % before if before == after else "被改了！"))
    a = load_action(path)
    names = [r["name"] for r in a.quality.rules]
    t.check("load_action 读回后与写入完全一致（配置往返）：lo/hi/first/signal/points/cycles/规则名",
            (a.counter.lo, a.counter.hi, a.counter.first) == (c["lo"], c["hi"], c["first"])
            and (a.signal_type, a.signal_points) == (c["signal"], c["points"])
            and a.counter.cycles_per_rep == 1 and names == ["not_enough_range", "not_returned"],
            "读回 lo=%r hi=%r first=%r signal=%r points=%r 规则=%s"
            % (a.counter.lo, a.counter.hi, a.counter.first, a.signal_type,
               a.signal_points, names))

    t.section("三、这份配置真的能驱动计数与质量判定")
    reps, seen, score = _reps(path, 2, 170, 45)
    t.check("按生成配置做 2 次标准弯举（170°→45°）→ 计数 2、无错误提示、评分在 0~100",
            reps == 2 and not seen and score is not None and 0 <= score <= 100,
            "计数=%r 错误=%s 评分=%r" % (reps, seen or "无", score))
    reps, seen, _ = _reps(path, 2, 170, 100)
    t.check("只弯到 100°（未达表单填的深度线 80°）→ 仍计数 2 但报 not_enough_range",
            reps == 2 and "not_enough_range" in seen, "计数=%r 错误=%s" % (reps, seen or "无"))

    t.section("四、非法配置必须在校验器被拦下（不是等到摄像头前才发现）")
    errs = _errors_of(t, _curl_cfg(start_th=130, end_th=120))
    t.check("lo >= hi（开始 130°/还原 120°，迟滞区写反）→ 校验器报错",
            bool(errs) and any("lo" in e and "hi" in e for e in errs), "错误=%s" % errs)
    errs = _errors_of(t, _curl_cfg(points=[11, 13, 99]))
    t.check("关键点编号 99 越界（合法 0~32）→ 校验器报错并给出相邻的正确写法",
            bool(errs) and any("99" in e and ("越界" in e or "0~32" in e) for e in errs),
            "错误=%s" % errs)
    errs = _errors_of(t, _curl_cfg(signal="angel", points=[11, 13]))
    t.check("signal 拼错成 angel → 校验器报「不支持」并列出全部合法取值",
            bool(errs) and any("angel" in e and "不支持" in e for e in errs),
            "错误=%s（注意 load_action 自己不校验 signal 名，拼错时每帧信号为 None、静默永不计数，"
            "所以这道校验是唯一防线）" % errs)
    bad = _curl_cfg()
    bad["quality"][0]["check"] = "valley_maxx"
    errs = _errors_of(t, bad)
    t.check("quality.check 拼错成 valley_maxx → 校验器报「不支持」并列出全部合法取值",
            bool(errs) and any("valley_maxx" in e and "不支持" in e for e in errs), "错误=%s" % errs)

    t.section("五、id 生成与坏 JSON 的提示质量")
    sid = slugify_id
    t.check("slugify_id：中文名（无法当文件名）→ 退回 action；重名时自动加序号 action_2",
            sid("测试弯举") == "action" and sid("测试弯举", ["action"]) == "action_2",
            "中文=%r 重名=%r" % (sid("测试弯举"), sid("测试弯举", ["action"])))
    t.check("slugify_id：英文/空格/特殊字符规范化，纯数字与空串同样退回 action",
            sid(" Bicep Curl 2! ") == "bicep_curl_2"
            and sid("123") == "action" and sid("") == "action",
            "『 Bicep Curl 2! 』=%r 123=%r 空串=%r"
            % (sid(" Bicep Curl 2! "), sid("123"), sid("")))
    broken = os.path.join(t.tmpdir(), "broken.json")
    with open(broken, "w", encoding="utf-8") as f:
        f.write('{\n  "id": "x",\n  "counter": {"lo": 1,\n}\n')
    msg = ""
    try:
        load_action(broken)
    except ValueError as e:
        msg = str(e)
    t.expect_exception("坏 JSON（少一个逗号）交给 load_action → 抛 ValueError，而不是裸 JSONDecodeError",
                       lambda: load_action(broken), ValueError)
    t.check("坏 JSON 的提示带「第 N 行第 M 列」和文件名，用户能直接定位",
            "行" in msg and "列" in msg and "broken.json" in msg, msg or "（没有抛 ValueError）")


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
