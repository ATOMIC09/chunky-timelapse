#!/bin/bash

# Script to convert Minecraft Bedrock worlds to Java format and take snapshots
# Using chunker-cli-1.7.0.jar and ChunkyLauncher.jar

# Set default values for all parameters
JAR_FILE="$HOME/world-snapshot/chunker-cli-1.7.0.jar"
CHUNKY_JAR="$HOME/world-snapshot/ChunkyLauncher.jar"
INPUT_DIR="$HOME/world-snapshot/worlds"
OUTPUT_DIR="$HOME/world-snapshot/world_java/"
FORMAT="JAVA_1_21_5"
SCENE_NAME="smallnickbigtown-topview" # User-defined scene name
WORLD_NAME=""
TEMP_DIR="$HOME/world-snapshot/temp_world"
SPP_TARGET="16"
MINECRAFT_JAR_VERSION="1.21.5"
CHUNKY_HOME_DIR="$HOME/.chunky"
SCENE_DIR="$CHUNKY_HOME_DIR/scenes/$SCENE_NAME"
CHUNKY_DOWNLOAD_URL="https://chunkyupdate.lemaik.de/ChunkyLauncher.jar"
DISCORD_SH_URL="https://raw.githubusercontent.com/fieu/discord.sh/master/discord.sh"
NBT2JSON_SH_URL="https://raw.githubusercontent.com/mridlen/nbt2json/refs/heads/main/nbt2json.sh"
CONVERT_BEDROCK_JAVA=true
TAKE_SNAPSHOT=true

DISCORD_WEBHOOK_URL=""
DISCORD_WEBHOOK_USERNAME="Chunky Photographer"
DISCORD_WEBHOOK_AVATAR_URL="https://chunky-dev.github.io/docs/assets/hero.webp"

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
    echo "  -d CHUNKY_DIR  Path to Chunky home directory (default: $CHUNKY_HOME_DIR)"
    echo "  -u WEBHOOK_URL Discord webhook URL for notifications"
    echo "  -r            Take a snapshot after conversion (requires Chunky)"
    echo "  -b            Skip Bedrock to Java conversion (use existing world_java)"
    echo "  -h            Show this help"
    exit 0
}

# Function to convert hex to decimal
hex_to_decimal() {
    local hex=$1
    # Remove potential leading zeros
    hex=$(echo "$hex" | sed 's/^0*//')
    # If hex is empty after removing zeros, it was all zeros
    if [ -z "$hex" ]; then
        hex="0"
    fi
    echo $((16#$hex))
}

# Process command line arguments
while getopts "j:c:i:o:f:w:n:m:d:u:rbh" opt; do
  case $opt in
    j) JAR_FILE="$OPTARG" ;;
    c) CHUNKY_JAR="$OPTARG" ;;
    i) INPUT_DIR="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    f) FORMAT="$OPTARG" ;;
    w) WORLD_NAME="$OPTARG" ;;
    n) SCENE_NAME="$OPTARG" ;;
    m) MINECRAFT_JAR_VERSION="$OPTARG" ;;
    d) CHUNKY_HOME_DIR="$OPTARG" ;;
    u) DISCORD_WEBHOOK_URL="$OPTARG" ;;
    r) TAKE_SNAPSHOT=true ;;
    b) CONVERT_BEDROCK_JAVA=false ;;
    h) show_help ;;
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1 ;;
  esac
done

# Check if ChunkyLauncher.jar exists
if [ "$TAKE_SNAPSHOT" = true ] && [ ! -f "$CHUNKY_JAR" ]; then
    echo "ChunkyLauncher.jar not found at: $CHUNKY_JAR"
    
    # Check if wget is available
    if command -v wget > /dev/null 2>&1; then
        echo "Downloading ChunkyLauncher.jar using wget..."
        wget -O "$CHUNKY_JAR" "$CHUNKY_DOWNLOAD_URL"
        
        # Check if download was successful
        if [ ! -f "$CHUNKY_JAR" ]; then
            echo "Error: Failed to download ChunkyLauncher.jar."
            echo "Please download it manually from $CHUNKY_DOWNLOAD_URL"
            exit 1
        else
            echo "Successfully downloaded ChunkyLauncher.jar."
        fi
    # Check if curl is available as alternative
    elif command -v curl > /dev/null 2>&1; then
        echo "Downloading ChunkyLauncher.jar using curl..."
        curl -o "$CHUNKY_JAR" "$CHUNKY_DOWNLOAD_URL"
        
        # Check if download was successful
        if [ ! -f "$CHUNKY_JAR" ]; then
            echo "Error: Failed to download ChunkyLauncher.jar."
            echo "Please download it manually from $CHUNKY_DOWNLOAD_URL"
            exit 1
        else
            echo "Successfully downloaded ChunkyLauncher.jar."
        fi
    else
        echo "Error: Neither wget nor curl is available."
        echo "Please install wget or curl, or download ChunkyLauncher.jar manually from:"
        echo "$CHUNKY_DOWNLOAD_URL"
        exit 1
    fi
