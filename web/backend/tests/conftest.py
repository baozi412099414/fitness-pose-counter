"""测试环境开关。

模型预热会让 pytest 退出时等 mediapipe 的加载线程（macOS 上首次可能约一分钟），
而回放测试根本不需要模型，所以统一关掉预热。
"""

import os

os.environ.setdefault("WEB_BACKEND_NO_WARMUP", "1")
