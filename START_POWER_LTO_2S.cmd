@echo off
setlocal DisableDelayedExpansion
if not exist "%~dp0third_party\NexusBV\0.9\NexusBV.exe" goto missing
if not exist "%~dp0v2\output\current\POWER\Mesh_Repeater_v2.10_POWER_LTO_2S.cad" goto missing
if not exist "%~dp0v2\output\current\POWER\POWER_schematic.pdf" goto missing
start "" /D "%~dp0third_party\NexusBV\0.9" "%~dp0third_party\NexusBV\0.9\NexusBV.exe" "%~dp0v2\output\current\POWER\Mesh_Repeater_v2.10_POWER_LTO_2S.cad" "%~dp0v2\output\current\POWER\POWER_schematic.pdf"
if errorlevel 1 goto failed
exit /b 0
:missing
echo Required files are missing. Extract the complete ZIP before starting.
pause
exit /b 1
:failed
echo NexusBV could not start.
pause
exit /b 1
