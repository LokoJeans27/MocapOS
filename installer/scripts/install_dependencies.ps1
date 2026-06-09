# MocapOS Dependency Installer — Step-based (Fixed v2)
# Run by Inno Setup after files are extracted
param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet(1,2,3,4)]
    [int]$Step,
    
    [Parameter(Mandatory=$false)]
    [string]$GPURec = "AUTO"
)

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$LogFile = "$InstallDir\installer\install.log"
$ProgressFile = "$InstallDir\installer\progress.txt"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $Message" | Out-File -FilePath $LogFile -Encoding UTF8 -Append
    Write-Host $Message
}

function Write-ProgressStatus {
    param([string]$Message, [int]$Percent)
    "$Percent|$Message" | Out-File -FilePath $ProgressFile -Encoding UTF8
    Write-Log "$Message ($Percent%)"
}

function Test-Command {
    param([string]$Cmd)
    $null = Get-Command $Cmd -ErrorAction SilentlyContinue
    return $?
}

function Test-NvidiaGPU {
    try {
        $gpu = Get-WmiObject -Query "SELECT Name FROM Win32_VideoController" -ErrorAction SilentlyContinue
        foreach ($g in $gpu) {
            if ($g.Name -match "NVIDIA|GeForce|RTX|GTX|Quadro|Tesla") {
                return $true
            }
        }
    } catch {}
    # Also try nvidia-smi
    try {
        $null = & nvidia-smi -L 2>$null
        if ($LASTEXITCODE -eq 0) { return $true }
    } catch {}
    return $false
}

function Accept-CondaToS {
    param([string]$CondaBat)
    Write-Log "Accepting Anaconda Terms of Service..."
    $channels = @(
        "https://repo.anaconda.com/pkgs/main",
        "https://repo.anaconda.com/pkgs/r",
        "https://repo.anaconda.com/pkgs/msys2"
    )
    foreach ($ch in $channels) {
        & $CondaBat tos accept --override-channels --channel $ch 2>&1 | ForEach-Object { Write-Log $_ }
    }
    Write-Log "ToS accepted."
}

function Install-Git {
    param([string]$CondaBat, [string]$EnvName)
    Write-Log "Git not found. Installing via conda..."
    & $CondaBat install -n $EnvName git -y 2>&1 | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "WARNING: Failed to install git via conda. Some builds may fail."
        return $false
    }
    Write-Log "Git installed successfully."
    return $true
}

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path "$InstallDir\installer" | Out-Null
if (-not (Test-Path $LogFile)) {
    "=== MocapOS Installation Log ===" | Out-File -FilePath $LogFile -Encoding UTF8
}

# Common paths (used by multiple steps)
$EnvName = "gvhmr"
$CondaBat = "$env:USERPROFILE\miniconda3\condabin\conda.bat"
$PythonExe = "$env:USERPROFILE\miniconda3\envs\$EnvName\python.exe"
$Pip = "$env:USERPROFILE\miniconda3\envs\$EnvName\Scripts\pip.exe"

# Ensure git is available globally for all steps (needed for pip install git+https://)
$condaGitBin = "$env:USERPROFILE\miniconda3\envs\$EnvName\Library\bin"
$condaGitExe = "$condaGitBin\git.exe"
if (-not (Test-Command "git")) {
    if (Test-Path $condaGitExe) {
        $env:PATH = "$condaGitBin;$env:PATH"
        Write-Log "Added conda git to PATH: $condaGitBin"
    }
}

# Track missing components for post-install report
$MissingComponents = @()
$PostInstallFile = "$InstallDir\POST_INSTALL_STEPS.txt"

