# MocapOS Model Downloader (HuggingFace edition)
# Downloads all tracking checkpoints from Hugging Face (public, no auth, resumable).
# Body models (SMPL, SMPL-X) are NOT downloaded here - they require user registration
# at Max Planck Institute. The GUI's Body Models Importer handles those.

param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir,

    [Parameter(Mandatory=$false)]
    [string]$ProgressFile = ""
)

if ($ProgressFile -and ($ProgressFile -ne "")) {
    $ProgressFile = [System.IO.Path]::GetFullPath($ProgressFile)
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

function Write-Progress-Msg {
    param([string]$Message, [int]$Percent)
    if ($ProgressFile -and ($ProgressFile -ne "")) {
        "$Percent|$Message" | Out-File -FilePath $ProgressFile -Encoding UTF8
    }
}

function Ensure-Dir {
    param([string]$Path)
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

$DownloadLog = "$InstallDir\installer\download_log.txt"
Ensure-Dir "$InstallDir\installer"
"=== Model Download Log ===" | Out-File -FilePath $DownloadLog -Encoding UTF8

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $Message" | Out-File -FilePath $DownloadLog -Encoding UTF8 -Append
    Write-Host $Message
}

function Invoke-HFDownload {
    param(
        [string]$Url,
        [string]$Dest,
        [string]$Label
    )
    if (Test-Path $Dest) {
        Write-Log "[SKIP] $Label already exists at $Dest"
        return $true
    }
    Ensure-Dir (Split-Path $Dest -Parent)
    Write-Log "Downloading $Label ..."
    try {
        # curl is built-in on Windows 10+ and supports HTTP range/resume
        $exit = (Start-Process -FilePath "curl.exe" -ArgumentList @(
            "-L", "--fail", "--retry", "3", "--retry-delay", "5",
            "-C", "-",
            "-o", $Dest,
            $Url
        ) -NoNewWindow -Wait -PassThru).ExitCode
        if ($exit -eq 0 -and (Test-Path $Dest)) {
            Write-Log "[OK] $Label downloaded."
            return $true
        }
        Write-Log "[WARN] curl exited with code $exit for $Label"
    } catch {
        Write-Log "[WARN] Exception downloading $Label : $($_.Exception.Message)"
    }
    if (Test-Path $Dest) { Remove-Item $Dest -Force -ErrorAction SilentlyContinue }
    return $false
}

# ========== Tracking Models (HuggingFace) ==========
Write-Progress-Msg -Message "Downloading tracking models..." -Percent 5

$CkptDir   = "$InstallDir\inputs\checkpoints"
$HamerData = "$InstallDir\hamer_lib\_DATA"

$Downloads = @(
    @{ Url = "https://huggingface.co/camenduru/GVHMR/resolve/main/gvhmr/gvhmr_siga24_release.ckpt";
       Dest = "$CkptDir\gvhmr\gvhmr_siga24_release.ckpt"; Label = "GVHMR (164 MB)" }
    @{ Url = "https://huggingface.co/camenduru/GVHMR/resolve/main/hmr2/epoch%3D10-step%3D25000.ckpt";
       Dest = "$CkptDir\hmr2\epoch=10-step=25000.ckpt"; Label = "HMR2 (2.7 GB)" }
    @{ Url = "https://huggingface.co/camenduru/GVHMR/resolve/main/vitpose/vitpose-h-multi-coco.pth";
       Dest = "$CkptDir\vitpose\vitpose-h-multi-coco.pth"; Label = "ViTPose-H (2.5 GB)" }
    @{ Url = "https://huggingface.co/camenduru/GVHMR/resolve/main/dpvo/dpvo.pth";
       Dest = "$CkptDir\dpvo\dpvo.pth"; Label = "DPVO (14 MB)" }
    @{ Url = "https://huggingface.co/camenduru/GVHMR/resolve/main/yolo/yolov8x.pt";
       Dest = "$CkptDir\yolo\yolov8x.pt"; Label = "YOLOv8x (131 MB)" }
    @{ Url = "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/checkpoints/hamer.ckpt";
       Dest = "$HamerData\hamer_ckpts\checkpoints\hamer.ckpt"; Label = "HaMeR (2.7 GB)" }
    @{ Url = "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/vitpose_ckpts/vitpose%2B_huge/wholebody.pth";
       Dest = "$HamerData\vitpose_ckpts\vitpose+_huge\wholebody.pth"; Label = "ViTPose+ Huge wholebody (3.8 GB)" }
    @{ Url = "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/model_config.yaml";
       Dest = "$HamerData\hamer_ckpts\model_config.yaml"; Label = "HaMeR model_config.yaml" }
    @{ Url = "https://huggingface.co/spaces/geopavlakos/HaMeR/resolve/main/_DATA/hamer_ckpts/dataset_config.yaml";
       Dest = "$HamerData\hamer_ckpts\dataset_config.yaml"; Label = "HaMeR dataset_config.yaml" }
)

$Total = $Downloads.Count
for ($i = 0; $i -lt $Total; $i++) {
    $d = $Downloads[$i]
    $pct = [int](5 + ($i / $Total) * 85)
    Write-Progress-Msg -Message "($($i+1)/$Total) $($d.Label)" -Percent $pct
    Invoke-HFDownload -Url $d.Url -Dest $d.Dest -Label $d.Label | Out-Null
}

# ========== Final Status ==========
Write-Progress-Msg -Message "Verifying checkpoints..." -Percent 92

$Missing = @()
$Checks = @(
    @{ Path = "$CkptDir\gvhmr\gvhmr_siga24_release.ckpt"; Name = "GVHMR" }
    @{ Path = "$CkptDir\hmr2\epoch=10-step=25000.ckpt"; Name = "HMR2" }
    @{ Path = "$CkptDir\vitpose\vitpose-h-multi-coco.pth"; Name = "ViTPose" }
    @{ Path = "$CkptDir\yolo\yolov8x.pt"; Name = "YOLOv8x" }
    @{ Path = "$CkptDir\dpvo\dpvo.pth"; Name = "DPVO" }
    @{ Path = "$HamerData\hamer_ckpts\checkpoints\hamer.ckpt"; Name = "HaMeR" }
    @{ Path = "$HamerData\vitpose_ckpts\vitpose+_huge\wholebody.pth"; Name = "ViTPose+ wholebody" }
)
foreach ($check in $Checks) {
    if (-not (Test-Path $check.Path)) {
        $Missing += $check.Name
        Write-Log "MISSING: $($check.Name)"
    } else {
        Write-Log "FOUND:   $($check.Name)"
    }
}

# Body models are user-supplied; just note their absence
$BodyMissing = @()
if (-not (Test-Path "$CkptDir\body_models\smplx\SMPLX_NEUTRAL.npz")) { $BodyMissing += "SMPL-X" }
if (-not (Test-Path "$CkptDir\body_models\smpl\SMPL_NEUTRAL.pkl"))   { $BodyMissing += "SMPL" }

if ($Missing.Count -gt 0 -or $BodyMissing.Count -gt 0) {
    $Instructions = "$InstallDir\MODEL_DOWNLOAD_INSTRUCTIONS.txt"
    @"
================================================================================
  MocapOS - Models Status
================================================================================

"@ | Out-File -FilePath $Instructions -Encoding UTF8

    if ($Missing.Count -gt 0) {
        @"
Tracking models that failed to download (retry installer or check internet):
$($Missing | ForEach-Object { "  - $_" } | Out-String)

"@ | Out-File -FilePath $Instructions -Encoding UTF8 -Append
    }

    if ($BodyMissing.Count -gt 0) {
        @"
Body models (require registration - use the GUI's Body Models Importer):
$($BodyMissing | ForEach-Object { "  - $_" } | Out-String)

After install:
  1. Open MocapOS (run_gui.bat)
  2. Go to Settings > Body Models
  3. Follow the step-by-step instructions and drag the downloaded zip(s)

Or manually:

SMPL-X: https://smpl-x.is.tue.mpg.de/
  Click "Download SMPL-X v1.1 (NPZ+PKL, 830 MB) - Use this for SMPL-X Python codebase"
  Extract SMPLX_*.npz to: inputs/checkpoints/body_models/smplx/

SMPL: https://smpl.is.tue.mpg.de/
  Click "Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)"
  Extract basicmodel_*.pkl, RENAME to SMPL_NEUTRAL/MALE/FEMALE.pkl
  Place in: inputs/checkpoints/body_models/smpl/
"@ | Out-File -FilePath $Instructions -Encoding UTF8 -Append
    }
    Write-Log "Status written to: $Instructions"
    Write-Progress-Msg -Message "Done. Body models still needed - see GUI." -Percent 95
} else {
    Write-Progress-Msg -Message "All models present!" -Percent 100
}

Write-Log "=== Model Download Finished ==="
