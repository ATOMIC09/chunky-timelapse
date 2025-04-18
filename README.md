# Chunky Timelapse Generator

<p>
  <img alt="Version" src="https://img.shields.io/badge/version-1.0-blue.svg?cacheSeconds=2592000" />
  <a href="#" target="_blank">
    <img alt="License: MIT" src="https://img.shields.io/badge/License-GPLv3-yellow.svg" />
  </a>
  <a href="https://github.com/ATOMIC09/chunky-timelapse/tags">
      <img alt="Download" src="https://img.shields.io/github/downloads/ATOMIC09/chunky-timelapse/total" />
  </a>
</p>

![image](https://github.com/user-attachments/assets/ef8ce44c-31b9-4b26-8cb5-989126453c50)

## Overview

Chunky Timelapse Generator is designed to streamline the process of creating beautiful timelapse videos showing the progression of Minecraft worlds over time. This tool automates the rendering of multiple world snapshots and combines them into a smooth video, making it perfect for showcasing your builds as they evolve.

Especially useful when you have backed up worlds with date suffixes, this tool can automatically sort and render them in chronological order.

## Download
You can see all versions from `Releases` tab
- [`Download for Windows (v1.0)`](https://github.com/ATOMIC09/chunky-timelapse/releases/download/v1.0/ChunkyTimelapse-1.0-windows-x86_64.exe)

## Features

- **Batch Render Multiple Worlds**: Select multiple Minecraft world directories and render them in sequence
- **Built-in Chunky Integration**: Download Chunky directly from the application and render scenes
- **Automatic World Sorting**: Automatically sorts worlds with date patterns (DDMMYY format) chronologically
- **Video Creation**: Combine rendered snapshots into a video with configurable FPS and codec options
- **Day Counter**: Automatically displays the in-game day count on each frame
- **Progress Tracking**: Real-time rendering progress with detailed logging
- **Scene Management**: Work with your existing Chunky scenes or create new ones

## Requirements

- Python 3.9 or higher
- PyQt6
- OpenCV (cv2)
- Java 17 or higher *(required for Chunky)*
- Chunky *(can be downloaded through the application)*
- mcworldlib (for reading Minecraft world data)

## World Naming Convention

For optimal usage, name your world folders with a date suffix in DDMMYY format:
- Example: `my-minecraft-world-010422` (for April 1st, 2022)

When named this way, worlds will be automatically sorted chronologically in the timelapse.

## Input Directory Structure
```
world_java/
├── world-010124/
│   ├── level.dat
│   └── ... (other world files)
├── world-150625/
│   ├── level.dat
│   └── ... (other world files)
└── world-311226/
    ├── level.dat
    └── ... (other world files)
```

## How to Use

1. Create a Chunky scene with the camera position and settings you want before starting, you can see [renderlapse](https://github.com/moon44432/renderlapse?tab=readme-ov-file#preparing-json-file-requires-chunky) for an example of how to set up a scene then you will get a scene with json file at `.chunky/scenes/`

2. Choose the world directory containing your Minecraft Java worlds.

3. Select each world you want to include in the timelapse.
*(The tool will automatically sort the worlds based on their date suffix. e.g. `world-010124` will be sorted before `world-150625`)*

4. Click "Render Selected Worlds" to start the rendering process. The tool will use the selected Chunky scene to render each world snapshot. And the rendered images will be saved at `.chunky/scenes/snapshots/`

5. After rendering is complete, click "Create Video from Snapshots" to generate a video from the rendered images. You can configure the video settings such as FPS and codec.
