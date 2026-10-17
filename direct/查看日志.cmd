@echo off
if not exist "%~dp0checkin.log" (
  echo No scheduled check-in log yet.
  pause
  exit /b 1
)
start "" notepad.exe "%~dp0checkin.log"
