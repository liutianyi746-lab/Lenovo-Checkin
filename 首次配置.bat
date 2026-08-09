@echo off
chcp 65001 >nul
pushd "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python setup_config.py
) else (
    py -3 setup_config.py
)
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" pause
popd
exit /b %exit_code%
