@echo off
REM Build Lambda deployment package for GreenTrack backend (Windows)
REM Usage: scripts\build-lambda.bat

echo Building Lambda deployment package...

REM Navigate to repository root
cd /d %~dp0..

REM Configuration
set APP_DIR=app
set BUILD_DIR=build\lambda-package
set OUTPUT_ZIP=build\lambda.zip
set REQUIREMENTS_FILE=app\requirements.txt

REM Clean previous build
echo Cleaning previous build...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%OUTPUT_ZIP%" del /q "%OUTPUT_ZIP%"
mkdir "%BUILD_DIR%"

REM Install Python dependencies
echo Installing Python dependencies...
if exist "%REQUIREMENTS_FILE%" (
    pip install -r "%REQUIREMENTS_FILE%" -t "%BUILD_DIR%" --quiet
    echo    Dependencies installed
) else (
    echo    No requirements.txt found, skipping dependencies
)

REM Copy application code
echo Copying application code...
xcopy /E /I /Q "%APP_DIR%\backend" "%BUILD_DIR%\backend"
xcopy /E /I /Q "%APP_DIR%\adapters" "%BUILD_DIR%\adapters"
if exist "%APP_DIR%\__init__.py" (
    copy "%APP_DIR%\__init__.py" "%BUILD_DIR%\" >nul
) else (
    echo. > "%BUILD_DIR%\__init__.py"
)

REM Copy ML code (needed for forecasting)
if exist "ml" (
    echo Copying ML modules...
    mkdir "%BUILD_DIR%\ml"
    xcopy /E /I /Q "ml\forecasting" "%BUILD_DIR%\ml\forecasting"
    if exist "ml\__init__.py" (
        copy "ml\__init__.py" "%BUILD_DIR%\ml\" >nul
    ) else (
        echo. > "%BUILD_DIR%\ml\__init__.py"
    )
)

REM Remove unnecessary files
echo Removing unnecessary files...
for /d /r "%BUILD_DIR%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /d /r "%BUILD_DIR%" %%d in (*.dist-info) do @if exist "%%d" rd /s /q "%%d"
for /d /r "%BUILD_DIR%" %%d in (*.egg-info) do @if exist "%%d" rd /s /q "%%d"
del /s /q "%BUILD_DIR%\*.pyc" 2>nul
del /s /q "%BUILD_DIR%\*.pyo" 2>nul

REM Create ZIP file
echo Creating deployment package...
powershell -command "Compress-Archive -Path '%BUILD_DIR%\*' -DestinationPath '%OUTPUT_ZIP%' -Force"

echo.
echo Lambda package built successfully!
echo    Location: %OUTPUT_ZIP%
echo.
echo Next steps:
echo    1. Test locally: python -c "import app.backend.consumption"
echo    2. Deploy: terraform apply
echo.
