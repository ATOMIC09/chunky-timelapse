#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import shutil
import glob
from pathlib import Path
import threading
import queue
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QLineEdit, 
    QGroupBox, QFormLayout, QMessageBox, QTextEdit, QSplitter
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
    
    def __init__(self):
        super().__init__()
        
        # Default paths
        self.chunky_launcher_path = ""
        self.scenes_dir = os.path.join(os.path.expanduser("~"), ".chunky", "scenes")
        self.world_dir = ""
        self.scene_name = ""
        self.scene_json_data = None
        self.current_process = None
        self.output_reader = None
        
        # Connect signal to slot
        self.log_update_signal.connect(self.append_to_log)
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Chunky Timelapse Generator")
        self.setGeometry(100, 100, 900, 700)
        
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
        
        # World Directory
        world_layout = QHBoxLayout()
        self.world_dir_edit = QLineEdit()
        self.world_dir_edit.setPlaceholderText("Path to Minecraft world directory")
        self.world_dir_edit.setReadOnly(True)
        world_browse_btn = QPushButton("Browse...")
        world_browse_btn.clicked.connect(self.browse_world_dir)
        world_layout.addWidget(self.world_dir_edit)
        world_layout.addWidget(world_browse_btn)
        paths_layout.addRow("World Directory:", world_layout)
        
        paths_group.setLayout(paths_layout)
        upper_layout.addWidget(paths_group)
        
        # Scene info
        scene_info_group = QGroupBox("Scene Information")
        scene_info_layout = QVBoxLayout()
        self.scene_info_text = QTextEdit()
        self.scene_info_text.setReadOnly(True)
        scene_info_layout.addWidget(self.scene_info_text)
        scene_info_group.setLayout(scene_info_layout)
        upper_layout.addWidget(scene_info_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        buttons_layout.addStretch()
        
        self.render_button = QPushButton("Render Scene")
        self.render_button.clicked.connect(self.render_scene)
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
        main_splitter.setSizes([500, 200])
        
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
            self, "Select Minecraft World Directory", ""
        )
        if dir_path:
            self.world_dir = dir_path
            self.world_dir_edit.setText(dir_path)
            self.update_render_button_state()
            
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
        has_world = bool(self.world_dir)
        has_json = self.scene_json_data is not None
        
        # Enable the button only if all conditions are met
        can_render = has_launcher and has_scene and has_world and has_json
        
        # Use setEnabled with a bool value
        self.render_button.setEnabled(can_render)
        
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