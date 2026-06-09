@echo off
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%..\.."
set "STEP=%~1"

REM Use app dir for logs so they persist after installer closes
set "LOGDIR=%APP_DIR%\installer\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\MocapOS_Step%STEP%.log"

echo === MocapOS Step %STEP% started at %date% %time% === > "%LOGFILE%"
echo Script dir: %SCRIPT_DIR% >> "%LOGFILE%"
echo App dir: %APP_DIR% >> "%LOGFILE%"
echo Current user: %USERNAME% >> "%LOGFILE%"
echo User profile: %USERPROFILE% >> "%LOGFILE%"

powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%install_dependencies.ps1" -InstallDir "%APP_DIR%" -Step %STEP% >> "%LOGFILE%" 2>&1
set EXITCODE=%ERRORLEVEL%

echo === Step %STEP% finished with exit code %EXITCODE% at %date% %time% === >> "%LOGFILE%"
exit /b %EXITCODE%