fi

# Check if Chunky home directory exists
if [ "$TAKE_SNAPSHOT" = true ] && [ ! -d "$CHUNKY_HOME_DIR" ]; then
    echo "Chunky home directory not found at: $CHUNKY_HOME_DIR"
    echo "Running Chunky update to initialize the directory..."
    
    java -jar "$CHUNKY_JAR" --update
    
    # Check again if directory was created
    if [ ! -d "$CHUNKY_HOME_DIR" ]; then
        echo "Error: Failed to create Chunky home directory."
        echo "Please run 'java -jar ChunkyLauncher.jar --update' manually and try again."
        exit 1
    else
        echo "Chunky home directory initialized successfully."
    fi
else
    echo "Chunky home directory found at: $CHUNKY_HOME_DIR"
fi

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
    echo "  Chunky Home:   $CHUNKY_HOME_DIR"
    echo "  Scene Dir:     $SCENE_DIR"
    echo "  Scene Name:    $SCENE_NAME"
    echo "  MC Version:    $MINECRAFT_JAR_VERSION"
    echo "  Take Snapshot: Yes"
fi
echo "  Convert World: $([ "$CONVERT_BEDROCK_JAVA" = true ] && echo "Yes" || echo "No")"
if [ -n "$DISCORD_WEBHOOK_URL" ]; then
    echo "  Discord Webhook: Enabled"
else
    echo "  Discord Webhook: Disabled"
fi

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

# Process level.dat to extract world information
echo "Processing level.dat to extract world information..."
LEVEL_DAT_PATH="$OUTPUT_DIR/level.dat"
LEVEL_DAT_JSON_PATH="$OUTPUT_DIR/level.dat.json"

# Check if level.dat exists
if [ ! -f "$LEVEL_DAT_PATH" ]; then
    echo "Warning: level.dat not found at $LEVEL_DAT_PATH"
    WORLD_INFO="World information not available"
