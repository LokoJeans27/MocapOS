@echo off
setlocal EnableDelayedExpansion
title MocapOS - Setup (portable)
color 0A

echo ============================================================
echo   MocapOS - Full Body + Hands Motion Capture
echo   Portable Setup (no compiling, no Build Tools)
echo ============================================================
echo.

:: App folder = where this script lives (strip trailing backslash)
set "APP=%~dp0"
set "APP=%APP:~0,-1%"
set "ENV=%APP%\env"

:: Hugging Face repo that hosts the two portable env tarballs (env_cu124 / env_cu128).
:: Public repo = free + unlimited bandwidth. Change this if you fork the project.
set "HF_REPO=LokoJeans/mocapos-envs"

:: ---------- 1. Detect GPU and choose env variant ----------
echo [1/6] Detecting NVIDIA GPU...
set "GPUNAME="
for /f "skip=1 tokens=*" %%g in ('nvidia-smi --query-gpu^=name --format^=csv 2^>nul') do (
    if not defined GPUNAME set "GPUNAME=%%g"
)
if not defined GPUNAME (
    echo   [ERROR] No NVIDIA GPU detected ^(nvidia-smi missing^).
    echo           Install the latest driver: https://www.nvidia.com/drivers
    echo           A NVIDIA GPU with driver ^>= 525 is required.
    pause
    exit /b 1
)
echo   GPU: !GPUNAME!

:: RTX 50xx (Blackwell) needs CUDA 12.8; everything older uses the cu124 build.
set "VARIANT=cu124"
echo !GPUNAME! | findstr /I /R /C:"RTX 50[0-9][0-9]" >nul && set "VARIANT=cu128"
echo   Selected environment: !VARIANT!
echo.

:: ---------- 2. Locate (or download) the env archive ----------
echo [2/6] Locating environment package...
set "ARC="
for %%P in (
    "%APP%\..\envs\env_!VARIANT!.tar.gz"
    "%APP%\envs\env_!VARIANT!.tar.gz"
    "%APP%\env_!VARIANT!.tar.gz"
) do (
    if not defined ARC if exist "%%~fP" set "ARC=%%~fP"
)
if not defined ARC if exist "%ENV%\python.exe" (
    :: Env already extracted from a previous run; archive no longer needed.
    set "ARC=ALREADY_INSTALLED"
)
if not defined ARC (
    echo   Not bundled locally - downloading from Hugging Face ^(one-time, ~5 GB^)...
    set "DLDIR=%APP%\envs"
    if not exist "!DLDIR!" mkdir "!DLDIR!"
    set "ARC=!DLDIR!\env_!VARIANT!.tar.gz"
    set "HFURL=https://huggingface.co/%HF_REPO%/resolve/main/env_!VARIANT!.tar.gz?download=true"
    echo   URL: !HFURL!
    :: -L follow redirects, -C - resume a partial download, --fail on HTTP errors.
    curl.exe -L -C - --fail --retry 3 --retry-delay 5 -o "!ARC!" "!HFURL!"
    if errorlevel 1 (
        echo   [ERROR] Could not download the environment from Hugging Face.
        echo           Check your internet connection and that the repo is public:
        echo           https://huggingface.co/%HF_REPO%
        pause
        exit /b 1
    )
)
echo   Using: !ARC!
echo.

:: ---------- 3. Extract environment ----------
echo [3/6] Installing environment...
if exist "%ENV%\python.exe" (
    echo   Environment already present at %ENV% ^(skipping extraction^).
) else (
    if not exist "%ENV%" mkdir "%ENV%"
    echo   Extracting ^(several minutes, ~8 GB^)...
    :: Use the Windows-bundled bsdtar explicitly. Calling bare "tar" can pick up
    :: a Git/MSYS tar earlier in PATH, which treats "C:\..." as a remote host
    :: and fails with "Cannot connect to C: resolve failed".
    set "WINTAR=%SystemRoot%\System32\tar.exe"
    if not exist "!WINTAR!" set "WINTAR=tar"
    "!WINTAR!" -xf "!ARC!" -C "%ENV%"
    if errorlevel 1 (
        echo   [ERROR] Extraction failed. Disk full or archive corrupt?
        pause
        exit /b 1
    )
)
if not exist "%ENV%\python.exe" (
    echo   [ERROR] python.exe not found after extraction. Archive may be invalid.
    pause
    exit /b 1
)