# ========== STEP 1: Miniconda + Conda Environment + Git ==========
if ($Step -eq 1) {
    Write-ProgressStatus "Checking Miniconda3..." 5
    
    $CondaExe = "$env:USERPROFILE\miniconda3\condabin\conda.bat"
    if (-not (Test-Path $CondaExe)) {
        Write-Log "Miniconda3 not found. Downloading..."
        Write-ProgressStatus "Downloading Miniconda3..." 10
        
        $MinicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
        $MinicondaInstaller = "$env:TEMP\Miniconda3Installer.exe"
        
        try {
            Invoke-WebRequest -Uri $MinicondaUrl -OutFile $MinicondaInstaller -UseBasicParsing
            Write-Log "Installing Miniconda3..."
            Write-ProgressStatus "Installing Miniconda3..." 15
            Start-Process -FilePath $MinicondaInstaller -ArgumentList "/S /D=$env:USERPROFILE\miniconda3" -Wait -NoNewWindow
            Write-Log "Miniconda3 installed."
            
            Start-Sleep -Seconds 3
            
            if (-not (Test-Path $CondaExe)) {
                Write-Log "ERROR: Miniconda3 installed but conda.bat not found at $CondaExe"
                exit 1
            }
        }
        catch {
            Write-Log "ERROR: Failed to install Miniconda3: $($_.Exception.Message)"
            exit 1
        }
    }
    else {
        Write-Log "Miniconda3 found at $CondaExe"
    }
    
    # Accept Anaconda ToS before any conda operation
    Accept-CondaToS -CondaBat $CondaBat
    
    Write-ProgressStatus "Creating Python environment..." 20
    
    $envExists = & $CondaBat env list 2>$null | Select-String "^$EnvName\s"
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: conda env list failed with exit code $LASTEXITCODE"
        exit 1
    }
    if ($envExists) {
        Write-Log "Conda environment '$EnvName' already exists. Reusing."
    } else {
        Write-Log "Creating conda environment '$EnvName'..."
        & $CondaBat create -n $EnvName python=3.10 -y 2>&1 | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "ERROR: Failed to create conda environment '$EnvName' (exit $LASTEXITCODE)"
            exit 1
        }
        Write-Log "Conda environment '$EnvName' created."
    }
    
    # Verify python.exe exists in the environment
    if (-not (Test-Path $PythonExe)) {
        Write-Log "ERROR: Python executable not found at $PythonExe after Step 1"
        exit 1
    }
    
    # Install Git inside the conda environment if not available system-wide
    $gitAvailable = Test-Command "git"
    if (-not $gitAvailable) {
        Write-Log "Git not found in PATH. Installing into conda environment..."
        Install-Git -CondaBat $CondaBat -EnvName $EnvName | Out-Null
    } else {
        Write-Log "Git found in PATH."
    }
    
    Write-ProgressStatus "Step 1 complete" 25
    exit 0
}

