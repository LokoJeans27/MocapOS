@echo off
setlocal EnableDelayedExpansion
title MocapOS - Uninstall / Clean up
color 0E

:: App folder = where this script lives (strip trailing backslash)
set "APP=%~dp0"
set "APP=%APP:~0,-1%"

echo ============================================================
echo   MocapOS - Uninstall / Clean up
echo ============================================================
echo.
echo   Folder: %APP%
echo.
echo   MocapOS is portable - it installs NOTHING in Windows. Everything
echo   it downloaded lives inside the folder above, so removing it just
echo   means deleting these. Your original input videos are NOT touched.
echo.
echo   What do you want to do?
echo.
echo     [1]  Free up space  ^(~13 GB^)
echo          Delete the portable environment + the downloaded archive
echo          + outputs. KEEPS your code and all models ^(incl. licensed
echo          SMPL / SMPL-X / MANO^). Re-run setup.bat later to use again.
echo.
echo     [2]  Full uninstall
echo          Delete the ENTIRE MocapOS folder and the Desktop shortcut.
echo          Removes everything, including the models you downloaded.
echo.
echo     [0]  Cancel
echo.
set "CH="
set /p "CH=Choose 1, 2 or 0: "

if "!CH!"=="1" goto freespace
if "!CH!"=="2" goto full
echo.
echo Cancelled. Nothing was deleted.
pause
exit /b 0

:freespace
echo.
echo Removing portable environment, downloaded archive and outputs...
if exist "%APP%\env"     rmdir /s /q "%APP%\env"
if exist "%APP%\envs"    rmdir /s /q "%APP%\envs"
if exist "%APP%\outputs" rmdir /s /q "%APP%\outputs"
echo.
echo Done. Freed up space. Your code and models are still here.
echo Run setup.bat again whenever you want to use MocapOS.
echo.
pause
exit /b 0

:full
echo.
echo   WARNING: this deletes the WHOLE folder, including any SMPL / SMPL-X /
echo            MANO models you downloaded. This cannot be undone.
echo.
set "CONF="
set /p "CONF=Type  YES  to fully uninstall (anything else cancels): "
if /I not "!CONF!"=="YES" (
    echo Cancelled. Nothing was deleted.
    pause
    exit /b 0
)
echo.
echo Removing Desktop shortcut...
del "%USERPROFILE%\Desktop\MocapOS.lnk" 2>nul
del "%APP%\MocapOS.lnk" 2>nul
echo Removing all MocapOS files ^(close MocapOS first if it is open^)...
:: Delete every sub-folder inside the app...
for /d %%D in ("%APP%\*") do rmdir /s /q "%%D"
:: ...and every file inside it EXCEPT this uninstaller itself.
for %%F in ("%APP%\*") do if /I not "%%~nxF"=="uninstall.bat" del /q "%%F"
echo.
echo ============================================================
echo   Done. Everything was removed.
echo   This folder is now empty - just delete it yourself:
echo   send  "%APP%"  to the Recycle Bin.
echo ============================================================
echo.
pause
exit /b 0
