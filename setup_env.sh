#!/bin/bash
# =============================================================================
# 摄像头接入环境一键配置  —— 选题 11 健身动作计数与姿态纠正
#
# 用法：在「终端」里粘贴下面两行
#     cd ~/Desktop/选题\ 2
#     bash setup_env.sh
#
# 可选参数：
#     bash setup_env.sh --minimal    只装 opencv，不装 mediapipe（更快，够跑摄像头）
#     bash setup_env.sh --cn         直接用国内镜像，不试官方源
#
# 脚本做的事：检查系统 → 建独立虚拟环境 → 装依赖 → 下模型 → 自检摄像头
# 全程不动你的系统 Python，所有东西都装在本目录的 .venv 里，删掉即可还原。
# =============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

VENV="$SCRIPT_DIR/.venv"
PY="$VENV/bin/python"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
MODEL="pose_landmarker_lite.task"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

INSTALL_MP=1
FORCE_CN=0
for a in "$@"; do
  case "$a" in
    --minimal) INSTALL_MP=0 ;;
    --cn)      FORCE_CN=1 ;;
  esac
done

say()  { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }
ok()   { printf "    \033[1;32m✓\033[0m %s\n" "$1"; }
bad()  { printf "    \033[1;31m✗\033[0m %s\n" "$1"; }
warn() { printf "    \033[1;33m!\033[0m %s\n" "$1"; }
info() { printf "      %s\n" "$1"; }

printf "\n\033[1m摄像头接入环境配置\033[0m  ——  选题 11\n"
printf "工作目录：%s\n" "$SCRIPT_DIR"

# -----------------------------------------------------------------------------
say "1/5  检查系统"
# -----------------------------------------------------------------------------
if [ "$(uname -s)" != "Darwin" ]; then
  bad "这个脚本是给 macOS 用的"
  exit 1
fi

OSV="$(sw_vers -productVersion)"
OSMAJOR="${OSV%%.*}"
ARCH="$(uname -m)"
ok "macOS $OSV  ($ARCH)"

if [ "$OSMAJOR" -ge 13 ] 2>/dev/null; then
  ok "系统版本支持「连续互通相机」（iPhone 当摄像头）"
else
  warn "macOS $OSV 低于 13，不支持连续互通相机"
  info "环境照样能配，但 iPhone 接不进来，只能用内置摄像头或读录好的视频"
fi

# -----------------------------------------------------------------------------
say "2/5  检查 Python"
# -----------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  bad "没有找到 python3"
  info "先装一下命令行工具，终端里运行： xcode-select --install"
  info "装完重新跑本脚本"
  exit 1
fi

PYPATH="$(command -v python3)"
PYVER="$(python3 -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null)"
PYMINOR="$(python3 -c 'import sys;print(sys.version_info[1])' 2>/dev/null)"
if [ -z "$PYVER" ]; then
  bad "python3 存在但跑不起来，可能命令行工具没装全"
  info "运行： xcode-select --install"
  exit 1
fi
ok "Python $PYVER   ($PYPATH)"

if [ "$PYMINOR" -lt 9 ] 2>/dev/null; then
  bad "Python 版本太低（需要 3.9 以上）"
  info "建议装 Homebrew 版：brew install python@3.12"
  exit 1
fi
if [ "$INSTALL_MP" -eq 1 ] && [ "$PYMINOR" -ge 13 ] 2>/dev/null; then
  warn "Python 3.$PYMINOR 上 mediapipe 可能还没有预编译包"
  info "如果第 3 步装 mediapipe 失败，用 --minimal 重跑，先把摄像头跑通"
fi

# -----------------------------------------------------------------------------
say "3/5  创建虚拟环境"
# -----------------------------------------------------------------------------
if [ -d "$VENV" ] && [ -x "$PY" ]; then
  ok "已存在 .venv，复用它"
else
  rm -rf "$VENV"
  if python3 -m venv "$VENV" 2>/dev/null; then
    ok "已创建 .venv"
  else
    bad "创建虚拟环境失败"
    info "试试： python3 -m pip install --user virtualenv"
    exit 1
  fi
fi

"$PY" -m pip install --quiet --upgrade pip 2>/dev/null
ok "pip 已就绪"

