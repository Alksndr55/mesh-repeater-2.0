@echo off
setlocal DisableDelayedExpansion
echo Mesh Repeater v2.11 - NaIon_COLD
echo.
echo 1. POWER
echo 2. LOGIC
echo 3. SHIELD
echo Q. Exit
choice /C 123Q /N /M "Open boardview: "
if errorlevel 255 exit /b 1
if errorlevel 4 exit /b 0
if errorlevel 3 goto board3
if errorlevel 2 goto board2
if errorlevel 1 goto board1
exit /b 1
:board1
if not exist "%~dp0third_party\NexusBV\0.9\NexusBV.exe" goto missing
if not exist "%~dp0v2\output\current\POWER\Mesh_Repeater_v2.11_POWER_NaIon_COLD.cad" goto missing
if not exist "%~dp0v2\output\current\POWER\POWER_schematic.pdf" goto missing
start "" /D "%~dp0third_party\NexusBV\0.9" "%~dp0third_party\NexusBV\0.9\NexusBV.exe" "%~dp0v2\output\current\POWER\Mesh_Repeater_v2.11_POWER_NaIon_COLD.cad" "%~dp0v2\output\current\POWER\POWER_schematic.pdf"
if errorlevel 1 goto failed
exit /b 0
:board2
if not exist "%~dp0third_party\NexusBV\0.9\NexusBV.exe" goto missing
if not exist "%~dp0v2\output\current\LOGIC\Mesh_Repeater_v2.11_LOGIC_NaIon_COLD.cad" goto missing
if not exist "%~dp0v2\output\current\LOGIC\LOGIC_schematic.pdf" goto missing
start "" /D "%~dp0third_party\NexusBV\0.9" "%~dp0third_party\NexusBV\0.9\NexusBV.exe" "%~dp0v2\output\current\LOGIC\Mesh_Repeater_v2.11_LOGIC_NaIon_COLD.cad" "%~dp0v2\output\current\LOGIC\LOGIC_schematic.pdf"
if errorlevel 1 goto failed
exit /b 0
:board3
if not exist "%~dp0third_party\NexusBV\0.9\NexusBV.exe" goto missing
if not exist "%~dp0v2\output\current\SHIELD\Mesh_Repeater_v2.11_SHIELD_NaIon_COLD.cad" goto missing
start "" /D "%~dp0third_party\NexusBV\0.9" "%~dp0third_party\NexusBV\0.9\NexusBV.exe" "%~dp0v2\output\current\SHIELD\Mesh_Repeater_v2.11_SHIELD_NaIon_COLD.cad"
if errorlevel 1 goto failed
exit /b 0
:missing
echo Extract the complete ZIP before starting.
pause
exit /b 1
:failed
echo NexusBV could not start.
pause
exit /b 1
