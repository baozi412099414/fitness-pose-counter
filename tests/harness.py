"""按模块组织测试的公共框架。

设计目标
--------
1. **一个模块一个文件**：`tests/test_m01_*.py` ~ `tests/test_m10_*.py`，
   每个文件对应《选题说明》第 11 题的 10 个功能模块之一。
2. **每个文件可单独运行**：`python tests/test_m07_sets.py`
3. **也能一次全跑**：`python tests/run_module_tests.py`
4. **不改被测代码**：本框架只 import 项目模块，不做任何 monkey patch 之外的侵入。
   （个别测试需要伪造硬件时，用临时替换 + 复原，不在项目文件里留痕。）

用法（写新测试）
----------------
    from harness import suite, check, eq

    @suite("模块 07 · 训练组与间歇管理")
    def main(t):
        t.section("组数与次数")
        got = ...
        check(t, "3 组 x 10 次能产生 all_done", got == "all_done", detail=got)

约定
----
- 每个用例都要**写明输入与预期**（打印里体现），这是验收文档要的东西。
- 失败不抛异常中断，统一收集到结果里，最后给通过率。
- 退出码：全通过 0，有失败 1。
"""

import io
import os
import sys
import tempfile
import time
import traceback

# 让 tests/ 目录下的脚本能 import 项目根目录的模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Windows 控制台 GBK 会打不出中文和 ✅，统一转成 UTF-8
if hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

OK_MARK = "PASS"
FAIL_MARK = "FAIL"


class Case:
    __slots__ = ("module", "name", "ok", "detail", "elapsed")

    def __init__(self, module, name):
        self.module = module
        self.name = name
        self.ok = True
        self.detail = ""
        self.elapsed = 0.0

    def __repr__(self):
        return "<Case %s %s %s>" % (self.module, self.name, OK_MARK if self.ok else FAIL_MARK)


class Tracker:
    """测试上下文：提供 section / 断言 / 规范化的小工具。"""

    def __init__(self, module_name):
        self.module = module_name
        self.cases = []
        self._section = ""
        self._t0 = time.time()
        self.tmpdirs = []
        print("\n" + "=" * 74)
        print("  " + module_name)
        print("=" * 74)

    # ---------- 展示 ----------
    def section(self, title):
        self._section = title
        print("\n--- %s ---" % title)

    # ---------- 断言 ----------
    def check(self, name, cond, detail=""):
        c = Case(self.module, name)
        c.ok = bool(cond)
        c.detail = str(detail)
        self.cases.append(c)
        line = "  [%s] %s" % (OK_MARK if c.ok else FAIL_MARK, name)
        if c.detail and not c.ok:
            line += "   <- " + c.detail
        elif c.detail:
            line += "   (" + c.detail + ")"
        print(line)
        return c.ok

    def eq(self, name, got, want):
        return self.check(name, got == want, "实际=%r 预期=%r" % (got, want))

    def near(self, name, got, want, tol=1e-6):
        try:
            ok = abs(float(got) - float(want)) <= tol
        except Exception:
            ok = False
        return self.check(name, ok, "实际=%r 预期=%r±%r" % (got, want, tol))

    def between(self, name, got, lo, hi):
        try:
            ok = lo <= float(got) <= hi
        except Exception:
            ok = False
        return self.check(name, ok, "实际=%r 期望区间=[%r, %r]" % (got, lo, hi))

    def truthy(self, name, got, detail=""):
        return self.check(name, bool(got), detail or "实际=%r" % (got,))

    def falsy(self, name, got, detail=""):
        return self.check(name, not got, detail or "实际=%r" % (got,))

    # ---------- 工具 ----------
    def tmpdir(self):
        d = tempfile.mkdtemp(prefix="dsh_test_")
        self.tmpdirs.append(d)
        return d

    def cleanup(self):
        import shutil
        for d in self.tmpdirs:
            shutil.rmtree(d, ignore_errors=True)
        self.tmpdirs = []

    def expect_exception(self, name, fn, exc_type=Exception):
        try:
            fn()
        except exc_type as e:
            return self.check(name, True, "如期抛出 %s: %s" % (type(e).__name__, e))
        except Exception as e:
            return self.check(name, False, "抛了别的异常 %s: %s" % (type(e).__name__, e))
        return self.check(name, False, "预期抛异常，实际没有抛")

    # ---------- 汇总 ----------
    def summary(self):
        total = len(self.cases)
        passed = sum(1 for c in self.cases if c.ok)
        failed = total - passed
        print("\n" + "-" * 74)
        if failed == 0:
            print("  模块结果：%d/%d 通过  >>> 全部通过" % (passed, total))
        else:
            print("  模块结果：%d/%d 通过，%d 条失败" % (passed, total, failed))
            for c in self.cases:
                if not c.ok:
                    print("    x %s   %s" % (c.name, c.detail))
        print("-" * 74)
        return {"module": self.module, "total": total, "passed": passed, "failed": failed}


REGISTRY = []


def suite(module_name):
    """装饰器：把一个函数登记成一个模块测试。"""
    def deco(fn):
        REGISTRY.append((module_name, fn))
        return fn
    return deco


def run_one(module_name, fn):
    t = Tracker(module_name)
    try:
        fn(t)
    except Exception:
        t.check("模块执行过程未抛异常", False, "抛了异常：\n" + traceback.format_exc())
    finally:
        t.cleanup()
    return t.summary()


def run_all():
    if not REGISTRY:
        print("没有登记任何模块测试。请先 import tests 目录下的模块文件。")
        return 1
    results = []
    print("\n" + "#" * 74)
    print("#  按模块测试 —— 共 %d 个模块" % len(REGISTRY))
    print("#" * 74)
    for module_name, fn in REGISTRY:
        results.append(run_one(module_name, fn))

    print("\n" + "#" * 74)
    print("#  汇总")
    print("#" * 74)
    print("  %-42s %6s %6s %6s" % ("模块", "用例", "通过", "失败"))
    print("  " + "-" * 62)
    t_total = t_pass = t_fail = 0
    for r in results:
        flag = "" if r["failed"] == 0 else "  <<<"
        print("  %-42s %6d %6d %6d%s" % (r["module"], r["total"], r["passed"], r["failed"], flag))
        t_total += r["total"]
        t_pass += r["passed"]
        t_fail += r["failed"]
    print("  " + "-" * 62)
    print("  %-42s %6d %6d %6d" % ("合计", t_total, t_pass, t_fail))
    if t_fail == 0:
        print("\n  全部模块通过")
    else:
        print("\n  有 %d 条用例失败" % t_fail)
    return 0 if t_fail == 0 else 1
