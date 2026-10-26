# =============================================================================
# 一键启动 - 选题 11 健身动作计数与姿态纠正（Windows）
#
# 用法（在项目根目录）：
#     powershell -ExecutionPolicy Bypass -File start_app.ps1            # 图形界面
#     powershell -ExecutionPolicy Bypass -File start_app.ps1 -Test      # 跑全部测试
#     powershell -ExecutionPolicy Bypass -File start_app.ps1 -Demo      # 示例数据回放
#     powershell -ExecutionPolicy Bypass -File start_app.ps1 -Camera    # 列出摄像头
#
# 这个脚本只做两件事：设好 UTF-8（避免 Windows 控制台 GBK 报错），
# 然后用项目自己的 .venv 跑对应文件。
# =============================================================================

param(
    [switch]$Test,
    [switch]$Demo,
    [switch]$Camera,
    [switch]$Modules,
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Windows 控制台默认 GBK，不加这两行中文输出会抛 UnicodeEncodeError
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "还没配环境。先跑：" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File setup_env_windows.ps1" -ForegroundColor White
    exit 1
}

function Invoke-Py {
    param($File, [string[]]$ArgList)
    Write-Host ""
    Write-Host (">>> " + $File + " " + ($ArgList -join ' ')) -ForegroundColor Cyan
    # OpenCV / mediapipe 会往 stderr 打大量警告（XNNPACK、FFMPEG 等），
    # PowerShell 默认会把它当成错误中断脚本，这里临时放宽成只显示不中断。
    # 关键：把子进程输出全部写进主机流，绝不让它混进函数返回值（否则退出码会被吞掉）。
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Py $File @ArgList 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($code -ne 0) { Write-Host ("退出码：" + $code) -ForegroundColor Red }
    return $code
}

if ($Modules) {
    Write-Host "======== 按模块跑测试（10 个功能模块）========" -ForegroundColor White
    $args2 = @()
    if ($Only.Count -gt 0) { $args2 = $Only }
    $code = Invoke-Py -File "tests\run_module_tests.py" -ArgList $args2
    Write-Host ""
    if ($code -eq 0) {
        Write-Host "全部模块通过 OK" -ForegroundColor Green
    } else {
        Write-Host "有模块用例失败，看上面的 FAIL 行" -ForegroundColor Red
        exit 1
    }
}
elseif ($Test) {
    Write-Host "======== 全部测试 ========" -ForegroundColor White
    $fail = 0
    if ((Invoke-Py -File "test_pose_logic.py" -ArgList @()) -ne 0)       { $fail++ }
    if ((Invoke-Py -File "test_training_manager.py" -ArgList @()) -ne 0) { $fail++ }
    if ((Invoke-Py -File "motion_synth.py" -ArgList @("--all")) -ne 0)   { $fail++ }
    if ((Invoke-Py -File "validate_config.py" -ArgList @()) -ne 0)       { $fail++ }
    Write-Host ""
    Write-Host "======== 结果 ========" -ForegroundColor White
    if ($fail -eq 0) {
        Write-Host "四个套件全部通过 OK" -ForegroundColor Green
    } else {
        Write-Host ("$fail 个套件失败") -ForegroundColor Red
        exit 1
    }
}
elseif ($Demo) {
    Write-Host "======== 示例数据回放（不需要摄像头）========" -ForegroundColor White
    $samples = @(
        @{ f = "samples\squat_standard.json";  d = "深蹲 · 标准" },
        @{ f = "samples\pushup_sag.json";      d = "俯卧撑 · 塌腰" },
        @{ f = "samples\jack_standard.json";   d = "开合跳 · 标准" }
    )
    foreach ($s in $samples) {
        Write-Host ""
        Write-Host ("--- " + $s.d + " ---") -ForegroundColor Yellow
        Invoke-Py -File "pose_player.py" -ArgList @("--data", $s.f)
    }
}
elseif ($Camera) {
    Invoke-Py -File "camera_check.py" -ArgList @("--list")
}
else {
    Write-Host "启动全模块图形界面…" -ForegroundColor Cyan
    Write-Host "提示：输入选「关键点数据」→ 选 samples 里的 json → 选动作 → 开始测试" -ForegroundColor DarkGray
    Invoke-Py -File "fitness_ui.py" -ArgList @()
}