# ========== STEP 2: PyTorch + Requirements + PyTorch3D + Detectron2 ==========
if ($Step -eq 2) {
    # Verify binaries exist before starting
    if (-not (Test-Path $PythonExe)) {
        Write-Log "ERROR: Python not found at $PythonExe. Step 1 may have failed."
        exit 1
    }
    if (-not (Test-Path $Pip)) {
        Write-Log "ERROR: pip not found at $Pip. Step 1 may have failed."
        exit 1
    }
    
    # Detect GPU and choose appropriate PyTorch
    $hasNvidia = Test-NvidiaGPU
    if ($hasNvidia) {
        Write-Log "NVIDIA GPU detected. Installing PyTorch with CUDA support."
        Write-ProgressStatus "Installing PyTorch with CUDA..." 30
        $TorchIndex = "https://download.pytorch.org/whl/cu128"
    } else {
        Write-Log "WARNING: No NVIDIA GPU detected. Installing PyTorch CPU-only. Some features will be limited."
        Write-ProgressStatus "Installing PyTorch (CPU-only, no GPU detected)..." 30
        $TorchIndex = "https://download.pytorch.org/whl/cpu"
    }
    
    & $Pip install torch torchvision --index-url $TorchIndex 2>&1 | ForEach-Object { Write-Log $_ }
    
    # If CUDA 12.8 failed and we have GPU, try CUDA 12.6
    if ($hasNvidia) {
        $torchCheck = & $PythonExe -c "import torch; print(torch.__version__)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $torchCheck) {
            Write-Log "CUDA 12.8 failed, trying CUDA 12.6..."
            $TorchIndex = "https://download.pytorch.org/whl/cu126"
            & $Pip install torch torchvision --index-url $TorchIndex 2>&1 | ForEach-Object { Write-Log $_ }
        }
    }
    
    $torchVersion = & $PythonExe -c "import torch; print(torch.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $torchVersion) {
        Write-Log "ERROR: PyTorch installation failed"
        exit 1
    }
    Write-Log "PyTorch installed: $torchVersion"
    
    Write-ProgressStatus "Installing Python dependencies..." 40
    $ReqFile = "$InstallDir\requirements.txt"
    if (Test-Path $ReqFile) {
        & $Pip install -r $ReqFile 2>&1 | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "WARNING: Some requirements failed to install (exit $LASTEXITCODE)"
        }
    }
    Write-Log "Dependencies installed."
    
    # Check for C++ compiler (needed for pytorch3d and detectron2 on Windows)
    $hasCL = Test-Command "cl.exe"
    if (-not $hasCL) {
        Write-Log "No C++ compiler found. Installing Visual Studio Build Tools..."
        Write-ProgressStatus "Installing Visual C++ Build Tools (~2GB) ..." 32
        
        $VSBootstrapper = "$env:TEMP\vs_buildtools.exe"
        try {
            Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_buildtools.exe" -OutFile $VSBootstrapper -UseBasicParsing
            Write-Log "Downloaded VS Build Tools installer. Installing..."
            
            $vsArgs = @(
                "--quiet", "--wait", "--norestart", "--nocache",
                "--installPath", "C:\BuildTools",
                "--add", "Microsoft.VisualStudio.Workload.VCTools",
                "--add", "Microsoft.VisualStudio.Component.Windows11SDK.22621",
                "--add", "Microsoft.VisualStudio.Component.VC.CMake.Project",
                "--add", "Microsoft.VisualStudio.Component.VC.14.38.17.8.x86.x64"
            )
            
            Start-Process -FilePath $VSBootstrapper -ArgumentList $vsArgs -Wait -NoNewWindow
            Write-Log "VS Build Tools installation completed."
            
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
            $hasCL = Test-Command "cl.exe"
            if (-not $hasCL) {
                $clPaths = @(
                    "C:\BuildTools\VC\Tools\MSVC\14.38.33130\bin\Hostx64\x64\cl.exe",
                    "C:\BuildTools\VC\Tools\MSVC\14.39.33519\bin\Hostx64\x64\cl.exe",
                    "C:\BuildTools\VC\Tools\MSVC\14.40.33807\bin\Hostx64\x64\cl.exe",
                    "C:\BuildTools\VC\Tools\MSVC\14.41.34120\bin\Hostx64\x64\cl.exe",
                    "C:\BuildTools\VC\Tools\MSVC\14.42.34433\bin\Hostx64\x64\cl.exe"
                )
                foreach ($clPath in $clPaths) {
                    if (Test-Path $clPath) {
                        $env:PATH = "$(Split-Path $clPath);$env:PATH"
                        $hasCL = $true
                        Write-Log "Found cl.exe at: $clPath"
                        break
                    }
                }
            }
            
            if (-not $hasCL) {
                Write-Log "WARNING: VS Build Tools installed but cl.exe not found in PATH."
            }
        }
        catch {
            Write-Log "WARNING: Failed to install VS Build Tools: $($_.Exception.Message)"
        }
    } else {
        Write-Log "C++ compiler (cl.exe) found."
    }
    
    # Ensure git is available (installed in Step 1, but verify)
    $gitAvailable = Test-Command "git"
    $condaGitBin = "$env:USERPROFILE\miniconda3\envs\$EnvName\Library\bin"
    $condaGitExe = "$condaGitBin\git.exe"
    
    if (-not $gitAvailable) {
        if (Test-Path $condaGitExe) {
            $env:PATH = "$condaGitBin;$env:PATH"
            $gitAvailable = $true
            Write-Log "Found git in conda environment. Added to PATH."
        }
    } else {
        # Even if git is found, ensure conda git bin is in PATH for pip
        if (Test-Path $condaGitExe) {
            $env:PATH = "$condaGitBin;$env:PATH"
            Write-Log "Ensured conda git bin is in PATH for pip."
        }
    }
    
    # PyTorch3D - try pre-built wheel first, then source build if possible
    Write-ProgressStatus "Installing PyTorch3D..." 50
    & $Pip install pytorch3d 2>&1 | ForEach-Object { Write-Log $_ }
    $pt3dCheck = & $PythonExe -c "import pytorch3d; print('OK')" 2>$null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Pre-built PyTorch3D wheel not available. Attempting build from source..."
        if ($hasCL -and $gitAvailable) {
            if ($hasNvidia) {
                # Install CUDA toolkit for build
                & $CondaBat install -n $EnvName cuda-toolkit cuda-cccl -c nvidia -y 2>&1 | ForEach-Object { Write-Log $_ }
                
                $env:DISTUTILS_USE_SDK = "1"
                $env:FORCE_CUDA = "1"
                $env:CUDA_HOME = "$env:USERPROFILE\miniconda3\envs\$EnvName\Library"
                $env:CUB_HOME = "$env:CUDA_HOME\include\cub"
                $env:PATH = "$env:CUDA_HOME\bin;$env:PATH"
                
                & $Pip install --no-build-isolation --no-cache-dir "git+https://github.com/facebookresearch/pytorch3d.git" 2>&1 | ForEach-Object { Write-Log $_ }
            } else {
                # CPU-only build
                Write-Log "Building PyTorch3D CPU-only (no GPU)..."
                $env:FORCE_CUDA = "0"
                & $Pip install --no-build-isolation --no-cache-dir "git+https://github.com/facebookresearch/pytorch3d.git" 2>&1 | ForEach-Object { Write-Log $_ }
            }
            
            $pt3dCheck2 = & $PythonExe -c "import pytorch3d; print('OK')" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Log "WARNING: PyTorch3D build from source failed."
                $MissingComponents += "pytorch3d (build failed - see POST_INSTALL_STEPS.txt)"
            }
        } else {
            $reason = if (-not $hasCL) { "no C++ compiler" } else { "no git" }
            Write-Log "WARNING: Skipping PyTorch3D build - $reason."
            $MissingComponents += "pytorch3d (install Visual C++ Build Tools + git, then run: pip install 'git+https://github.com/facebookresearch/pytorch3d.git')"
        }
    }
    
    # Detectron2
    Write-ProgressStatus "Installing Detectron2..." 55
    if ($hasCL -and $gitAvailable) {
        & $Pip install --no-build-isolation "git+https://github.com/facebookresearch/detectron2.git" 2>&1 | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -ne 0) {
            Write-Log "WARNING: Detectron2 installation failed."
            if (-not $hasCL) {
                $MissingComponents += "detectron2 (install Visual C++ Build Tools, then run: pip install 'git+https://github.com/facebookresearch/detectron2.git')"
            } else {
                $MissingComponents += "detectron2 (build failed - see install.log)"
            }
        }
    } else {
        $reason = if (-not $hasCL) { "no C++ compiler" } else { "no git" }
        Write-Log "WARNING: Skipping Detectron2 - $reason."
        $MissingComponents += "detectron2 (install Visual C++ Build Tools + git, then run: pip install 'git+https://github.com/facebookresearch/detectron2.git')"
    }
    
    # Write post-install instructions if anything is missing
    if ($MissingComponents.Count -gt 0) {
        $instructions = @"
================================================================================
  MocapOS - Additional Installation Steps Required
================================================================================

The automated installer could not complete the following steps.

MISSING COMPONENTS:
$(foreach ($c in $MissingComponents) { "  - $c`n" })

STEP-BY-STEP FIX:

1. Install Visual Studio Build Tools (or full Visual Studio 2022):
   Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   Required components:
     - MSVC v143 - VS 2022 C++ x64/x86 build tools
     - Windows 11 SDK (or Windows 10 SDK)
     - C++ CMake tools for Windows

2. After installation, open "Developer Command Prompt for VS 2022" and run:

   conda activate gvhmr

   # Install pytorch3d
   pip install --no-build-isolation --no-cache-dir "git+https://github.com/facebookresearch/pytorch3d.git"

   # Install detectron2
   pip install --no-build-isolation "git+https://github.com/facebookresearch/detectron2.git"

3. Verify with:
   python -c "import torch; import pytorch3d; import detectron2; print('All OK')"

================================================================================
"@
        $instructions | Out-File -FilePath $PostInstallFile -Encoding UTF8
        Write-Log "Post-install instructions written to: $PostInstallFile"
    }
    
    Write-ProgressStatus "Step 2 complete" 60
    exit 0
}

