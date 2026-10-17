@echo off
chcp 65001 >nul
setlocal
set "CHECKIN_LOG=%~dp0checkin.log"
echo [%date% %time%] START >> "%CHECKIN_LOG%"
node "%~dp0checkin.mjs" >> "%CHECKIN_LOG%" 2>&1
set "CHECKIN_RESULT=%ERRORLEVEL%"
echo [%date% %time%] EXIT_CODE=%CHECKIN_RESULT% >> "%CHECKIN_LOG%"
exit /b %CHECKIN_RESULT%
