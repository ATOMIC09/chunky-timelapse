@echo off
setlocal EnableDelayedExpansion

REM Check if Nuitka is installed (always needed for the build process)
echo Checking for Nuitka installation...
python -c "import nuitka" 2>nul
if %errorlevel% neq 0 (
    echo Nuitka is not installed. Installing now...
    pip install nuitka
) else (
    echo Nuitka is already installed.
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

REM Step 1: Run nuitka to build main.exe
echo 1. Running nuitka to build main.exe...
python -m nuitka --standalone ..\..\main.py --onefile --enable-plugin=pyqt6 --include-package=cv2 --windows-icon-from-ico="..\asset\windows-logo.ico" --windows-console-mode=disable --company-name="ATOMIC09" --product-name="Chunky Timelapse" --file-version=1.0 --product-version=1.0 --file-description="Minecraft world timelapse generator using Chunky" --copyright="Licensed under the GPLv3 License"
if %errorlevel% neq 0 (
    echo ! Nuitka failed to build the application.
    exit /b 1
)
echo / Nuitka build complete.
echo.

REM Step 2: Rename main.exe to ChunkyTimelapse.exe
echo 2. Renaming main.exe to ChunkyTimelapse.exe...
ren main.exe ChunkyTimelapse.exe
echo / Renaming complete.
echo.

REM Step 3: Clean up built artifacts
set /p cleanup="3. Do you want to remove the build directories (main.build, main.dist, main.onefile-build)? (y/n): "
if /i "%cleanup%"=="y" (
    rmdir /s /q main.build
    rmdir /s /q main.dist
    rmdir /s /q main.onefile-build
    echo / Cleanup complete.
) else if /i "%cleanup%"=="yes" (
    rmdir /s /q main.build
    rmdir /s /q main.dist
    rmdir /s /q main.onefile-build
    echo / Cleanup complete.
) else if /i "%cleanup%"=="Y" (
    rmdir /s /q main.build
    rmdir /s /q main.dist
    rmdir /s /q main.onefile-build
    echo / Cleanup complete.
) else (
    echo - Skipping cleanup.
)
echo.

REM Step 4: Echo run complete
echo / Run complete.
echo.
pause
