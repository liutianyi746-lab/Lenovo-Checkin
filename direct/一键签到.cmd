@echo off
chcp 65001 >nul
node "%~dp0checkin.mjs"
set "CHECKIN_RESULT=%ERRORLEVEL%"
pause
exit /b %CHECKIN_RESULT%