# -----------------------------------------------------------------------------
say "4/5  安装依赖"
# -----------------------------------------------------------------------------
PKGS="numpy opencv-python"
# mediapipe 必须固定 0.10.35：1.0.1 在 macOS 26 上初始化 Metal 时会直接 abort
# （Check failed: service_ Service is unavailable），详见 CLAUDE.md「mediapipe 版本坑」
[ "$INSTALL_MP" -eq 1 ] && PKGS="$PKGS mediapipe==0.10.35"
info "准备安装：$PKGS"
info "（第一次装要下几十 MB，慢的话是在下载，不是卡住）"
echo

pip_try() {
  # $1 = 额外参数
  # shellcheck disable=SC2086
  "$PY" -m pip install --timeout 30 $1 $PKGS
}

INSTALLED=0
if [ "$FORCE_CN" -eq 0 ]; then
  if pip_try ""; then
    INSTALLED=1
    ok "从官方源安装完成"
  else
    echo
    warn "官方源失败或太慢，换国内镜像重试"
  fi
fi

if [ "$INSTALLED" -eq 0 ]; then
  echo
  if pip_try "-i $MIRROR"; then
    INSTALLED=1
    ok "从清华镜像安装完成"
  fi
fi

if [ "$INSTALLED" -eq 0 ]; then
  echo
  bad "依赖安装失败"
  info "如果是 mediapipe 装不上，用 --minimal 重跑先把摄像头跑通："
  info "    bash setup_env.sh --minimal"
  info "如果是网络问题，开着代理再试，或强制走镜像："
  info "    bash setup_env.sh --cn"
  exit 1
fi

# -----------------------------------------------------------------------------
say "5/5  下载姿态模型并自检"
# -----------------------------------------------------------------------------
if [ "$INSTALL_MP" -eq 1 ]; then
  if [ -f "$MODEL" ]; then
    ok "$MODEL 已存在"
  else
    info "下载 $MODEL （约 9MB）…"
    if curl -fL --connect-timeout 20 --max-time 180 -o "$MODEL.part" "$MODEL_URL" 2>/dev/null; then
      mv "$MODEL.part" "$MODEL"
      ok "模型已下载"
    else
      rm -f "$MODEL.part"
      warn "模型下载失败（这个地址在国内常连不上）"
      info "摄像头这一步不需要它，先跳过。等要跑姿态识别时："
      info "  · 开代理后重跑本脚本，或"
      info "  · 手动下载放到本目录："
      info "    $MODEL_URL"
    fi
  fi
fi

echo
"$PY" - <<'PYEOF'
import sys
print("    自检：")
try:
    import numpy, cv2
    print(f"      numpy   {numpy.__version__}")
    print(f"      opencv  {cv2.__version__}")
except Exception as e:
    print(f"      导入失败：{e}")
    sys.exit(1)
try:
    import mediapipe
    print(f"      mediapipe {mediapipe.__version__}")
except ImportError:
    print("      mediapipe 未安装（--minimal 模式，摄像头不需要它）")
except Exception as e:
    print(f"      mediapipe 有问题：{e}")
PYEOF

if [ $? -ne 0 ]; then
  bad "自检没过，依赖可能装坏了"
  info "删掉 .venv 重跑： rm -rf .venv && bash setup_env.sh"
  exit 1
fi

# -----------------------------------------------------------------------------
printf "\n\033[1;32m环境配好了。\033[0m\n\n"
printf "接下来两条命令：\n\n"
printf "  \033[1m1. 看看 Mac 认得哪些摄像头\033[0m\n"
printf "     .venv/bin/python camera_check.py --list\n\n"
printf "  \033[1m2. 打开实时画面\033[0m\n"
printf "     .venv/bin/python camera_check.py\n\n"
printf "\033[1;33m注意\033[0m：第一次跑会弹「终端想要访问摄像头」，点\033[1m好\033[0m。\n"
printf "      如果没弹框或点错了，去 系统设置 → 隐私与安全性 → 摄像头，\n"
printf "      把「终端」打开，然后\033[1m完全退出终端再重开\033[0m。\n\n"
printf "iPhone 没出现在列表里 → 先在 Mac 上打开一次「照片亭」把它唤醒，\n"
printf "详见 摄像头接入教程.md 第六节。\n\n"
