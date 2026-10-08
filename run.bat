@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"

if exist ".venv\Scripts\python.exe" goto venv
where py >nul 2>nul
if not errorlevel 1 goto launcher
where python >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.11+ was not found. Install Python and run setup.bat. 1>&2
set "RUN_EXIT=1"
goto finish

:venv
".venv\Scripts\python.exe" -X utf8 -m tuidungeon %*
goto result

:launcher
py -3 -X utf8 -m tuidungeon %*
goto result

:python
python -X utf8 -m tuidungeon %*

:result
set "RUN_EXIT=%errorlevel%"
:finish
popd
exit /b %RUN_EXIT%
