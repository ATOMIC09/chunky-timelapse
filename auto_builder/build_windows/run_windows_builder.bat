@echo off
setlocal EnableDelayedExpansion

REM Check if PyInstaller is installed (always needed for the build process)
echo Checking for PyInstaller installation...
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller is not installed. Installing now...
    pip install pyinstaller
) else (
    echo PyInstaller is already installed.
)

REM Process requirements.txt and check for all required packages
echo Checking packages from requirements.txt...
for /f "tokens=1 delims=>=" %%a in ('type ..\..\requirements.txt ^| findstr /v "#" ^| findstr /v "^$"') do (
    set pkg=%%a
    set pkg=!pkg: =!
    if not "!pkg!"=="" (
        echo Checking for !pkg! installation...
        python -c "import !pkg:.=!" 2>nul
        if !errorlevel! neq 0 (
            echo !pkg! is not installed. Installing now...
            pip install !pkg!
        ) else (
            echo !pkg! is already installed.
        )
    )
)
echo.

REM Step 1: Run PyInstaller to build main.exe
echo 1. Running PyInstaller to build main.exe...
python -m PyInstaller --noconsole --onefile --windowed --icon="..\asset\windows-logo.ico" --name="ChunkyTimelapse" ^
--add-data="..\asset\windows-logo.ico;." ^
--hidden-import=cv2 --hidden-import=PyQt6 --hidden-import=mcworldlib ^
--version-file=version_info.txt ^
..\..\main.py

if %errorlevel% neq 0 (
    echo ! PyInstaller failed to build the application.
    exit /b 1
)
echo / PyInstaller build complete.
echo.

REM Step 2: Move the built executable to the desired location
echo 2. Moving the built executable to the desired location...
move dist\ChunkyTimelapse.exe .\ChunkyTimelapse.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo ! Failed to move the executable.
    exit /b 1
)
echo / Executable moved.
echo.

REM Step 3: Clean up built artifacts
set /p cleanup="3. Do you want to remove the build directories (dist, build, __pycache__, ChunkyTimelapse.spec)? (y/n): "
if /i "%cleanup%"=="y" (
    rmdir /s /q dist
    rmdir /s /q build
    rmdir /s /q __pycache__
    del /q ChunkyTimelapse.spec
    echo / Cleanup complete.
) else if /i "%cleanup%"=="yes" (
    rmdir /s /q dist
    rmdir /s /q build
    rmdir /s /q __pycache__
    del /q ChunkyTimelapse.spec
    echo / Cleanup complete.
) else if /i "%cleanup%"=="Y" (
    rmdir /s /q dist
    rmdir /s /q build
    rmdir /s /q __pycache__
    del /q ChunkyTimelapse.spec
    echo / Cleanup complete.
) else (
    echo - Skipping cleanup.
)
echo.

REM Step 4: Echo run complete
echo / Run complete.
echo.
pause
