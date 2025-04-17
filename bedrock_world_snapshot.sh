#!/bin/bash

# Script to convert Minecraft Bedrock worlds to Java format
# Using chunker-cli-1.7.0.jar

# Set default values for all parameters
JAR_FILE="chunker-cli-1.7.0.jar"
INPUT_DIR="./worlds/"
OUTPUT_DIR="./world_java/"
FORMAT="JAVA_1_21_5"
WORLD_NAME=""
TEMP_DIR="./temp_world"

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -j JAR_FILE    Path to the chunker-cli JAR file (default: $JAR_FILE)"
    echo "  -i INPUT_DIR   Input directory containing Bedrock worlds (default: $INPUT_DIR)"
    echo "  -o OUTPUT_DIR  Output directory for Java worlds (default: $OUTPUT_DIR)"
    echo "  -f FORMAT      Target Java format (default: $FORMAT)"
    echo "  -w WORLD_NAME  Specific world folder name inside INPUT_DIR (default: first found)"
    echo "  -h             Show this help"
    exit 0
}

# Process command line arguments
while getopts "j:i:o:f:w:h" opt; do
  case $opt in
    j) JAR_FILE="$OPTARG" ;;
    i) INPUT_DIR="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    f) FORMAT="$OPTARG" ;;
    w) WORLD_NAME="$OPTARG" ;;
    h) show_help ;;
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done

# Remove trailing slash if present
INPUT_DIR=${INPUT_DIR%/}
OUTPUT_DIR=${OUTPUT_DIR%/}

# Display configuration
echo "Configuration:"
echo "  JAR File:      $JAR_FILE"
echo "  Input Dir:     $INPUT_DIR"
echo "  Output Dir:    $OUTPUT_DIR" 
echo "  Format:        $FORMAT"
if [ -n "$WORLD_NAME" ]; then
    echo "  World Name:    $WORLD_NAME"
fi

# Check if the chunker-cli JAR exists
if [ ! -f "$JAR_FILE" ]; then
    echo "Error: $JAR_FILE not found!"
    echo "Please download it from https://github.com/chunky-dev/chunker/releases"
    echo "Or specify a different path using the -j option"
    exit 1
fi

# Check if input directory exists
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: $INPUT_DIR directory not found!"
    echo "Please create this directory and place Bedrock worlds inside it"
    echo "Or specify a different directory using the -i option"
    exit 1
fi

# Find world folder if not specified
if [ -z "$WORLD_NAME" ]; then
    # Look for a directory inside INPUT_DIR that contains level.dat
    for dir in "$INPUT_DIR"/*/; do
        if [ -f "${dir}level.dat" ]; then
            WORLD_NAME=$(basename "${dir%/}")
            echo "Found world: $WORLD_NAME"
            break
        fi
    done
    
    # If still not found, check if level.dat exists directly in INPUT_DIR
    if [ -z "$WORLD_NAME" ] && [ -f "$INPUT_DIR/level.dat" ]; then
        echo "World files found directly in $INPUT_DIR"
        # No need for WORLD_NAME in this case
    elif [ -z "$WORLD_NAME" ]; then
        echo "Error: Could not find any Minecraft Bedrock world in $INPUT_DIR"
        echo "Make sure there is a folder with level.dat inside $INPUT_DIR"
        exit 1
    fi
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Clear temp directory if it exists
if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
fi

echo "Starting Bedrock to Java world conversion..."

# Prepare the input for conversion
if [ -n "$WORLD_NAME" ] && [ -d "$INPUT_DIR/$WORLD_NAME" ]; then
    echo "Creating temporary directory for world files..."
    mkdir -p "$TEMP_DIR"
    cp -r "$INPUT_DIR/$WORLD_NAME"/* "$TEMP_DIR/"
    
    # Execute the command using temp directory
    CMD="java -jar $JAR_FILE -i $TEMP_DIR -o $OUTPUT_DIR -f $FORMAT"
else
    # Use INPUT_DIR directly if world files are already there
    CMD="java -jar $JAR_FILE -i $INPUT_DIR -o $OUTPUT_DIR -f $FORMAT"
fi

echo "Running: $CMD"
eval $CMD

# Check if conversion was successful
if [ $? -eq 0 ]; then
    echo "Conversion completed successfully!"
    echo "Java worlds are located in $OUTPUT_DIR"
else
    echo "Conversion failed. Please check the error messages above."
fi

# Clean up temporary directory
if [ -d "$TEMP_DIR" ]; then
    echo "Cleaning up temporary files..."
    rm -rf "$TEMP_DIR"
fi

echo "Done."