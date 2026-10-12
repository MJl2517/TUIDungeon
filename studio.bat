@echo off
setlocal
call "%~dp0run.bat" --studio %*
set "STUDIO_EXIT=%errorlevel%"
if not "%STUDIO_EXIT%"=="0" pause
exit /b %STUDIO_EXIT%
