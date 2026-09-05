@echo off
REM Starts rover_bridge/server.py on the Pi (must already be deployed there).
REM Safe to re-run: it checks for an already-running instance first.
REM
REM Note: the SSH call that launches the server can report a timeout/nonzero
REM exit even when the server started fine -- that's the SSH session hanging
REM on the backgrounded remote process, not a real failure. This script
REM always re-checks and prints the real status at the end.

set PI_HOST=nithin@10.7.20.227

echo Checking for an existing server on the Pi...
ssh -o ConnectTimeout=5 %PI_HOST% "pgrep -af server.py" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Server is already running.
    goto :status
)

echo Starting rover_bridge/server.py on the Pi...
ssh %PI_HOST% "cd ~/rover_bridge && nohup python3 server.py > ~/rover_bridge/server.log 2>&1 </dev/null &"

timeout /t 2 /nobreak >nul

:status
echo.
echo Current status:
ssh -o ConnectTimeout=5 %PI_HOST% "pgrep -af server.py; echo ---; tail -n 6 ~/rover_bridge/server.log"
echo.
echo Control page: http://10.7.20.227:5000/
pause
