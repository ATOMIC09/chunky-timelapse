#!/bin/bash

# Script to convert Minecraft Bedrock worlds to Java format and take snapshots
# Using chunker-cli-1.7.0.jar and ChunkyLauncher.jar

# Set default values for all parameters
JAR_FILE="chunker-cli-1.7.0.jar"
CHUNKY_JAR="ChunkyLauncher.jar"
INPUT_DIR="./worlds/"
OUTPUT_DIR="./world_java/"
FORMAT="JAVA_1_21_5"
SCENE_DIR="/home/atomic/.chunky/scenes/smallnickbigtown-topview" # Edit your home directory
SCENE_NAME="smallnickbigtown-topview"
WORLD_NAME=""
TEMP_DIR="./temp_world"
TAKE_SNAPSHOT=true
CONVERT_BEDROCK_JAVA=true
SPP_TARGET="16"
MINECRAFT_JAR_VERSION="1.21.5"

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -j JAR_FILE    Path to the chunker-cli JAR file (default: $JAR_FILE)"
    echo "  -c CHUNKY_JAR  Path to the ChunkyLauncher JAR (default: $CHUNKY_JAR)"
    echo "  -i INPUT_DIR   Input directory containing Bedrock worlds (default: $INPUT_DIR)"
    echo "  -o OUTPUT_DIR  Output directory for Java worlds (default: $OUTPUT_DIR)"
    echo "  -f FORMAT      Target Java format (default: $FORMAT)"
    echo "  -w WORLD_NAME  Specific world folder name inside INPUT_DIR (default: first found)"
    echo "  -n SCENE_NAME  Scene name for Chunky render (default: $SCENE_NAME)"
    echo "  -m MC_VERSION  Minecraft version for texture resources (default: $MINECRAFT_JAR_VERSION)"
    echo "  -r            Take a snapshot after conversion (requires Chunky)"
    echo "  -b            Skip Bedrock to Java conversion (use existing world_java)"
    echo "  -h            Show this help"
    exit 0
}

# Process command line arguments
while getopts "j:c:i:o:f:w:n:m:rbh" opt; do
  case $opt in
    j) JAR_FILE="$OPTARG" ;;
    c) CHUNKY_JAR="$OPTARG" ;;
    i) INPUT_DIR="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    f) FORMAT="$OPTARG" ;;
    w) WORLD_NAME="$OPTARG" ;;
    n) SCENE_NAME="$OPTARG" ;;
    m) MINECRAFT_JAR_VERSION="$OPTARG" ;;
    r) TAKE_SNAPSHOT=true ;;
    b) CONVERT_BEDROCK_JAVA=false ;;
    h) show_help ;;
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done

# Remove trailing slash if present
INPUT_DIR=${INPUT_DIR%/}
OUTPUT_DIR=${OUTPUT_DIR%/}
SCENE_DIR=${SCENE_DIR%/}

# Display configuration
echo "Configuration:"
echo "  JAR File:      $JAR_FILE"
echo "  Input Dir:     $INPUT_DIR"
echo "  Output Dir:    $OUTPUT_DIR" 
echo "  Format:        $FORMAT"
if [ -n "$WORLD_NAME" ]; then
    echo "  World Name:    $WORLD_NAME"
fi
if [ "$TAKE_SNAPSHOT" = true ]; then
    echo "  Chunky JAR:    $CHUNKY_JAR"
    echo "  Scene Dir:     $SCENE_DIR"
    echo "  Scene Name:    $SCENE_NAME"
    echo "  MC Version:    $MINECRAFT_JAR_VERSION"
    echo "  Take Snapshot: Yes"
fi
echo "  Convert World: $([ "$CONVERT_BEDROCK_JAVA" = true ] && echo "Yes" || echo "No")"

# Only check for conversion dependencies if we're doing conversion
if [ "$CONVERT_BEDROCK_JAVA" = true ]; then
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
fi

# Check if Chunky JAR exists when snapshot is enabled
if [ "$TAKE_SNAPSHOT" = true ] && [ ! -f "$CHUNKY_JAR" ]; then
    echo "Error: $CHUNKY_JAR not found!"
    echo "Please provide the path to ChunkyLauncher.jar using the -c option"
    exit 1
fi

