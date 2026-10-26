"""逐模块体检：列出每个模块的测试文件是否存在、能否独立跑通、用例数。

比 run_module_tests.py 更适合「边写边看」：它逐个文件用子进程跑，
一个模块崩了不影响其他模块的结果收集。

用法：
    python tests/check_modules.py            # 全部检查
    python tests/check_modules.py m03 m07    # 只检查指定模块
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MODULES = [
    ("m01", "模块 01 · 人体关键点实时检测（核心）", "test_m01_keypoints.py"),
    ("m02", "模块 02 · 自定义健身姿势（核心）", "test_m02_custom_pose.py"),
    ("m03", "模块 03 · 动作状态机与计数（核心）", "test_m03_statemachine.py"),
    ("m04", "模块 04 · 动作质量判定（核心）", "test_m04_quality.py"),
    ("m05", "模块 05 · 内置动作库", "test_m05_actionlib.py"),
    ("m06", "模块 06 · 实时提示与语音播报", "test_m06_feedback.py"),
    ("m07", "模块 07 · 训练组与间歇管理", "test_m07_sets.py"),
    ("m08", "模块 08 · 训练历史与目标", "test_m08_history.py"),
    ("m09", "模块 09 · 视频回放与错误片段标记", "test_m09_replay.py"),
    ("m10", "模块 10 · 个人档案与多用户切换", "test_m10_profiles.py"),
]


def run(path, timeout=240):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        p = subprocess.run([sys.executable, path], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "超时（>%ds）" % timeout, ""
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, None, out


def parse(out):
    """从输出里抓「模块结果：a/b 通过」和失败行。"""
    import re
    m = re.search(r"模块结果：(\d+)/(\d+) 通过", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    passed = out.count("[PASS]")
    failed = out.count("[FAIL]")
    return passed, passed + failed


def main(argv):
    only = {a.lower() for a in argv}
    print("\n" + "#" * 78)
    print("#  逐模块体检")
    print("#" * 78)
    rows = []
    for key, label, fname in MODULES:
        if only and key not in only:
            continue
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            rows.append((label, "缺失", 0, 0, "文件还没写"))
            print("  %-40s 缺失" % label)
            continue
        code, err, out = run(path)
        if code is None:
            rows.append((label, "超时", 0, 0, err))
            print("  %-40s 超时" % label)
            continue
        passed, total = parse(out)
        status = "通过" if code == 0 else "失败"
        rows.append((label, status, passed, total, ""))
        print("  %-40s %-4s %3d/%-3d" % (label, status, passed, total))
        if code != 0:
            for line in out.splitlines():
                if "[FAIL]" in line or "Traceback" in line or "Error" in line:
                    print("      " + line.strip()[:150])

    print("\n  " + "-" * 74)
    ok = sum(1 for r in rows if r[1] == "通过")
    missing = sum(1 for r in rows if r[1] == "缺失")
    bad = sum(1 for r in rows if r[1] == "失败")
    total_cases = sum(r[3] for r in rows)
    total_pass = sum(r[2] for r in rows)
    print("  模块总数 %d：通过 %d / 失败 %d / 缺失 %d" % (len(rows), ok, bad, missing))
    print("  用例合计 %d，其中通过 %d" % (total_cases, total_pass))
    print("  " + "-" * 74)
    return 0 if (bad == 0 and missing == 0) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
