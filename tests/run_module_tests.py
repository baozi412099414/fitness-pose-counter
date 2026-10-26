"""按模块跑全部测试。

用法：
    python tests/run_module_tests.py               # 跑全部 10 个模块
    python tests/run_module_tests.py m03 m07       # 只跑指定模块

每个模块也可以单独跑：
    python tests/test_m07_sets.py
"""

import sys

from harness import REGISTRY, run_all

# 导入即登记。顺序 = 选题说明里的模块顺序。
MODULES = [
    ("m01", "test_m01_keypoints"),
    ("m02", "test_m02_custom_pose"),
    ("m03", "test_m03_statemachine"),
    ("m04", "test_m04_quality"),
    ("m05", "test_m05_actionlib"),
    ("m06", "test_m06_feedback"),
    ("m07", "test_m07_sets"),
    ("m08", "test_m08_history"),
    ("m09", "test_m09_replay"),
    ("m10", "test_m10_profiles"),
]


def load(only=None):
    import importlib
    for key, modname in MODULES:
        if only and key not in only:
            continue
        try:
            importlib.import_module(modname)
        except Exception as e:
            print("!! 加载 %s 失败：%s: %s" % (modname, type(e).__name__, e))


if __name__ == "__main__":
    args = [a.lower().lstrip("-") for a in sys.argv[1:]]
    load(set(args) if args else None)
    sys.exit(run_all())
