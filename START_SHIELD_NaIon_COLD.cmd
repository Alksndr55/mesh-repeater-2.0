@echo off
setlocal DisableDelayedExpansion
if not exist "%~dp0third_party\NexusBV\0.9\NexusBV.exe" goto missing
if not exist "%~dp0v2\output\current\SHIELD\Mesh_Repeater_v2.10_SHIELD_NaIon_COLD.cad" goto missing
start "" /D "%~dp0third_party\NexusBV\0.9" "%~dp0third_party\NexusBV\0.9\NexusBV.exe" "%~dp0v2\output\current\SHIELD\Mesh_Repeater_v2.10_SHIELD_NaIon_COLD.cad"
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