# ========== STEP 3: Project Packages + Patches + Models ==========
if ($Step -eq 3) {
    if (-not (Test-Path $PythonExe)) {
        Write-Log "ERROR: Python not found at $PythonExe. Step 1 may have failed."
        exit 1
    }
    if (-not (Test-Path $Pip)) {
        Write-Log "ERROR: pip not found at $Pip. Step 1 may have failed."
        exit 1
    }
    
    Write-ProgressStatus "Installing MocapOS packages..." 65
    
    cd $InstallDir
    & $Pip install -e . 2>&1 | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "WARNING: MocapOS package install had issues (exit $LASTEXITCODE)"
    }
    
    cd "$InstallDir\hamer_lib"
    & $Pip install --no-build-isolation -e ".[all]" 2>&1 | ForEach-Object { Write-Log $_ }
    & $Pip install --no-build-isolation -e . 2>&1 | ForEach-Object { Write-Log $_ }
    
    Write-Log "Project packages installed."
    
    Write-ProgressStatus "Applying Windows compatibility patches..." 70
    $PatchScript = "$InstallDir\tools\dev\apply_patches.py"
    if (Test-Path $PatchScript) {
        & $PythonExe $PatchScript 2>&1 | ForEach-Object { Write-Log $_ }
        Write-Log "Patches applied."
    } else {
        Write-Log "WARNING: apply_patches.py not found at $PatchScript"
    }
    
    Write-ProgressStatus "Downloading AI models (~6GB)..." 75
    $DownloadScript = "$InstallDir\installer\scripts\download_models.ps1"
    if (Test-Path $DownloadScript) {
        & powershell.exe -ExecutionPolicy Bypass -NoProfile -File $DownloadScript -InstallDir $InstallDir 2>&1 | ForEach-Object { Write-Log $_ }
        Write-Log "Models downloaded."
    } else {
        Write-Log "WARNING: download_models.ps1 not found."
    }
    
    Write-ProgressStatus "Step 3 complete" 90
    exit 0
}

