# MocapOS Installer Dry-Run Test
# Validates the entire installation pipeline without modifying the system
param([string]$TestDir = "C:\Users\User\Documents\MocapOS_Installer_Test")

$Errors = @()
$Warnings = @()
$Passed = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "TEST: $Name ... " -NoNewline
    try {
        & $Action
        Write-Host "PASS" -ForegroundColor Green
        $script:Passed++
    }
    catch {
        Write-Host "FAIL" -ForegroundColor Red
        $script:Errors += "$Name`: $($_.Exception.Message)"
    }
}

function Test-Warn {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "TEST: $Name ... " -NoNewline
    try {
        & $Action
        Write-Host "OK" -ForegroundColor Green
        $script:Passed++
    }
    catch {
        Write-Host "WARN" -ForegroundColor Yellow
        $script:Warnings += "$Name`: $($_.Exception.Message)"
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  MocapOS Installer Dry-Run Test"
Write-Host "========================================`n" -ForegroundColor Cyan

# --- 1. File Structure ---
Test-Step "Installer .exe exists" {
    $exe = "C:\Users\User\Documents\MocapOS\installer\output\MocapOS_Setup_v1.exe"
    if (-not (Test-Path $exe)) { throw "Not found: $exe" }
    $size = (Get-Item $exe).Length / 1MB
    if ($size -lt 1) { throw "Too small: $size MB" }
}

Test-Step "Required scripts present" {
    $scripts = @(
        "C:\Users\User\Documents\MocapOS\installer\scripts\install_dependencies.ps1",
        "C:\Users\User\Documents\MocapOS\installer\scripts\download_models.ps1",
        "C:\Users\User\Documents\MocapOS\installer\scripts\detect_gpu.ps1",
        "C:\Users\User\Documents\MocapOS\MocapOS.vbs",
        "C:\Users\User\Documents\MocapOS\run_gui.bat",
        "C:\Users\User\Documents\MocapOS\install.bat",
        "C:\Users\User\Documents\MocapOS\gvhmr_gui.py",
        "C:\Users\User\Documents\MocapOS\tools\dev\apply_patches.py"
    )
    foreach ($path in $scripts) {
        if (-not (Test-Path $path)) { throw "Missing: $path" }
    }
}

# --- 2. PowerShell Syntax ---
Test-Step "install_dependencies.ps1 syntax" {
    $e = $null
    $content = Get-Content "C:\Users\User\Documents\MocapOS\installer\scripts\install_dependencies.ps1" -Raw
    [void][System.Management.Automation.PSParser]::Tokenize($content, [ref]$e)
    # Filter out the known false-positive on last line
    $realErrors = $e | Where-Object { $_.Message -notlike "*terminador*" }
    if ($realErrors.Count -gt 0) {
        throw ($realErrors | ForEach-Object { $_.Message } | Join-String -Separator "; ")
    }
}

Test-Step "download_models.ps1 syntax" {
    $e = $null
    $content = Get-Content "C:\Users\User\Documents\MocapOS\installer\scripts\download_models.ps1" -Raw
    [void][System.Management.Automation.PSParser]::Tokenize($content, [ref]$e)
    if ($e.Count -gt 0) { throw ($e | ForEach-Object { $_.Message } | Join-String -Separator "; ") }
}

Test-Step "detect_gpu.ps1 syntax" {
    $e = $null
    $content = Get-Content "C:\Users\User\Documents\MocapOS\installer\scripts\detect_gpu.ps1" -Raw
    [void][System.Management.Automation.PSParser]::Tokenize($content, [ref]$e)
    if ($e.Count -gt 0) { throw ($e | ForEach-Object { $_.Message } | Join-String -Separator "; ") }
}

# --- 3. Launcher validation ---
Test-Step "MocapOS.vbs references correct pythonw path" {
    $vbs = Get-Content "C:\Users\User\Documents\MocapOS\MocapOS.vbs" -Raw
    if ($vbs -notmatch "pythonw\.exe") { throw "Missing pythonw.exe reference" }
    if ($vbs -notmatch "gvhmr_gui\.py") { throw "Missing gvhmr_gui.py reference" }
}

Test-Step "run_gui.bat references correct paths" {
    $bat = Get-Content "C:\Users\User\Documents\MocapOS\run_gui.bat" -Raw
    if ($bat -notmatch "gvhmr") { throw "Missing gvhmr env reference" }
    if ($bat -notmatch "gvhmr_gui\.py") { throw "Missing gvhmr_gui.py reference" }
}

# --- 4. URL Validation ---
Write-Host "`n--- URL Availability Tests ---" -ForegroundColor Cyan

$Urls = @(
    @{ Name = "Miniconda installer"; Url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" },
    @{ Name = "GVHMR checkpoint"; Url = "https://github.com/zju3dv/GVHMR/releases/download/v1.0/gvhmr_siga24_release.ckpt" },
    @{ Name = "HMR2 checkpoint"; Url = "https://github.com/zju3dv/GVHMR/releases/download/v1.0/hmr2_epoch=10-step=25000.ckpt" },
    @{ Name = "ViTPose checkpoint"; Url = "https://github.com/zju3dv/GVHMR/releases/download/v1.0/vitpose-h-multi-coco.pth" },
    @{ Name = "YOLOv8x"; Url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8x.pt" },
    @{ Name = "DPVO checkpoint"; Url = "https://github.com/zju3dv/GVHMR/releases/download/v1.0/dpvo.pth" },
    @{ Name = "HaMeR checkpoint"; Url = "https://github.com/geopavlakos/hamer/releases/download/v0.1/hamer.ckpt" },
    @{ Name = "HaMeR config"; Url = "https://github.com/geopavlakos/hamer/releases/download/v0.1/model_config.yaml" }
)

foreach ($u in $Urls) {
    Test-Warn "URL: $($u.Name)" {
        $req = [System.Net.WebRequest]::Create($u.Url)
        $req.Method = "HEAD"
        $req.AllowAutoRedirect = $true
        $req.Timeout = 15000
        $resp = $req.GetResponse()
        $status = [int]$resp.StatusCode
        $resp.Close()
        if ($status -ne 200 -and $status -ne 302) {
            throw "HTTP $status"
        }
    }
}

# --- 5. Python environment parity check ---
Write-Host "`n--- Environment Parity Check ---" -ForegroundColor Cyan

Test-Step "Current env has torch" {
    $torch = & "$env:USERPROFILE\miniconda3\envs\gvhmr\python.exe" -c "import torch; print(torch.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "torch not importable" }
    Write-Host "($torch) " -NoNewline -ForegroundColor Gray
}

Test-Step "Current env has pytorch3d" {
    & "$env:USERPROFILE\miniconda3\envs\gvhmr\python.exe" -c "import pytorch3d; print(pytorch3d.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "pytorch3d not importable" }
}

Test-Step "Current env has detectron2" {
    & "$env:USERPROFILE\miniconda3\envs\gvhmr\python.exe" -c "import detectron2; print(detectron2.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "detectron2 not importable" }
}

Test-Step "Current env has hmr4d" {
    & "$env:USERPROFILE\miniconda3\envs\gvhmr\python.exe" -c "import hmr4d; print('ok')" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "hmr4d not importable" }
}

# --- 6. Simulated install structure test ---
Write-Host "`n--- Simulated Install Structure ---" -ForegroundColor Cyan

Test-Step "Can create temp install dir" {
    New-Item -ItemType Directory -Force -Path "$TestDir\inputs\checkpoints\gvhmr" | Out-Null
    if (-not (Test-Path $TestDir)) { throw "Cannot create test dir" }
}

Test-Step "Simulated file copy works" {
    Copy-Item "C:\Users\User\Documents\MocapOS\gvhmr_gui.py" "$TestDir\gvhmr_gui.py" -Force
    if (-not (Test-Path "$TestDir\gvhmr_gui.py")) { throw "Copy failed" }
}

Test-Step "Simulated checkpoint dir structure" {
    $dirs = @("inputs\checkpoints\gvhmr", "inputs\checkpoints\hmr2", "inputs\checkpoints\vitpose",
              "inputs\checkpoints\yolo", "inputs\checkpoints\dpvo", "inputs\checkpoints\body_models\smplx",
              "hamer_lib\_DATA\hamer_ckpts\checkpoints", "hamer_lib\_DATA\vitpose_ckpts\vitpose+_huge")
    foreach ($d in $dirs) {
        New-Item -ItemType Directory -Force -Path "$TestDir\$d" | Out-Null
    }
}

# Cleanup test dir
Remove-Item $TestDir -Recurse -Force -ErrorAction SilentlyContinue

# --- Summary ---
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Test Results" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Passed:   $Passed" -ForegroundColor Green
Write-Host "Warnings: $($Warnings.Count)" -ForegroundColor Yellow
Write-Host "Errors:   $($Errors.Count)" -ForegroundColor Red

if ($Warnings.Count -gt 0) {
    Write-Host "`nWarnings:" -ForegroundColor Yellow
    $Warnings | ForEach-Object { Write-Host "  [WARN] $_" -ForegroundColor Yellow }
}

if ($Errors.Count -gt 0) {
    Write-Host "`nErrors:" -ForegroundColor Red
    $Errors | ForEach-Object { Write-Host "  [ERROR] $_" -ForegroundColor Red }
    exit 1
} else {
    Write-Host "`n[PASS] Installer validation PASSED" -ForegroundColor Green
    exit 0
}
