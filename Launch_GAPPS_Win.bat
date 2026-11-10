@echo off
rem GAPPS launcher (Windows)
rem Uses the virtual environment .venv of the GAPPS folder (pip installation) if it exists,
rem otherwise the conda environment "gapps" (installation with environment.yml).
setlocal EnableExtensions
set "ENV_NAME=gapps"
set "GAPPS_DIR=%~dp0"

rem 1) pip installation: .venv inside the GAPPS folder
if exist "%GAPPS_DIR%.venv\Scripts\python.exe" (
    "%GAPPS_DIR%.venv\Scripts\python.exe" "%GAPPS_DIR%run_gapps.py"
    goto end
)

rem 2) conda installation in a usual location: activate the environment (GDAL/PROJ need it)
for %%B in ("%USERPROFILE%\miniforge3" "%USERPROFILE%\mambaforge" "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniforge3" "%LOCALAPPDATA%\mambaforge" "%LOCALAPPDATA%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%ProgramData%\miniforge3" "%ProgramData%\mambaforge" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3") do (
    if exist "%%~B\envs\%ENV_NAME%\python.exe" if exist "%%~B\Scripts\activate.bat" (
        call "%%~B\Scripts\activate.bat" "%%~B\envs\%ENV_NAME%"
        python "%GAPPS_DIR%run_gapps.py"
        goto end
    )
)

rem 3) conda elsewhere (conda on the PATH, e.g. from a conda prompt)
if defined CONDA_EXE (
    "%CONDA_EXE%" run --no-capture-output -n %ENV_NAME% python "%GAPPS_DIR%run_gapps.py"
    goto end
)
where conda >nul 2>nul
if not errorlevel 1 (
    call conda run --no-capture-output -n %ENV_NAME% python "%GAPPS_DIR%run_gapps.py"
    goto end
)

echo GAPPS: no Python environment found.
echo Expected: .venv in the GAPPS folder (pip installation) or the conda environment "%ENV_NAME%"
echo (conda env create -f environment.yml). See README.md, "Installation of GAPPS".
pause
exit /b 1

:end
if errorlevel 1 pause
