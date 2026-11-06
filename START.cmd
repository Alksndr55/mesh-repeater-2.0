@echo off
setlocal DisableDelayedExpansion
echo Mesh Repeater v2.10 - NexusBV 0.9
echo.
echo 1. POWER - NaIon_COLD
echo 2. POWER - LTO_2S
echo 3. LOGIC - NaIon_COLD
echo 4. LOGIC - LTO_2S
echo 5. SHIELD - NaIon_COLD
echo 6. SHIELD - LTO_2S
echo Q. Exit
choice /C 123456Q /N /M "Open boardview: "
if errorlevel 255 exit /b 1
if errorlevel 7 exit /b 0
if errorlevel 6 goto board6
if errorlevel 5 goto board5
if errorlevel 4 goto board4
if errorlevel 3 goto board3
if errorlevel 2 goto board2
if errorlevel 1 goto board1
exit /b 1
:board1
if not exist "%~dp0START_POWER_NaIon_COLD.cmd" goto missing
"%~dp0START_POWER_NaIon_COLD.cmd"
exit /b
:board2
if not exist "%~dp0START_POWER_LTO_2S.cmd" goto missing
"%~dp0START_POWER_LTO_2S.cmd"
exit /b
:board3
if not exist "%~dp0START_LOGIC_NaIon_COLD.cmd" goto missing
"%~dp0START_LOGIC_NaIon_COLD.cmd"
exit /b
:board4
if not exist "%~dp0START_LOGIC_LTO_2S.cmd" goto missing
"%~dp0START_LOGIC_LTO_2S.cmd"
exit /b
:board5
if not exist "%~dp0START_SHIELD_NaIon_COLD.cmd" goto missing
"%~dp0START_SHIELD_NaIon_COLD.cmd"
exit /b
:board6
if not exist "%~dp0START_SHIELD_LTO_2S.cmd" goto missing
"%~dp0START_SHIELD_LTO_2S.cmd"
exit /b
:missing
echo Extract the complete ZIP before starting.
pause
exit /b 1