if [ "$CONVERT_BEDROCK_JAVA" = true ]; then
    # Remove old world_java directory if it exists
    if [ -d "$OUTPUT_DIR" ]; then
        echo "Removing old $OUTPUT_DIR directory..."
        rm -rf "$OUTPUT_DIR"
    fi

    # Create output directory
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
    if [ $? -ne 0 ]; then
        echo "Conversion failed. Please check the error messages above."
        # Clean up temporary directory
        if [ -d "$TEMP_DIR" ]; then
            echo "Cleaning up temporary files..."
            rm -rf "$TEMP_DIR"
        fi
        exit 1
    fi

    echo "Conversion completed successfully!"
    echo "Java worlds are located in $OUTPUT_DIR"
    
    # Clean up temporary directory
    if [ -d "$TEMP_DIR" ]; then
        echo "Cleaning up temporary files..."
        rm -rf "$TEMP_DIR"
    fi
else
    echo "Skipping Bedrock to Java conversion as requested."
    # Verify that world_java exists if we're skipping conversion
    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "Error: $OUTPUT_DIR directory not found but conversion was skipped!"
        echo "Please make sure the Java world exists or enable conversion."
        exit 1
    fi
    echo "Using existing Java world in $OUTPUT_DIR"
fi

# Take a snapshot if requested
if [ "$TAKE_SNAPSHOT" = true ]; then
    echo "Preparing to take a snapshot with Chunky..."
    
    # Check if scene directory exists
    if [ ! -d "$SCENE_DIR" ]; then
        echo "Error: Scene directory $SCENE_DIR not found!"
        exit 1
    fi
    
    # Check if scene JSON file exists
    SCENE_JSON="$SCENE_DIR/$SCENE_NAME.json"
    if [ ! -f "$SCENE_JSON" ]; then
        echo "Error: Scene file $SCENE_JSON not found!"
        exit 1
    fi
    
    # Check for minecraft.jar
    MINECRAFT_JAR_PATH="$HOME/.chunky/resources/minecraft.jar"
    if [ ! -f "$MINECRAFT_JAR_PATH" ]; then
        echo "minecraft.jar not found at $MINECRAFT_JAR_PATH"
        echo "Downloading Minecraft $MINECRAFT_JAR_VERSION for texture resources..."
        java -jar "$CHUNKY_JAR" -download-mc "$MINECRAFT_JAR_VERSION"
        
        # Check if download was successful
        if [ ! -f "$MINECRAFT_JAR_PATH" ]; then
            echo "Warning: Failed to download minecraft.jar. Rendering may not include proper textures."
        else
            echo "Successfully downloaded minecraft.jar textures."
        fi
    else
        echo "Found minecraft.jar textures."
    fi
    
    echo "Setting up Chunky scene..."
    
    # Delete .octree2 and .dump files if they exist
    echo "Removing previous octree and dump files..."
    rm -f "$SCENE_DIR/$SCENE_NAME.octree2" 2>/dev/null
    rm -f "$SCENE_DIR/$SCENE_NAME.dump" 2>/dev/null
    
    # Create snapshots directory if it doesn't exist
    SNAPSHOT_DIR="$SCENE_DIR/snapshots"
    if [ ! -d "$SNAPSHOT_DIR" ]; then
        echo "Creating snapshots directory: $SNAPSHOT_DIR"
        mkdir -p "$SNAPSHOT_DIR"
    fi
    
    # Run Chunky to take the snapshot
    echo "Taking snapshot with Chunky..."
    CMD2="java -jar "$CHUNKY_JAR" -scene-dir "$SCENE_DIR" -render "$SCENE_NAME" -f"
    
    echo "Running: $CMD2"
    eval $CMD2
    
    # Check if the snapshot was created
    if [ -d "$SNAPSHOT_DIR" ]; then
        # Find the latest snapshot
        LATEST_SNAPSHOT=$(ls -t "$SNAPSHOT_DIR"/"$SCENE_NAME"-"$SPP_TARGET".png 2>/dev/null | head -1)
        if [ -n "$LATEST_SNAPSHOT" ]; then
            echo "Snapshot created successfully: $LATEST_SNAPSHOT"
        else
            echo "Snapshot wasn't created or couldn't be found."
        fi
    else
        echo "Error: Snapshots directory doesn't exist after attempted creation."
    fi
fi

echo "Done."