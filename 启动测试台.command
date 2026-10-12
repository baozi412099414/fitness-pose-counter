#!/bin/bash
# 双击即可启动「健身动作识别测试台」。
# 用系统「终端.app」打开这个文件才会有摄像头权限（macOS 的 TCC 责任链要求）。
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python fitness_ui.py