else
    # Check for nbt2json.sh
    if [ ! -f "./nbt2json.sh" ]; then
        echo "nbt2json.sh not found. Downloading from $NBT2JSON_SH_URL..."
        
        # Try with wget first
        if command -v wget > /dev/null 2>&1; then
            wget -O "./nbt2json.sh" "$NBT2JSON_SH_URL"
        # Fall back to curl if wget is not available
        elif command -v curl > /dev/null 2>&1; then
            curl -o "./nbt2json.sh" "$NBT2JSON_SH_URL"
        else
            echo "Error: Neither wget nor curl is available to download nbt2json.sh"
            echo "Please download nbt2json.sh manually from $NBT2JSON_SH_URL"
            exit 1
        fi
        
        # Make sure nbt2json.sh is executable
        chmod +x ./nbt2json.sh
    fi
    
    # Run nbt2json.sh to convert level.dat to JSON
    echo "Converting level.dat to JSON..."
    ./nbt2json.sh "$LEVEL_DAT_PATH"
    
    # Extract world time from level.dat.json if it exists
    if [ -f "$LEVEL_DAT_JSON_PATH" ]; then
        echo "Extracting world information from level.dat.json..."
        
        # Use grep with different pattern that matches the actual JSON format
        # This will find the Time tag with format {"Tag":"04", "Label":"Time", "Payload":"HEXVALUE"},
        TIME_LINE=$(grep -o '{.*"Label":"Time".*"Payload":"[^"]*".*}' "$LEVEL_DAT_JSON_PATH")
        
        if [ -n "$TIME_LINE" ]; then
            # Extract the hex payload using sed
            TIME_HEX=$(echo "$TIME_LINE" | sed -n 's/.*"Payload":"\([^"]*\)".*/\1/p')
            
            if [ -n "$TIME_HEX" ]; then
                # Convert hex to decimal
                TIME_DEC=$(hex_to_decimal "$TIME_HEX")
                echo "World Time (hex): $TIME_HEX"
                echo "World Time (decimal): $TIME_DEC ticks"
                
                # Calculate days (20 min per day, 24000 ticks per day)
                DAYS=$(($TIME_DEC / 24000))
                REMAINING_TICKS=$(($TIME_DEC % 24000))
                HOURS=$(($REMAINING_TICKS / 1000))
                
                # Format time of day using 24-hour clock
                TIME_OF_DAY=$(printf "%02d:00" $HOURS)
                
                # Determine if it's day or night
                if [ $HOURS -ge 6 ] && [ $HOURS -lt 18 ]; then
                    DAYNIGHT="day"
                else
                    DAYNIGHT="night"
                fi
                
                WORLD_INFO="World Time: $TIME_DEC ticks (Day $DAYS, $TIME_OF_DAY, $DAYNIGHT)"
            else
                WORLD_INFO="Time value found but couldn't extract hex payload"
            fi
        else
            WORLD_INFO="Time value not found in level.dat.json"
            # Fallback to alternative grep pattern
            TIME_LINE=$(grep -o '"Label":"Time".*"Payload":"[^"]*"' "$LEVEL_DAT_JSON_PATH")
            if [ -n "$TIME_LINE" ]; then
                TIME_HEX=$(echo "$TIME_LINE" | sed -n 's/.*"Payload":"\([^"]*\)".*/\1/p')
                if [ -n "$TIME_HEX" ]; then
                    TIME_DEC=$(hex_to_decimal "$TIME_HEX")
                    echo "Found Time using fallback method: $TIME_DEC ticks"
                    DAYS=$(($TIME_DEC / 24000))
                    WORLD_INFO="World Time: $TIME_DEC ticks (Day $DAYS)"
                fi
            fi
        fi
        
        # Extract world name using better grep pattern
        LEVEL_NAME_LINE=$(grep -o '{.*"Label":"LevelName".*"Payload":"[^"]*".*}' "$LEVEL_DAT_JSON_PATH")
        if [ -n "$LEVEL_NAME_LINE" ]; then
            LEVEL_NAME=$(echo "$LEVEL_NAME_LINE" | sed -n 's/.*"Payload":"\([^"]*\)".*/\1/p')
            if [ -n "$LEVEL_NAME" ]; then
                WORLD_INFO="$WORLD_INFO\nWorld Name: $LEVEL_NAME"
            fi
        fi
        
        # Extract DayTime if available
        DAY_TIME_LINE=$(grep -o '{.*"Label":"DayTime".*"Payload":"[^"]*".*}' "$LEVEL_DAT_JSON_PATH")
        if [ -n "$DAY_TIME_LINE" ]; then
            DAY_TIME_HEX=$(echo "$DAY_TIME_LINE" | sed -n 's/.*"Payload":"\([^"]*\)".*/\1/p')
            if [ -n "$DAY_TIME_HEX" ]; then
                DAY_TIME_DEC=$(hex_to_decimal "$DAY_TIME_HEX")
                WORLD_INFO="$WORLD_INFO\nDay Time: $DAY_TIME_DEC ticks"
            fi
        fi
        
        # Extract difficulty if available
        DIFF_LINE=$(grep -o '{.*"Label":"Difficulty".*"Payload":"[^"]*".*}' "$LEVEL_DAT_JSON_PATH")
        if [ -n "$DIFF_LINE" ]; then
            DIFF_HEX=$(echo "$DIFF_LINE" | sed -n 's/.*"Payload":"\([^"]*\)".*/\1/p')
            if [ -n "$DIFF_HEX" ]; then
                DIFF_DEC=$(hex_to_decimal "$DIFF_HEX")
                DIFF_NAME=""
                case $DIFF_DEC in
                    0) DIFF_NAME="Peaceful" ;;
                    1) DIFF_NAME="Easy" ;;
                    2) DIFF_NAME="Normal" ;;
                    3) DIFF_NAME="Hard" ;;
                    *) DIFF_NAME="Unknown" ;;
                esac
                WORLD_INFO="$WORLD_INFO\nDifficulty: $DIFF_NAME"
            fi
        fi
        
    else
        WORLD_INFO="Could not generate level.dat.json"
    fi
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
    MINECRAFT_JAR_PATH="$CHUNKY_HOME_DIR/resources/minecraft.jar"
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
            
            # Send Discord notification if webhook URL is provided
            if [ -n "$DISCORD_WEBHOOK_URL" ]; then
                echo "Sending Discord notification..."
                
                # Check if discord.sh exists, download if not
                if [ ! -f "./discord.sh" ]; then
                    echo "discord.sh not found. Downloading from GitHub..."
                    
                    # Try with wget first
                    if command -v wget > /dev/null 2>&1; then
                        wget -O "./discord.sh" "$DISCORD_SH_URL"
                    # Fall back to curl if wget is not available
                    elif command -v curl > /dev/null 2>&1; then
                        curl -o "./discord.sh" "$DISCORD_SH_URL"
                    else
                        echo "Error: Neither wget nor curl is available to download discord.sh"
                        echo "Please download discord.sh manually from $DISCORD_SH_URL"
                        echo "Discord notification will be skipped."
                    fi
                fi
                
                # Make sure discord.sh is executable
                if [ -f "./discord.sh" ]; then
                    chmod +x ./discord.sh
                    
                    # Format date for the message
                    # CURRENT_DATE=$(date "+%Y-%m-%d %H:%M:%S")
                    
                    # Send notification with the snapshot and world information
                    ./discord.sh --webhook-url "$DISCORD_WEBHOOK_URL" \
                              --file "$LATEST_SNAPSHOT" \
                              --username "$DISCORD_WEBHOOK_USERNAME" \
                              --avatar "$DISCORD_WEBHOOK_AVATAR_URL" \
                              --text "$WORLD_INFO"
                else
                    echo "Error: discord.sh not found or couldn't be downloaded."
                    echo "Discord notification will be skipped."
                fi
            fi
        else
            echo "Snapshot wasn't created or couldn't be found."
        fi
    else
        echo "Error: Snapshots directory doesn't exist after attempted creation."
    fi
fi

echo "Done."