# ========== STEP 4: Verify Installation ==========
if ($Step -eq 4) {
    if (-not (Test-Path $PythonExe)) {
        Write-Log "ERROR: Python not found at $PythonExe. Installation incomplete."
        exit 1
    }
    
    Write-ProgressStatus "Verifying installation..." 95
    
    # Check core components first
    $torchOK = $false
    $hmr4dOK = $false
    $pytorch3dOK = $false
    $detectron2OK = $false
    
    $torchOut = & $PythonExe -c "import torch; print('TORCH_OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and ($torchOut -match "TORCH_OK")) {
        $torchOK = $true
        Write-Log "Core check: torch OK"
    } else {
        Write-Log "ERROR: torch import failed: $torchOut"
    }
    
    $hmr4dOut = & $PythonExe -c "import hmr4d; print('HMR4D_OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and ($hmr4dOut -match "HMR4D_OK")) {
        $hmr4dOK = $true
        Write-Log "Core check: hmr4d OK"
    } else {
        Write-Log "WARNING: hmr4d import failed: $hmr4dOut"
    }
    
    # Optional components
    $pt3dOut = & $PythonExe -c "import pytorch3d; print('PT3D_OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and ($pt3dOut -match "PT3D_OK")) {
        $pytorch3dOK = $true
        Write-Log "Optional check: pytorch3d OK"
    } else {
        Write-Log "WARNING: pytorch3d not available. Some features may be limited."
    }
    
    $d2Out = & $PythonExe -c "import detectron2; print('D2_OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and ($d2Out -match "D2_OK")) {
        $detectron2OK = $true
        Write-Log "Optional check: detectron2 OK"
    } else {
        Write-Log "WARNING: detectron2 not available. Some features may be limited."
    }
    
    # Determine overall status
    if ($torchOK -and $hmr4dOK -and $pytorch3dOK -and $detectron2OK) {
        Write-Log "Verification passed - all components installed."
        Write-ProgressStatus "Installation complete!" 100
        Write-Log "=== Installation Finished ==="
        exit 0
    } elseif ($torchOK -and $hmr4dOK) {
        Write-Log "Core verification passed. Optional components missing."
        Write-ProgressStatus "Installation complete (partial)" 100
        Write-Log "=== Installation Finished (partial) ==="
        exit 0
    } else {
        Write-Log "ERROR: Core verification failed. torch=$torchOK, hmr4d=$hmr4dOK"
        Write-ProgressStatus "Installation verification failed" 95
        exit 1
    }
}
