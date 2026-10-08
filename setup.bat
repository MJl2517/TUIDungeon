@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"

where py >nul 2>nul
if not errorlevel 1 (
    set "SETUP_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.11+ was not found. Install Python with its launcher or add it to PATH. 1>&2
        goto failed
    )
    set "SETUP_PYTHON=python"
)
%SETUP_PYTHON% -X utf8 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo Python 3.11+ is required. 1>&2
    goto failed
)
where node >nul 2>nul
if errorlevel 1 goto missing_node
where npm >nul 2>nul
if errorlevel 1 goto missing_node
node -e "const [major, minor] = process.versions.node.split('.').map(Number); process.exit(major > 20 || major === 20 && minor >= 19 ? 0 : 1)"
if errorlevel 1 goto missing_node

if not exist ".venv\Scripts\python.exe" (
    %SETUP_PYTHON% -X utf8 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -X utf8 -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
call npm ci --prefix studio
if errorlevel 1 goto failed
call npm run build --prefix studio
if errorlevel 1 goto failed
echo Ready. Game: run.bat ^| Studio: run.bat --studio
popd
exit /b 0

:missing_node
echo Node.js 20.19+ and npm are required. Add them to PATH and run setup.bat again. 1>&2
:failed
popd
exit /b 1