:: NOTE: we deliberately do NOT run conda-unpack. MocapOS invokes env\python.exe
:: directly (never `conda activate`), so the build-time prefixes baked into
:: Scripts shebangs are irrelevant. conda-unpack's text rewriting also corrupts
:: backslash escapes in some files (e.g. huggingface_hub uses "\\?\"), breaking
:: imports. Skipping it keeps every file byte-identical to the verified build.
echo   Linking app source packages...
"%ENV%\python.exe" "%APP%\tools\dev\fix_env_paths.py"
echo.

:: ---------- 4. Download + verify tracking models ----------
echo [4/6] Downloading and verifying AI models...
echo   ^(Public models from HuggingFace, ~12 GB on first run, resumable, hash-checked^)
"%ENV%\python.exe" "%APP%\tools\dev\fetch_models.py"
if errorlevel 1 (
    echo   [WARN] Some tracking models are missing/invalid. You can re-run setup.bat.
)
echo.

:: ---------- 5. Licensed models notice (SMPL / SMPL-X body + MANO hands) ----------
echo [5/6] Checking licensed models ^(SMPL / SMPL-X body, MANO hands^)...
set "BODYMISSING=0"
if not exist "%APP%\inputs\checkpoints\body_models\smplx\SMPLX_NEUTRAL.npz" set "BODYMISSING=1"
if not exist "%APP%\inputs\checkpoints\body_models\smpl\SMPL_NEUTRAL.pkl" set "BODYMISSING=1"
set "MANOMISSING=0"
if not exist "%APP%\hamer_lib\_DATA\data\mano\MANO_RIGHT.pkl" set "MANOMISSING=1"
if "!BODYMISSING!"=="1" (
    echo   SMPL / SMPL-X ^(body^) NOT included ^(Max Planck license - download once^).
    echo   After MocapOS opens: Settings ^> Body Models, and follow the importer.
    echo     SMPL-X: https://smpl-x.is.tue.mpg.de/   ^(NPZ+PKL 830 MB^)
    echo     SMPL:   https://smpl.is.tue.mpg.de/      ^(v1.1.0, 247 MB^)
) else (
    echo   Body models present.
)
if "!MANOMISSING!"=="1" (
    echo   MANO ^(hands^) not found - trying to auto-install from a downloaded mano_v1_2.zip...
    "%ENV%\python.exe" "%APP%\tools\dev\install_mano.py"
)
if not exist "%APP%\hamer_lib\_DATA\data\mano\MANO_RIGHT.pkl" (
    echo   MANO ^(hands^) NOT installed ^(Max Planck license - download once^).
    echo     1^) Register + download "Models ^& Code" ^(mano_v1_2.zip^): https://mano.is.tue.mpg.de/
    echo     2^) Re-run setup.bat ^(auto-installs from your Downloads^/Desktop^), or run:
    echo          env\python.exe tools\dev\install_mano.py ^<path-to-mano_v1_2.zip^>
    echo   ^(Without MANO the body still works; only hand capture is skipped.^)
) else (
    echo   MANO hand models present.
)
echo.

:: ---------- 6. Shortcut + self-test ----------
echo [6/6] Creating shortcut and verifying install...
set "VBS_PATH=%APP%\MocapOS.vbs"
set "ICON_PATH=%APP%\assets\icon.ico"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$desktop = [Environment]::GetFolderPath('Desktop');" ^
    "$targets = @(\"$desktop\MocapOS.lnk\", '%APP%\MocapOS.lnk');" ^
    "foreach ($t in $targets) {" ^
    "  $sc = $ws.CreateShortcut($t);" ^
    "  $sc.TargetPath = 'wscript.exe';" ^
    "  $sc.Arguments = '\"%VBS_PATH%\"';" ^
    "  if (Test-Path '%ICON_PATH%') { $sc.IconLocation = '%ICON_PATH%' };" ^
    "  $sc.WorkingDirectory = '%APP%';" ^
    "  $sc.Description = 'MocapOS - Full Body + Hands Motion Capture';" ^
    "  $sc.Save();" ^
    "}" 2>nul
echo   Shortcut created (Desktop + app folder).
echo.
echo   Running self-test...
"%ENV%\python.exe" "%APP%\tools\dev\selftest.py"
set "STRC=!errorlevel!"
echo.

echo ============================================================
if "!STRC!"=="0" (
    echo   Setup complete - MocapOS is READY.
) else (
    echo   Setup finished with warnings ^(see self-test above^).
    if "!BODYMISSING!"=="1" echo   Most likely just missing SMPL/SMPL-X body models.
)
echo.
echo   Launch MocapOS with the "MocapOS" icon on your Desktop.
echo ============================================================
pause
exit /b 0
