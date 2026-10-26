# =============================================================================
# Windows 环境配置 - 选题 11 健身动作计数与姿态纠正
#
# 原版 setup_env.sh 是给 macOS 用的（bash + sw_vers + .venv/bin/），
# Windows 上跑不了。这个脚本做等价的事：建 .venv -> 装依赖 -> 检查模型 -> 自检。
#
# 用法（在项目根目录）：
#     powershell -ExecutionPolicy Bypass -File setup_env_windows.ps1
#
# 可选参数：
#     -Minimal   只装 numpy/opencv/Pillow/matplotlib，不装 mediapipe
#     -Mirror    直接用清华镜像
#
# 所有东西都装在项目内的 .venv 里，删掉 .venv 即可完全还原。
# =============================================================================

param(
    [switch]$Minimal,
    [switch]$Mirror
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Venv   = Join-Path $ScriptDir ".venv"
$Py     = Join-Path $Venv "Scripts\python.exe"
$Model  = "pose_landmarker_lite.task"
$ModelUrl = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
$MirrorUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 中文输出在 Windows 控制台需要 UTF-8，否则 GBK 会抛 UnicodeEncodeError
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Write-Say  { param($m) Write-Host ""; Write-Host ("==> " + $m) -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host ("    [OK] " + $m) -ForegroundColor Green }
function Write-Bad  { param($m) Write-Host ("    [XX] " + $m) -ForegroundColor Red }
function Write-Warn2{ param($m) Write-Host ("    [!!] " + $m) -ForegroundColor Yellow }
function Write-Info { param($m) Write-Host ("         " + $m) -ForegroundColor DarkGray }

Write-Host ""
Write-Host "Windows 环境配置 - 选题 11" -ForegroundColor White
Write-Host ("工作目录：" + $ScriptDir)

# ---------------------------------------------------------------- 1/5 检查系统
Write-Say "1/5  检查系统"
Write-Ok ([System.Environment]::OSVersion.VersionString)

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Bad "没有找到 python"
    Write-Info "从 python.org 装一个 3.10~3.12，安装时勾选 Add to PATH"
    exit 1
}
$pyVer   = & python -c "import sys;print('%d.%d.%d'%sys.version_info[:3])"
$pyMinor = & python -c "import sys;print(sys.version_info[1])"
Write-Ok ("Python " + $pyVer + "   (" + $pyCmd.Source + ")")
if ([int]$pyMinor -lt 9) {
    Write-Bad "Python 版本太低（需要 3.9 以上）"
    exit 1
}

# ---------------------------------------------------------------- 2/5 虚拟环境
Write-Say "2/5  创建虚拟环境"
if (Test-Path $Py) {
    Write-Ok "已存在 .venv，复用它"
} else {
    if (Test-Path $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force }
    & python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Write-Bad "创建虚拟环境失败"; exit 1 }
    Write-Ok "已创建 .venv"
}

# ---------------------------------------------------------------- 3/5 依赖
Write-Say "3/5  安装依赖"
& $Py -m pip install --quiet --upgrade pip 2>$null
Write-Ok "pip 已就绪"

$pkgs = @("numpy", "opencv-python", "Pillow", "matplotlib")
if (-not $Minimal) { $pkgs += "mediapipe" }
Write-Info ("准备安装：" + ($pkgs -join " "))

$pipArgs = @()
if ($Mirror) { $pipArgs = @("-i", $MirrorUrl) }

& $Py -m pip install @pipArgs @pkgs
if ($LASTEXITCODE -ne 0) {
    Write-Warn2 "直接安装失败，换清华镜像重试"
    & $Py -m pip install -i $MirrorUrl @pkgs
    if ($LASTEXITCODE -ne 0) { Write-Bad "依赖安装失败"; exit 1 }
}
Write-Ok "依赖安装完成"

# ---------------------------------------------------------------- 4/5 模型
Write-Say "4/5  检查姿态模型"
if (Test-Path $Model) {
    $mb = [math]::Round((Get-Item $Model).Length / 1MB, 2)
    Write-Ok ($Model + " 已存在（" + $mb + " MB）")
} elseif ($Minimal) {
    Write-Info "-Minimal 模式，跳过模型"
} else {
    Write-Info ("下载 " + $Model + " （约 5.5 MB）...")
    try {
        Invoke-WebRequest -Uri $ModelUrl -OutFile ($Model + ".part") -TimeoutSec 180
        Move-Item ($Model + ".part") $Model
        Write-Ok "模型已下载"
    } catch {
        Remove-Item ($Model + ".part") -ErrorAction SilentlyContinue
        Write-Warn2 "模型下载失败（这个地址在国内常连不上）"
        Write-Info "开代理后重跑本脚本，或手动下载放到本目录："
        Write-Info ("  " + $ModelUrl)
    }
}

# ---------------------------------------------------------------- 5/5 自检
Write-Say "5/5  自检"
$selfCheck = @'
import sys
print("    Python      " + sys.version.split()[0])
mods = ["numpy", "cv2", "PIL", "matplotlib", "mediapipe", "tkinter"]
bad = 0
for m in mods:
    try:
        mod = __import__(m)
        v = getattr(mod, "__version__", "") or getattr(mod, "TkVersion", "")
        print("    %-12s %s" % (m, v))
    except Exception as e:
        if m == "mediapipe":
            print("    %-12s 未安装（-Minimal 模式，数据回放与测试不需要它）" % m)
        else:
            print("    %-12s 失败：%s" % (m, e))
            bad = 1
sys.exit(bad)
'@
& $Py -c $selfCheck
if ($LASTEXITCODE -ne 0) {
    Write-Bad "自检没过。删掉 .venv 重跑： Remove-Item .venv -Recurse -Force; .\setup_env_windows.ps1"
    exit 1
}

# ---------------------------------------------------------------- 完成
Write-Host ""
Write-Host "环境配好了。" -ForegroundColor Green
Write-Host ""
Write-Host "接下来常用命令（在项目根目录）：" -ForegroundColor White
Write-Host ""
Write-Host "  跑自动化测试（43 项）"
Write-Host "     .\.venv\Scripts\python.exe test_pose_logic.py"
Write-Host "     .\.venv\Scripts\python.exe test_training_manager.py"
Write-Host ""
Write-Host "  合成轨迹回归（13 条）"
Write-Host "     .\.venv\Scripts\python.exe motion_synth.py --all"
Write-Host ""
Write-Host "  校验动作配置"
Write-Host "     .\.venv\Scripts\python.exe validate_config.py"
Write-Host ""
Write-Host "  关键点数据回放（不需摄像头，秒出结果）"
Write-Host "     .\.venv\Scripts\python.exe pose_player.py --data samples\squat_standard.json"
Write-Host ""
Write-Host "  全模块图形界面"
Write-Host "     .\.venv\Scripts\python.exe fitness_ui.py"
Write-Host ""
Write-Host "  看有哪些摄像头"
Write-Host "     .\.venv\Scripts\python.exe camera_check.py --list"
Write-Host ""
Write-Host "提示：Windows 控制台默认 GBK，中文可能报 UnicodeEncodeError。" -ForegroundColor Yellow
Write-Host "      先执行  `$env:PYTHONUTF8=`"1`"  再跑，或者直接用 start_app.ps1。" -ForegroundColor Yellow
