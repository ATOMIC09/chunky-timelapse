#!/bin/bash

# Check if npm is installed
if ! command -v npm &> /dev/null; then
  echo "⚠️  npm is not installed. Please install Node.js"
  exit 1
fi
# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
  echo "⚠️  Python 3 is not installed. Please install Python 3"
  exit 1
fi

# Function to install appdmg if not installed
install_appdmg() {
  if ! command -v appdmg &> /dev/null; then
    echo "⬇️  appdmg is not installed. Installing..."
    npm install -g appdmg
    if [ $? -ne 0 ]; then
      echo "⚠️  Failed to install appdmg."
      exit 1
    fi
    echo "✅ appdmg installed successfully."
  else
    echo "✅ appdmg is already installed."
  fi
}

# Function to install pyinstaller if not installed
install_pyinstaller() {
  if ! command -v pyinstaller &> /dev/null; then
    echo "⬇️  PyInstaller is not installed. Installing..."
    python3 -m pip install pyinstaller
    if [ $? -ne 0 ]; then
      echo "⚠️  Failed to install PyInstaller."
      exit 1
    fi
    echo "✅ PyInstaller installed successfully."
  else
    echo "✅ PyInstaller is already installed."
  fi
}

# Function to install Python packages from requirements.txt
install_requirements() {
  echo "⬇️  Installing Python packages from requirements.txt..."
  python3 -m pip install -r ../../requirements.txt
  if [ $? -ne 0 ]; then
    echo "⚠️  Failed to install some Python packages from requirements.txt."
    exit 1
  fi
  echo "✅ All packages from requirements.txt installed successfully."
}

# Function to check if a Python package is installed and display its location
check_python_package() {
  if ! python3 -m pip show "$1" &> /dev/null; then
    echo "⚠️  Package $1 is not installed."
    return 1
  else
    location=$(python3 -m pip show "$1" | grep Location | cut -d ' ' -f 2)
    echo "✅ $1 is installed at: $location"
    return 0
  fi
}

# Function to check if a command exists and display its path
check_command() {
  if ! command -v "$1" &> /dev/null; then
    echo "⚠️  Error: $1 is not installed."
    if [ "$1" == "appdmg" ]; then
      install_appdmg
    elif [ "$1" == "pyinstaller" ]; then
      install_pyinstaller
    fi
  else
    location=$(command -v "$1")
    echo "✅ $1 is installed at: $location"
  fi
}

# Step 0: Check for dependencies
echo
echo "0️⃣  Checking for required dependencies..."
check_command appdmg
check_command pyinstaller

# Check Python packages from requirements.txt
echo
echo "0️⃣  Checking Python packages from requirements.txt..."
missing_packages=false
while IFS= read -r package_line || [[ -n "$package_line" ]]; do
  # Extract the package name (before any version specifiers)
  package_name=$(echo "$package_line" | cut -d'>' -f1 | cut -d'=' -f1 | cut -d'<' -f1 | tr -d ' ')
  if [ -n "$package_name" ]; then
    if ! check_python_package "$package_name"; then
      missing_packages=true
    fi
  fi
done < ../../requirements.txt

# Install missing packages if any
if [ "$missing_packages" = true ]; then
  echo "Missing Python packages found, installing from requirements.txt..."
  install_requirements
fi

# Step 1: Run pyinstaller to build main.app
echo
echo "1️⃣  Running pyinstaller to build main.app..."
pyinstaller --onefile --noconsole --icon=../asset/mac-logo.icns ../../main.py
if [ $? -ne 0 ]; then
  echo "⚠️  PyInstaller failed to build the application."
  exit 1
fi
echo "✅ PyInstaller build complete."
echo

# Step 2: Copy "dist/main.app" to "Chunky Timelapse.app"
if [ -d "dist/main.app" ]; then
  echo "2️⃣  Copying dist/main.app to Chunky Timelapse.app..."
  cp -r "dist/main.app" "Chunky Timelapse.app"
  echo "✅ Copy complete: dist/main.app to Chunky Timelapse.app"
else
  echo "⚠️  dist/main.app not found! The build may have failed."
  exit 1
fi

# Step 3: Run appdmg to create the DMG file
echo
echo "3️⃣  Running appdmg to create ChunkyTimelapse.dmg..."
appdmg ChunkyTimelapse.json ChunkyTimelapse.dmg
if [ $? -ne 0 ]; then
  echo "⚠️  appdmg command failed."
  exit 1
fi
echo
echo "✅ appdmg command executed successfully."
echo

# Step 4: Clean up built artifacts
read -p "4️⃣  Do you want to remove the build and dist directories? (y/n): " cleanup
if [ "$cleanup" == "y" ] || [ "$cleanup" == "Y" ]; then
  rm -rf build dist
  echo "✅ Cleanup complete."
else
  echo "⏭️  Skipping cleanup."
fi
echo

read -p "5️⃣  Do you want to remove the application files? (y/n): " cleanup
if [ "$cleanup" == "y" ] || [ "$cleanup" == "Y" ]; then
  rm -rf "Chunky Timelapse.app"
  rm main.spec
  echo "✅ Cleanup complete."
else
  echo "⏭️  Skipping cleanup."
fi
echo

# Step 5: Echo run complete
echo "✅ Run complete."
echo
