"""模块 X 测试 —— <模块名>

对应《选题说明》第 11 题「功能模块」第 N 项：<原文一句话>
"""

import sys

if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import run_one
    sys.exit(run_one(__name__, _run)[0] and 0 or 0)

from harness import suite


@suite("模块 X · <模块名>")
def _run(t):
    t.section("<小节标题>")
    # 用例 1：写下输入与预期
    got = 1 + 1
    t.eq("1+1 应该等于 2", got, 2)

    # 用例 2：区间判断
    t.between("分数应落在 0~100", 78.2, 0, 100)


if __name__ == "__main__":
    from harness import run_one
    r = run_one(__name__, _run)
    sys.exit(0 if r["failed"] == 0 else 1)
