"""模块 4 测试 —— 动作质量判定（按配置识别变形动作并提示纠正）

对应模块 4。预期值来源：`samples/README.md` 的「数据一览」表（计数 / 得分 / 报错）。
"""

import os
import sys

from harness import suite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
TOL = 0.2                      # 得分容差：README 的预期值给到小数点后一位


def _near(got, want, tol=TOL):
    return got is not None and abs(float(got) - float(want)) <= tol


def _run_sample(action_id, sample):
    """走「读数据 → 逐帧判定 → 汇总」链路，返回 (次数, 得分, 错误名集合, 明细)。"""
    from pose_player import load_data, play
    res = play(action_id, load_data(os.path.join(SAMPLES, sample)))
    return res["reps"], res["score"], set(res["errors"]), res


def _points(**kw):
    """构造一帧 33 个关键点（其余点为 (0,0)）：_points(p11=(200,100), p23=(200,200))"""
    pts = [(0, 0)] * 33
    for k, v in kw.items():
        pts[int(k[1:])] = v
    return pts


@suite("模块 04 · 动作质量判定")
def _run(t):
    os.chdir(ROOT)             # pose_player.play 用相对路径读 configs/*.json
    from pose_logic import QualityChecker, load_action
    from pose_player import load_data

    # ---------------- 塌腰：标准 vs 变形（一对） ----------------
    t.section("塌腰检测（俯卧撑）：pushup_sag vs pushup_standard")
    reps, score, errs, _ = _run_sample("pushup", "pushup_sag.json")
    g = QualityChecker.grade(score)
    t.check("pushup_sag（腰塌了）→ 3 次 + 报 low_back + 得分 64.3±0.2（及格）",
            reps == 3 and "low_back" in errs and _near(score, 64.3) and g == "及格",
            "实际：次数=%d 得分=%r 错误=%s 等级=%s" % (reps, score, sorted(errs), g))
    reps, score, errs, _ = _run_sample("pushup", "pushup_standard.json")
    t.check("pushup_standard（标准）→ 3 次 + 不报 low_back + 得分 88.3±0.2",
            reps == 3 and "low_back" not in errs and _near(score, 88.3),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))

    # ---------------- 蹲不够深 / 膝前移 ----------------
    t.section("蹲不够深与膝前移（深蹲）")
    reps, score, errs, _ = _run_sample("squat", "squat_shallow.json")
    want = {"not_deep_enough", "right_not_deep_enough", "not_standing_straight"}
    t.check("squat_shallow（只蹲到 135°）→ 3 次 + 报 %s + 得分 47.3±0.2" % sorted(want),
            reps == 3 and want <= errs and _near(score, 47.3),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))
    reps, score, errs, _ = _run_sample("squat", "squat_standard.json")
    t.check("squat_standard（标准蹲）→ 3 次 + 无任何错误 + 得分 78.2±0.2（对照组）",
            reps == 3 and not errs and _near(score, 78.2),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))
    reps, score, errs, _ = _run_sample("squat", "squat_knee_fwd.json")
    t.check("squat_knee_fwd（膝大幅前移）→ 3 次 + 报 knee_over_toe + 得分 54.6±0.2",
            reps == 3 and "knee_over_toe" in errs and _near(score, 54.6),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))

    # ---------------- 手没举过头 ----------------
    t.section("手没举过头（开合跳）")
    reps, score, errs, _ = _run_sample("jumping_jack", "jack_low_hands.json")
    want = {"hand_not_up", "right_hand_not_up"}
    t.check("jack_low_hands（手只到肩高）→ 3 次 + 报 %s + 得分 48.0±0.2" % sorted(want),
            reps == 3 and want <= errs and _near(score, 48.0),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))
    reps, score, errs, _ = _run_sample("jumping_jack", "jack_standard.json")
    t.check("jack_standard（标准开合跳）→ 3 次 + 无任何错误 + 得分 100.0±0.2",
            reps == 3 and not errs and _near(score, 100.0),
            "实际：次数=%d 得分=%r 错误=%s" % (reps, score, sorted(errs)))

    # ---------------- 优先级：同时命中多条时谁先报 ----------------
    t.section("优先级：同时命中多条时 priority 高的先报")
    data = load_data(os.path.join(SAMPLES, "squat_shallow.json"))
    shallow = load_action(os.path.join(ROOT, "configs", "squat.json"))
    order, prios = [], []
    for i, (pts, vis) in enumerate(zip(data["frames"], data["vis"])):
        count, stage, sig, hits, checks = shallow.update(pts, vis, now=i / data["fps"])
        if len(hits) >= 2:                 # 第一次同时命中多条：检查排序
            order, prios = [h["name"] for h in hits], [h["priority"] for h in hits]
            break
    t.check("squat_shallow 同时命中「蹲不够深」和「站起没伸直」时按 priority 降序"
            "（70 分的 not_deep_enough 排在 50 分的 not_standing_straight 之前）",
            len(order) >= 2 and prios == sorted(prios, reverse=True)
            and order.index("not_deep_enough") < order.index("not_standing_straight"),
            "实际顺序=%r 优先级=%r" % (order, prios))

    # ---------------- confirm_frames：连续确认 ----------------
    t.section("confirm_frames 连续确认：单帧违规不报，连续 N 帧才报")
    cfg = load_action(os.path.join(ROOT, "configs", "pushup.json"))
    cf = int(next(r for r in cfg.quality.rules if r.get("name") == "low_back").get("confirm_frames", 3))
    sag = dict(p11=(200, 100), p13=(200, 150), p15=(200, 200), p23=(200, 200), p27=(300, 300))
    seq = {}
    for n in (1, cf):                      # 髋角 135° < 160° = 塌腰
        a = load_action(os.path.join(ROOT, "configs", "pushup.json"))
        for k in range(n):
            _c, _s, _sig, hits, _checks = a.update(_points(**sag), None, now=k * 0.05)
        seq[n] = [h["name"] for h in hits]
    t.check("配置 confirm_frames=%d：只喂 1 帧塌腰不报；连续喂 %d 帧才报 low_back" % (cf, cf),
            cf == 3 and seq[1] == [] and "low_back" in seq[cf],
            "实际：confirm_frames=%r 1 帧→%r %d 帧→%r" % (cf, seq[1], cf, seq[cf]))

    # ---------------- 关键点不可见：不误报 ----------------
    t.section("关键点不可见时不误报（判为「不可判定」）")
    sag_data = load_data(os.path.join(SAMPLES, "pushup_sag.json"))
    a = load_action(os.path.join(ROOT, "configs", "pushup.json"))
    seen, lb, reps = set(), None, 0
    for i, (pts, vis) in enumerate(zip(sag_data["frames"], sag_data["vis"])):
        v = list(vis)
        v[23] = 0.0                        # 髋点出画：low_back 需要 11/23/27
        count, stage, sig, hits, checks = a.update(pts, v, now=i / sag_data["fps"])
        reps = count
        seen |= {h["name"] for h in hits}
        lb = {c["name"]: c for c in checks}.get("low_back", lb)
    # 记录当前行为：low_back 标 visible=False → 不进 hits / 不参与评分；ok 仍按算出的角度记 False。
    t.check("pushup_sag 把髋点(23) 的 visibility 设 0：low_back 判为不可见（visible=False）"
            "且不产生提示；计数仍为 3 次，其他规则（right_body_line）照常报",
            reps == 3 and "low_back" not in seen and "right_body_line" in seen
            and lb is not None and lb["visible"] is False,
            "实际：次数=%d 命中=%s low_back=%r（visible=False 使其不进 hits/评分，不会误报）"
            % (reps, sorted(seen), {k: lb[k] for k in ("value", "limit", "visible", "ok")}))

    # ---------------- 无数据：不误报 ----------------
    t.section("无数据不误报：极值没采到时不该报违规")
    qc = QualityChecker([{"name": "test_valley", "check": "valley_max", "max": 105,
                          "when": "on_rep", "priority": 70}])  # 最小场景：只有一条 valley_max
    fake = qc.check([], None, "any", True, None, None, {})
    real = load_action(os.path.join(ROOT, "configs", "pushup.json"))
    pts = _points(p11=(200, 100), p13=(200, 150), p15=(200, 200), p23=(200, 200), p27=(200, 300))
    rc = real.quality.check(pts, None, "ready", True, None, None, {})
    by = {c["name"]: c for c in rc}
    t.check("本轮没采到极值（peak/valley 均为 None）时，peak_*/valley_* 规则应是"
            " visible=False、ok=True；hits 为空、total_score 返回 None（算不出分）",
            fake[0]["visible"] is False and fake[0]["ok"] is True and qc.hits(fake) == []
            and qc.total_score(fake) is None and real.quality.hits(rc) == []
            and not by["not_low_enough"]["visible"] and by["not_low_enough"]["ok"]
            and not by["arm_not_straight"]["visible"] and by["arm_not_straight"]["ok"],
            "实际：最小规则=%r hits=%r total=%r；pushup not_low_enough=%r arm_not_straight=%r"
            % ({k: fake[0][k] for k in ("value", "visible", "ok")}, qc.hits(fake),
               qc.total_score(fake), by["not_low_enough"], by["arm_not_straight"]))

    # ---------------- 评分单调性 ----------------
    t.section("评分单调性：越标准分越高")
    pairs = [("pushup", "pushup_standard.json", "pushup_sag.json"), ("squat", "squat_standard.json", "squat_shallow.json"), ("jumping_jack", "jack_standard.json", "jack_low_hands.json")]
    ok, parts = True, []
    for aid, good, bad in pairs:
        gd, bd = _run_sample(aid, good)[1], _run_sample(aid, bad)[1]
        parts.append("%s 标准=%r > 变形=%r" % (aid, gd, bd))
        ok = ok and gd is not None and bd is not None and gd > bd
    t.check("三对样本（俯卧撑 / 深蹲 / 开合跳）的「标准分 > 变形分」都成立", ok, "；".join(parts))

    # ---------------- grade() 分档 + 及格/满分线 ----------------
    t.section("grade() 分档与 _score() 及格线 / 满分线")
    g = QualityChecker.grade
    want_g = {59.9: "待改进", 60: "及格", 75: "良好", 89.9: "良好", 90: "优秀",
              100: "优秀", None: "—"}
    t.check("grade 分档：59.9 待改进 / 60 及格 / 75 良好 / 89.9 良好 / 90 优秀 / 100 优秀 / None「—」",
            {k: g(k) for k in want_g} == want_g,
            "实际=%r" % ({k: g(k) for k in want_g},))
    s = QualityChecker._score
    got = [s(160, 160, "peak_min"), s(105, 105, "valley_max"), s(172, 160, "peak_min", 172),
           s(90, 105, "valley_max", 90), s(None, 160, "peak_min")]
    t.check("_score：实测值刚好压阈值 = 60 分（及格线），达到 ideal = 100 分，无数据不扣分",
            all(_near(v, w) for v, w in zip(got, [60.0, 60.0, 100.0, 100.0, 100.0])),
            "实际：压线=%r/%r 满分=%r/%r 无数据=%r" % tuple(got))


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
