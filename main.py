#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import shutil
import glob
import re
from pathlib import Path
import threading
import queue
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QLineEdit, 
    QGroupBox, QFormLayout, QMessageBox, QTextEdit, QSplitter,
    QListWidget, QAbstractItemView, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QObject

class ProcessOutputReader(QObject):
    output_received = pyqtSignal(str)
    
    def __init__(self, process):
        super().__init__()
        self.process = process
        self.queue = queue.Queue()
        self.running = True
        
    def start_reading(self):
        threading.Thread(target=self._read_output, daemon=True).start()
        threading.Thread(target=self._process_queue, daemon=True).start()
        
    def _read_output(self):
        for line in iter(self.process.stdout.readline, b''):
            if not self.running:
                break
            try:
                decoded_line = line.decode('utf-8').rstrip()
                self.queue.put(decoded_line)
            except UnicodeDecodeError:
                self.queue.put("[Error decoding output line]")
        
    def _process_queue(self):
        while self.running:
            try:
                line = self.queue.get(timeout=0.1)
                self.output_received.emit(line)
                self.queue.task_done()
            except queue.Empty:
                continue
            
    def stop(self):
        self.running = False

class ChunkyTimelapseApp(QMainWindow):
    # Add a signal for thread-safe log updates
    log_update_signal = pyqtSignal(str)
    progress_update_signal = pyqtSignal(int, int)  # current, total
    
    def __init__(self):
        super().__init__()
        
        # Default paths
        self.chunky_launcher_path = ""
        self.scenes_dir = os.path.join(os.path.expanduser("~"), ".chunky", "scenes")
        self.world_dir = ""  # Now this is the parent directory containing multiple worlds
        self.scene_name = ""
        self.scene_json_data = None
        self.current_process = None
        self.output_reader = None
        self.world_list = []  # Store list of worlds found
        self.render_queue = []  # Queue of worlds to render
        self.currently_rendering = False
        self.snapshot_pattern = None
        
        # Connect signals to slots
        self.log_update_signal.connect(self.append_to_log)
        self.progress_update_signal.connect(self.update_progress_bar)
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Chunky Timelapse Generator")
        self.setGeometry(100, 100, 1000, 800)
        
        # Create main splitter for upper and lower parts
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(main_splitter)
        
        # Upper part widget
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        
        # Path configuration group
        paths_group = QGroupBox("Configuration")
        paths_layout = QFormLayout()
        
        # Chunky Launcher
        chunky_layout = QHBoxLayout()
        self.chunky_path_edit = QLineEdit()
        self.chunky_path_edit.setPlaceholderText("Path to ChunkyLauncher.jar")
        self.chunky_path_edit.setReadOnly(True)
        chunky_browse_btn = QPushButton("Browse...")
        chunky_browse_btn.clicked.connect(self.browse_chunky_launcher)
        chunky_layout.addWidget(self.chunky_path_edit)
        chunky_layout.addWidget(chunky_browse_btn)
        paths_layout.addRow("Chunky Launcher:", chunky_layout)
        
        # Scenes Directory
        scenes_layout = QHBoxLayout()
        self.scenes_dir_edit = QLineEdit(self.scenes_dir)
        self.scenes_dir_edit.setReadOnly(True)
        scenes_browse_btn = QPushButton("Browse...")
        scenes_browse_btn.clicked.connect(self.browse_scenes_dir)
        scenes_layout.addWidget(self.scenes_dir_edit)
        scenes_layout.addWidget(scenes_browse_btn)
        paths_layout.addRow("Scenes Directory:", scenes_layout)
        
        # Scene selection
        self.scene_combo = QComboBox()
        self.scene_combo.currentTextChanged.connect(self.on_scene_selected)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_scenes)
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(self.scene_combo)
        scene_layout.addWidget(refresh_btn)
        paths_layout.addRow("Scene:", scene_layout)
        
        # Input Worlds Directory (parent directory containing multiple worlds)
        world_layout = QHBoxLayout()
        self.world_dir_edit = QLineEdit()
        self.world_dir_edit.setPlaceholderText("Path to parent directory containing Minecraft worlds")
        self.world_dir_edit.setReadOnly(True)
        world_browse_btn = QPushButton("Browse...")
        world_browse_btn.clicked.connect(self.browse_world_dir)
        scan_worlds_btn = QPushButton("Scan Worlds")
        scan_worlds_btn.clicked.connect(self.scan_worlds)
        world_layout.addWidget(self.world_dir_edit)
        world_layout.addWidget(world_browse_btn)
        world_layout.addWidget(scan_worlds_btn)
        paths_layout.addRow("Input Worlds:", world_layout)
        
        paths_group.setLayout(paths_layout)
        upper_layout.addWidget(paths_group)
        
        # World list and scene info in a horizontal split
        horz_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # World list group
        world_list_group = QGroupBox("Available Worlds")
        world_list_layout = QVBoxLayout()
        self.world_list_widget = QListWidget()
        self.world_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        world_list_layout.addWidget(self.world_list_widget)
        
        # Worlds control buttons
        worlds_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_worlds)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_worlds)
        worlds_buttons_layout.addWidget(self.select_all_btn)
        worlds_buttons_layout.addWidget(self.deselect_all_btn)
        world_list_layout.addLayout(worlds_buttons_layout)
        
        world_list_group.setLayout(world_list_layout)
        horz_splitter.addWidget(world_list_group)
        
        # Scene info
        scene_info_group = QGroupBox("Scene Information")
        scene_info_layout = QVBoxLayout()
        self.scene_info_text = QTextEdit()
        self.scene_info_text.setReadOnly(True)
        scene_info_layout.addWidget(self.scene_info_text)
        scene_info_group.setLayout(scene_info_layout)
        horz_splitter.addWidget(scene_info_group)
        
        # Add horizontal splitter to upper layout
        upper_layout.addWidget(horz_splitter)
        
        # Progress bar
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        upper_layout.addWidget(progress_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        buttons_layout.addStretch()
        
        self.render_button = QPushButton("Render Selected Worlds")
        self.render_button.clicked.connect(self.start_render_queue)
        self.render_button.setEnabled(False)
        
        buttons_layout.addWidget(self.render_button)
        
        upper_layout.addLayout(buttons_layout)
        
        # Add upper widget to splitter
        main_splitter.addWidget(upper_widget)
        
        # Log panel (lower part)
        log_group = QGroupBox("Process Output")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(self.create_monospace_font())
        log_layout.addWidget(self.log_text)
        
        # Log control buttons
        log_buttons_layout = QHBoxLayout()
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        log_buttons_layout.addStretch()
        log_buttons_layout.addWidget(self.clear_log_button)
        log_layout.addLayout(log_buttons_layout)
        
        log_group.setLayout(log_layout)
        main_splitter.addWidget(log_group)
        
        # Set initial splitter sizes
        main_splitter.setSizes([600, 200])
        
        # Initialize scene dropdown
        self.refresh_scenes()
        
    def create_monospace_font(self):
        font = self.log_text.font()
        font.setFamily("Courier New")
        return font
    
    def clear_log(self):
        self.log_text.clear()
        
    def append_to_log(self, text):
        self.log_text.append(text)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def browse_chunky_launcher(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ChunkyLauncher.jar", "", "JAR Files (*.jar)"
        )
        if file_path:
            self.chunky_launcher_path = file_path
            self.chunky_path_edit.setText(file_path)
            self.update_render_button_state()
            
    def browse_scenes_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Chunky Scenes Directory", self.scenes_dir
        )
        if dir_path:
            self.scenes_dir = dir_path
            self.scenes_dir_edit.setText(dir_path)
            self.refresh_scenes()
            
    def browse_world_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Parent Directory Containing Minecraft Worlds", ""
        )
        if dir_path:
            self.world_dir = dir_path
            self.world_dir_edit.setText(dir_path)
            self.scan_worlds()
            self.update_render_button_state()
            
    def scan_worlds(self):
        """Scan for Minecraft worlds in the selected directory"""
        self.world_list = []
        self.world_list_widget.clear()
        
        if not self.world_dir or not os.path.exists(self.world_dir):
            return
            
        try:
            # Look for directories containing level.dat
            for item in os.listdir(self.world_dir):
                item_path = os.path.join(self.world_dir, item)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "level.dat")):
                    self.world_list.append(item)
            
            # Populate the list widget
            self.world_list_widget.addItems(self.world_list)
            
            count = len(self.world_list)
            self.append_to_log(f"Found {count} Minecraft world{'s' if count != 1 else ''} in {self.world_dir}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to scan worlds: {str(e)}")
    
    def select_all_worlds(self):
        for i in range(self.world_list_widget.count()):
            self.world_list_widget.item(i).setSelected(True)
            
    def deselect_all_worlds(self):
        self.world_list_widget.clearSelection()
    
    def refresh_scenes(self):
        self.scene_combo.clear()
        
        try:
            scenes_path = Path(self.scenes_dir)
            if not scenes_path.exists():
                return
                
            # Find all scene directories (those containing a .json file with the same name)
            scene_dirs = [d for d in scenes_path.iterdir() if d.is_dir()]
            
            for scene_dir in scene_dirs:
                scene_name = scene_dir.name
                json_file = scene_dir / f"{scene_name}.json"
                if json_file.exists():
                    self.scene_combo.addItem(scene_name)
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load scenes: {str(e)}")
            
    def on_scene_selected(self):
        scene_name = self.scene_combo.currentText()
        # Reset state if no scene is selected
        if not scene_name:
            self.scene_name = ""
            self.scene_json_data = None
            self.scene_info_text.clear()
            self.update_render_button_state()
            return
        
        try:
            # Set the scene name properly
            self.scene_name = scene_name
            
            # Load the scene JSON
            json_path = os.path.join(self.scenes_dir, scene_name, f"{scene_name}.json")
            with open(json_path, 'r') as f:
                self.scene_json_data = json.load(f)
            
            # Display scene information
            self.display_scene_info()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load scene JSON: {str(e)}")
            self.scene_name = ""
            self.scene_json_data = None
            self.scene_info_text.clear()
        
        # Update button state after everything else
        self.update_render_button_state()

    def display_scene_info(self):
        if not self.scene_json_data:
            return
            
        info_text = ""
        
        # Add basic scene properties
        info_text += f"Scene Name: {self.scene_json_data.get('name', 'Unknown')}\n"
        info_text += f"Resolution: {self.scene_json_data.get('width', 'Unknown')}×{self.scene_json_data.get('height', 'Unknown')}\n"
        info_text += f"SPP Target: {self.scene_json_data.get('sppTarget', 'Unknown')}\n"
        
        # Add world information
        world_info = self.scene_json_data.get('world', {})
        info_text += f"Current World Path: {world_info.get('path', 'Not set')}\n"
        info_text += f"Dimension: {world_info.get('dimension', 'Unknown')}\n"
        
        # Add camera information
        camera_info = self.scene_json_data.get('camera', {})
        camera_pos = camera_info.get('position', {})
        if camera_pos:
            info_text += f"Camera Position: X:{camera_pos.get('x', 0):.2f}, Y:{camera_pos.get('y', 0):.2f}, Z:{camera_pos.get('z', 0):.2f}\n"
            
        self.scene_info_text.setPlainText(info_text)
        
    def update_render_button_state(self):
        # Check if all required fields are valid
        has_launcher = bool(self.chunky_launcher_path)
        has_scene = bool(self.scene_name)
        has_worlds_dir = bool(self.world_dir)
        has_json = self.scene_json_data is not None
        
        # Enable the button only if all conditions are met
        can_render = has_launcher and has_scene and has_worlds_dir and has_json
        
        # Use setEnabled with a bool value
        self.render_button.setEnabled(can_render)
        
    def update_progress_bar(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing world {current} of {total}")
            
    def start_render_queue(self):
        """Start rendering multiple worlds"""
        if self.currently_rendering:
            QMessageBox.warning(self, "Error", "A render is already in progress")
            return
            
        # Get selected worlds
        selected_worlds = [item.text() for item in self.world_list_widget.selectedItems()]
        if not selected_worlds:
            QMessageBox.warning(self, "Error", "No worlds selected for rendering")
            return
            
        # Setup the render queue
        self.render_queue = selected_worlds.copy()
        self.currently_rendering = True
        
        # Find the snapshot pattern from the scene directory to use for renaming
        self.detect_snapshot_pattern()
        
        # Start processing the queue
        self.append_to_log(f"Starting batch render of {len(self.render_queue)} world(s)")
        self.progress_update_signal.emit(0, len(self.render_queue))
        self.process_render_queue()
    
    def detect_snapshot_pattern(self):
        """Detect the snapshot filename pattern for the current scene"""
        snapshot_dir = os.path.join(self.scenes_dir, self.scene_name, "snapshots")
        if not os.path.exists(snapshot_dir):
            self.snapshot_pattern = f"{self.scene_name}-*.png"
            return
            
        # Look for existing snapshot files to determine the pattern
        snapshot_files = glob.glob(os.path.join(snapshot_dir, f"{self.scene_name}-*.png"))
        if snapshot_files:
            # Extract just the filename from the first snapshot
            filename = os.path.basename(snapshot_files[0])
            # Use regex to get the pattern (e.g., "test2-64.png" becomes "test2-(\d+).png")
            # Fix: Properly escape the regex pattern with raw string
            match = re.search(f"{self.scene_name}-(\\d+).png", filename)
            if match:
                self.snapshot_pattern = f"{self.scene_name}-{match.group(1)}.png"
            else:
                self.snapshot_pattern = f"{self.scene_name}-*.png"
        else:
            self.snapshot_pattern = f"{self.scene_name}-*.png"
            
        self.append_to_log(f"Detected snapshot pattern: {self.snapshot_pattern}")
        
    def process_render_queue(self):
        """Process the next world in the render queue"""
        if not self.render_queue:
            self.append_to_log("Batch rendering complete!")
            self.currently_rendering = False
            
            # Reset the progress bar and label to show completion
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.progress_label.setText("Rendering complete")
            
            # Re-enable UI elements that might have been disabled during rendering
            self.render_button.setEnabled(True)
            return
                
        # Get the next world to render
        world_name = self.render_queue.pop(0)
        world_path = os.path.join(self.world_dir, world_name)
        
        # Update progress bar
        current_index = len(self.world_list) - len(self.render_queue)
        total_worlds = len(self.world_list)
        self.progress_update_signal.emit(current_index, total_worlds)
        
        # Update the world path in the JSON
        self.append_to_log(f"Processing world: {world_name}")
        if not self.update_scene_json_with_path(world_path):
            # Skip this world if updating JSON failed
            self.append_to_log(f"Skipping world {world_name} due to JSON update failure")
            self.process_render_queue()
            return
            
        # Clean up .octree2 and .dump files before rendering
        self.cleanup_scene_files()
        
        # Prepare for post-render actions by storing world name
        self.current_world_name = world_name
        
        # Start the render
        self.render_scene_for_queue()
    
    def update_scene_json_with_path(self, world_path):
        """Update the scene JSON with a specific world path"""
        if not self.scene_json_data:
            return False
            
        try:
            # Update world path in JSON
            escaped_path = world_path.replace('\\', '\\\\')  # Properly escape backslashes
            self.scene_json_data['world']['path'] = escaped_path
            
            # Save updated JSON
            json_path = os.path.join(self.scenes_dir, self.scene_name, f"{self.scene_name}.json")
            with open(json_path, 'w') as f:
                json.dump(self.scene_json_data, f, indent=2)
                
            self.append_to_log(f"Updated scene JSON with world path: {world_path}")
            return True
                
        except Exception as e:
            self.append_to_log(f"Error updating scene JSON: {str(e)}")
            return False
    
    def render_scene_for_queue(self):
        """Render a scene as part of a batch queue"""
        try:
            cmd = [
                "java", "-jar", self.chunky_launcher_path,
                "-scene-dir", self.scenes_dir,
                "-render", self.scene_name,
                "-f"
            ]
            
            # Display command in log
            cmd_str = " ".join(cmd)
            self.append_to_log(f"Starting render with command:\n{cmd_str}\n")
            
            # Start the process with pipe for stdout and stderr
            # Fix: Remove bufsize parameter that was causing warnings
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False
            )
            
            # Set up the output reader
            self.output_reader = ProcessOutputReader(self.current_process)
            self.output_reader.output_received.connect(self.append_to_log)
            self.output_reader.start_reading()
            
            # Add monitoring thread to check when process is done
            threading.Thread(target=self.monitor_queue_process, daemon=True).start()
                
        except Exception as e:
            error_msg = f"Failed to start render: {str(e)}"
            self.append_to_log(f"ERROR: {error_msg}")
            # Continue with next world in queue even if this one failed
            self.process_render_queue()
            
    def monitor_queue_process(self):
        """Monitor the subprocess for queue processing and handle completion"""
        if not self.current_process:
            return
            
        # Wait for process to complete
        return_code = self.current_process.wait()
        
        # Stop the output reader
        if self.output_reader:
            self.output_reader.stop()
            
        # Log the completion status
        completion_msg = f"Render process completed with return code: {return_code}"
        self.log_update_signal.emit(completion_msg)
        
        # Rename the snapshot file to include the world name
        if return_code == 0:
            self.rename_snapshot_with_world_name()
            
        # Process the next world in the queue
        # Using a timer to avoid threading issues
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self.process_render_queue)
            
    def rename_snapshot_with_world_name(self):
        """Rename the snapshot file to include the world name"""
        try:
            snapshot_dir = os.path.join(self.scenes_dir, self.scene_name, "snapshots")
            if not os.path.exists(snapshot_dir):
                self.append_to_log("No snapshots directory found")
                return
                
            # Find the most recent snapshot file
            snapshot_files = glob.glob(os.path.join(snapshot_dir, f"{self.scene_name}-*.png"))
            if not snapshot_files:
                self.append_to_log("No snapshot files found")
                return
                
            # Sort by modification time to get the most recent one
            latest_snapshot = max(snapshot_files, key=os.path.getmtime)
            
            # Create the new filename with world name
            base_name = os.path.basename(latest_snapshot)
            # Extract the SPP number from filename (test2-64.png → 64)
            spp_match = re.search(f"{self.scene_name}-(\\d+).png", base_name)
            if spp_match:
                spp_num = spp_match.group(1)
                new_name = f"{self.scene_name}-{spp_num}-{self.current_world_name}.png"
            else:
                # Fallback if pattern doesn't match
                name_parts = os.path.splitext(base_name)
                new_name = f"{name_parts[0]}-{self.current_world_name}{name_parts[1]}"
                
            new_path = os.path.join(snapshot_dir, new_name)
            
            # Instead of copying, move the file (rename)
            shutil.move(latest_snapshot, new_path)
            self.append_to_log(f"Renamed snapshot to: {new_name}")
                
        except Exception as e:
            self.append_to_log(f"Error renaming snapshot: {str(e)}")
            
    def update_scene_json(self):
        if not self.scene_json_data or not self.world_dir:
            return False
            
        try:
            # Update world path in JSON
            escaped_path = self.world_dir.replace('\\', '\\\\')  # Properly escape backslashes
            self.scene_json_data['world']['path'] = escaped_path
            
            # Save updated JSON
            json_path = os.path.join(self.scenes_dir, self.scene_name, f"{self.scene_name}.json")
            with open(json_path, 'w') as f:
                json.dump(self.scene_json_data, f, indent=2)
                
            return True
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update scene JSON: {str(e)}")
            return False
    
    def cleanup_scene_files(self):
        """Remove .octree2 and .dump files from the scene directory"""
        if not self.scene_name or not self.scenes_dir:
            return
        
        scene_path = os.path.join(self.scenes_dir, self.scene_name)
        if not os.path.exists(scene_path):
            return
            
        try:
            # Find all .octree2 files
            octree_files = glob.glob(os.path.join(scene_path, "*.octree2"))
            dump_files = glob.glob(os.path.join(scene_path, "*.dump"))
            
            # Count files to be removed
            total_files = len(octree_files) + len(dump_files)
            self.append_to_log(f"Cleaning up: Found {total_files} files to remove...")
            
            # Remove .octree2 files
            for file in octree_files:
                os.remove(file)
                self.append_to_log(f"Removed: {os.path.basename(file)}")
                
            # Remove .dump files
            for file in dump_files:
                os.remove(file)
                self.append_to_log(f"Removed: {os.path.basename(file)}")
                
            self.append_to_log(f"Cleanup completed: {total_files} files removed.")
            
        except Exception as e:
            self.append_to_log(f"Error during cleanup: {str(e)}")
            
    def render_scene(self):
        """Render a single scene (used when not in batch mode)"""
        if not self.update_scene_json():
            return
        
        # Clean up .octree2 and .dump files before rendering
        self.cleanup_scene_files()
            
        try:
            cmd = [
                "java", "-jar", self.chunky_launcher_path,
                "-scene-dir", self.scenes_dir,
                "-render", self.scene_name,
                "-f"
            ]
            
            # Display command in log
            cmd_str = " ".join(cmd)
            self.append_to_log(f"Starting render with command:\n{cmd_str}\n")
            
            # Start the process with pipe for stdout and stderr
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                bufsize=1
            )
            
            # Set up the output reader
            self.output_reader = ProcessOutputReader(self.current_process)
            self.output_reader.output_received.connect(self.append_to_log)
            self.output_reader.start_reading()
            
            # Add monitoring thread to check when process is done
            threading.Thread(target=self.monitor_process, daemon=True).start()
                
        except Exception as e:
            error_msg = f"Failed to start render: {str(e)}"
            QMessageBox.critical(self, "Error", error_msg)
            self.append_to_log(f"ERROR: {error_msg}")
            
    def monitor_process(self):
        """Monitor the subprocess and cleanup when it's done"""
        if not self.current_process:
            return
            
        # Wait for process to complete
        return_code = self.current_process.wait()
        
        # Stop the output reader
        if self.output_reader:
            self.output_reader.stop()
            
        # Log the completion status
        completion_msg = f"\nProcess completed with return code: {return_code}"
        # Use the signal/slot mechanism to safely update GUI from a non-GUI thread
        self.log_update_signal.emit(completion_msg)

def main():
    app = QApplication(sys.argv)
    window = ChunkyTimelapseApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()