"""模块 5 测试 —— 内置动作库

对应《选题说明》第 11 题功能模块第 5 项：
「随程序提供俯卧撑、深蹲、开合跳、二头弯举、平板支撑等若干动作的配置，开箱即用。」

本模块测「随程序交付的动作配置本身」，不涉及判定算法。

注意这里有个重要事实：配置格式支持**两种计数器写法**
  · 单条件：`counter = {signal, points, lo, hi, first, ...}`  —— 深蹲 / 俯卧撑
  · 多条件：`counter = {conditions: [{signal, points, direction, on, off}, ...]}`
            —— 开合跳（手臂 + 腿 + 双臂同步，必须同时满足）
这正好是「一个格式描述多种动作」的证据。
"""

import glob
import json
import os
import sys

from harness import suite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "configs")

if __name__ == "__main__":
    pass


def _load(base):
    with open(os.path.join(CONFIG_DIR, base), encoding="utf-8") as fp:
        return json.load(fp)


def _counter_kind(cfg):
    c = cfg.get("counter") or {}
    if isinstance(c.get("conditions"), list) and c["conditions"]:
        return "multi"
    if all(k in c for k in ("signal", "points", "lo", "hi")):
        return "single"
    return "unknown"


@suite("模块 05 · 内置动作库")
def _run(t):
    import pose_logic
    import validate_config as vc

    # ---------------- 配置清单 ----------------
    t.section("内置配置清单")
    files = sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json")))
    bases = [os.path.basename(f) for f in files]
    t.truthy("configs/ 下至少有 3 份配置", len(files) >= 3, detail="实际=%r" % (bases,))
    for must in ("squat.json", "pushup.json", "jumping_jack.json"):
        t.truthy("内置 %s" % must, must in bases, detail="实际=%r" % (bases,))

    # ---------------- 必备字段 ----------------
    t.section("每份配置都有动作名 / id / 质量规则")
    for base in bases:
        cfg = _load(base)
        t.truthy("%s 有动作名 name" % base, bool(cfg.get("name")), detail=cfg.get("name"))
        t.truthy("%s 有动作 id" % base, bool(cfg.get("id")), detail=cfg.get("id"))
        t.truthy("%s 有非空质量规则 quality" % base,
                 isinstance(cfg.get("quality"), list) and len(cfg["quality"]) > 0,
                 detail="%r" % (cfg.get("quality"),))

    # ---------------- 计数器格式：两种写法都要能识别 ----------------
    t.section("计数器格式：单条件 / 多条件两种写法")
    kinds = {base: _counter_kind(_load(base)) for base in bases}
    t.truthy("每份配置的计数器格式都能被识别（不是 unknown）",
             all(k != "unknown" for k in kinds.values()), detail=kinds)
    t.truthy("存在「单条件」写法的配置（深蹲/俯卧撑）",
             any(k == "single" for k in kinds.values()), detail=kinds)
    t.truthy("存在「多条件」写法的配置（开合跳：手臂+腿+同步）",
             any(k == "multi" for k in kinds.values()), detail=kinds)
    t.eq("深蹲是单条件", kinds.get("squat.json"), "single")
    t.eq("俯卧撑是单条件", kinds.get("pushup.json"), "single")
    t.eq("开合跳是多条件", kinds.get("jumping_jack.json"), "multi")

    # ---------------- 单条件：阈值方向与时间参数 ----------------
    t.section("单条件配置：阈值方向 lo < hi、first 合法")
    for base in bases:
        cfg = _load(base)
        if _counter_kind(cfg) != "single":
            continue
        c = cfg["counter"]
        t.truthy("%s 的 lo < hi（%r < %r）" % (base, c["lo"], c["hi"]),
                 float(c["lo"]) < float(c["hi"]))
        t.truthy("%s 的 first 只能是 lo/hi（%r）" % (base, c.get("first")),
                 str(c.get("first")) in ("lo", "hi"))

    t.section("多条件配置：每个条件都有 signal/points/direction/on/off")
    for base in bases:
        cfg = _load(base)
        if _counter_kind(cfg) != "multi":
            continue
        for i, cond in enumerate(cfg["counter"]["conditions"]):
            missing = [k for k in ("signal", "points", "direction", "on", "off") if k not in cond]
            t.falsy("%s 第 %d 个条件字段齐全" % (base, i), missing, detail="缺=%r" % (missing,))
            if "on" in cond and "off" in cond:
                # 多条件里 on/off 就是阈值对，方向不同大小关系不同，但两者不能相等
                t.truthy("%s 第 %d 个条件 on != off（迟滞区存在）" % (base, i),
                         float(cond["on"]) != float(cond["off"]),
                         detail="on=%r off=%r" % (cond["on"], cond["off"]))

    t.section("时间参数非负")
    for base in bases:
        c = _load(base)["counter"]
        bad = [k for k in ("min_interval", "enter_hold", "exit_hold", "min_active_duration")
               if k in c and float(c[k]) < 0]
        t.falsy("%s 的时间参数都 >= 0" % base, bad, detail="负值=%r" % (bad,))

    # ---------------- 关键点编号合法 ----------------
    t.section("引用的关键点编号都在 0~32 之间")
    for base in bases:
        cfg = _load(base)
        used = set()
        c = cfg.get("counter") or {}
        if isinstance(c.get("conditions"), list):
            for cond in c["conditions"]:
                used.update(cond.get("points") or [])
                used.update(cond.get("unit_points") or [])
        else:
            used.update(c.get("points") or [])
            used.update(c.get("unit_points") or [])
        for rule in cfg.get("quality") or []:
            used.update(rule.get("points") or [])
            used.update(rule.get("unit_points") or [])
        out = sorted(i for i in used if not (0 <= int(i) <= 32))
        t.falsy("%s 引用的关键点编号全部合法（共用到 %d 个点）" % (base, len(used)),
                out, detail="越界=%r" % (out,))

    # ---------------- 质量规则结构 ----------------
    t.section("质量规则结构完整（name / tip / check）")
    for base in bases:
        rules = _load(base).get("quality") or []
        t.falsy("%s 每条规则都有 name" % base,
                [i for i, r in enumerate(rules) if not r.get("name")])
        t.falsy("%s 每条规则都有 tip（给人看的提示语）" % base,
                [r.get("name") for r in rules if not r.get("tip")])
        t.falsy("%s 每条规则都有 check（判定类型）" % base,
                [r.get("name") for r in rules if not r.get("check")])

    # ---------------- 项目自带校验器复核 ----------------
    t.section("项目自带校验器复核：3 份正式配置应零错误")
    t.truthy("validate_config.main 存在", callable(getattr(vc, "main", None)))
    rc = vc.main([])
    t.eq("validate_config 校验通过（返回 0）", rc, 0)

    # ---------------- 解释器能加载每个动作 ----------------
    t.section("pose_logic.load_action 能加载每个动作")
    for base in bases:
        cfg = _load(base)
        try:
            act = pose_logic.load_action(os.path.join(CONFIG_DIR, base))
        except Exception as e:
            t.check("%s 加载成功" % base, False, "异常：%s: %s" % (type(e).__name__, e))
            continue
        t.truthy("%s 加载成功且 id/name 与配置一致" % base,
                 act.id == cfg["id"] and act.name == cfg["name"],
                 detail="id=%r name=%r" % (act.id, act.name))

    # ---------------- 信号类型的多样性 ----------------
    t.section("配置格式的通用性：不同动作用到不同信号")
    counter_sigs = {}
    quality_sigs = {}
    for base in bases:
        cfg = _load(base)
        c = cfg["counter"]
        if isinstance(c.get("conditions"), list):
            counter_sigs[cfg["id"]] = sorted({cond["signal"] for cond in c["conditions"]})
        else:
            counter_sigs[cfg["id"]] = [c["signal"]]
        quality_sigs[cfg["id"]] = sorted({r["signal"] for r in (cfg.get("quality") or []) if r.get("signal")})
    flat_counter = {s for v in counter_sigs.values() for s in v}
    flat_all = flat_counter | {s for v in quality_sigs.values() for s in v}
    t.truthy("计数器至少用到 2 种信号（angle / dx）", len(flat_counter) >= 2,
             detail="计数器信号=%r 各动作=%r" % (sorted(flat_counter), counter_sigs))
    t.truthy("把质量规则的信号算进来至少 3 种（含 angle_pair_diff）", len(flat_all) >= 3,
             detail="全部信号=%r 各动作质量规则=%r" % (sorted(flat_all), quality_sigs))
    allowed = {"angle", "distance", "tilt", "dx", "dxs", "segment_angle_diff", "angle_pair_diff"}
    t.truthy("用到的信号都在已知集合里", flat_all <= allowed,
             detail="未知信号=%r" % (sorted(flat_all - allowed),))

    # ---------------- UI 动态发现 ----------------
    t.section("界面动作列表由 configs/ 扫描驱动")
    try:
        import fitness_ui
        found = fitness_ui.discover_actions()
        found_ids = [aid for _name, aid in found]
        ids = [base[:-5] for base in bases]
        missing = [i for i in ids if i not in found_ids]
        t.falsy("界面能发现全部内置动作", missing, detail="缺=%r 实际=%r" % (missing, found_ids))
    except Exception as e:
        t.check("界面 discover_actions 可用", False, "异常：%s: %s" % (type(e).__name__, e))


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
