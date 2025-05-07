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
import cv2
from datetime import datetime
import requests
import mcworldlib as mc


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QLineEdit, 
    QGroupBox, QFormLayout, QMessageBox, QTextEdit, QSplitter,
    QListWidget, QAbstractItemView, QProgressBar, QDialog, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QIcon

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

class DownloadThread(QThread):
    """Thread for downloading ChunkyLauncher.jar"""
    progress_updated = pyqtSignal(int)
    download_complete = pyqtSignal(str)
    download_error = pyqtSignal(str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        
    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            if response.status_code != 200:
                self.download_error.emit(f"Failed to download file: {response.status_code}")
                return
                
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  # 1 Kibibyte
            downloaded = 0
            
            with open(self.save_path, 'wb') as file:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    file.write(data)
                    if total_size:
                        percent = int(downloaded * 100 / total_size)
                        self.progress_updated.emit(percent)
                        
            self.download_complete.emit(self.save_path)
        except Exception as e:
            self.download_error.emit(f"Error downloading file: {str(e)}")
            if os.path.exists(self.save_path):
                os.remove(self.save_path)  # Clean up partially downloaded file

class VideoSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Export Settings")
        self.setMinimumWidth(400)
        
        # Default settings
        self.fps = 1
        self.codec = "h264"
        self.output_path = ""
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # FPS selector
        fps_group = QGroupBox("Frames Per Second (FPS)")
        fps_layout = QVBoxLayout()
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 60)
        self.fps_slider.setValue(self.fps)
        self.fps_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fps_slider.setTickInterval(5)
        self.fps_label = QLabel(f"FPS: {self.fps}")
        self.fps_slider.valueChanged.connect(self.update_fps_label)
        fps_layout.addWidget(self.fps_label)
        fps_layout.addWidget(self.fps_slider)
        fps_group.setLayout(fps_layout)
        layout.addWidget(fps_group)
        
        # Codec selector
        codec_group = QGroupBox("Video Codec")
        codec_layout = QVBoxLayout()
        self.codec_combo = QComboBox()
        self.codec_combo.addItem("H.264 (.mp4)", "h264")
        self.codec_combo.addItem("MPEG-4 (.mp4)", "mp4v")
        self.codec_combo.addItem("AVI (.avi)", "XVID")
        codec_layout.addWidget(self.codec_combo)
        codec_info = QLabel("Note: H.264 is most compatible with messaging apps")
        codec_info.setWordWrap(True)
        codec_layout.addWidget(codec_info)
        codec_group.setLayout(codec_layout)
        layout.addWidget(codec_group)
        
        # Output file location
        output_group = QGroupBox("Output File")
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Output video file path")
        self.output_path_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(browse_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Create Video")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)
        
    def update_fps_label(self, value):
        self.fps = value
        self.fps_label.setText(f"FPS: {value}")
        
    def browse_output(self):
        # Get selected codec info for proper file extension
        codec_data = self.codec_combo.currentData()
        extension = ".mp4" if codec_data in ["h264", "mp4v"] else ".avi"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Video File", "", f"Video Files (*{extension})"
        )
        if file_path:
            # Ensure correct extension
            if not file_path.lower().endswith(extension):
                file_path += extension
                
            self.output_path = file_path
            self.output_path_edit.setText(file_path)
            self.ok_button.setEnabled(True)
            
    def get_settings(self):
        return {
            "fps": self.fps,
            "codec": self.codec_combo.currentData(),
            "output_path": self.output_path
        }

class ChunkyTimelapseApp(QMainWindow):
    # Add a signal for thread-safe log updates
    log_update_signal = pyqtSignal(str)
    progress_update_signal = pyqtSignal(int, int)  # current, total
    
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
        self.world_list = []
        self.render_queue = [] 
        self.currently_rendering = False
        self.snapshot_pattern = None
        self.download_thread = None
        
        # Connect signals to slots
        self.log_update_signal.connect(self.append_to_log)
        self.progress_update_signal.connect(self.update_progress_bar)
        
        # Find ChunkyLauncher.jar in various locations
        self.find_chunky_launcher()
            
        # Check if .chunky directory exists
        self.chunky_home = os.path.join(os.path.expanduser("~"), ".chunky")
        self.chunky_initialized = os.path.exists(self.chunky_home)
            
        self.initUI()
        
    def find_chunky_launcher(self):
        """Find ChunkyLauncher.jar in various potential locations"""
        # List of locations to check
        search_locations = ['.']  # Current directory is always checked
        
        # 1. Check the directory of the executable if running as compiled app
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            search_locations.append(exe_dir)
        
        # 2. Check the directory of the script if running as Python script
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        search_locations.append(script_dir)
        
        # 3. Check platform-specific application directories
        if sys.platform == 'win32':  # Windows
            app_data_dir = os.path.join(os.environ.get("APPDATA", ""), "ChunkyTimelapse")
            if os.path.exists(app_data_dir):
                search_locations.append(app_data_dir)
        elif sys.platform == 'darwin':  # macOS
            documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
            app_data_dir = os.path.join(documents_dir, "ChunkyTimelapse")
            if os.path.exists(app_data_dir):
                search_locations.append(app_data_dir)
        else:  # Linux and others
            app_data_dir = os.path.join(os.path.expanduser("~"), ".chunky-timelapse")
            if os.path.exists(app_data_dir):
                search_locations.append(app_data_dir)
                
        # Search for jar in all potential locations
        for location in search_locations:
            print(f"Searching for ChunkyLauncher.jar in: {location}")
            jar_path = os.path.join(location, "ChunkyLauncher.jar")
            if os.path.exists(jar_path) and os.path.isfile(jar_path):
                self.chunky_launcher_path = jar_path
                return
                
        # If not found, leave the path empty
        self.chunky_launcher_path = ""
        
    def initUI(self):
        self.setWindowTitle("Chunky Timelapse Generator")
        self.setGeometry(100, 100, 1000, 800)
        
        # Check if .chunky directory exists and notify if it doesn't
        if not self.chunky_initialized:
            QMessageBox.warning(
                self,
                "Chunky Not Initialized",
                "The Chunky configuration directory (.chunky) was not found.\n\n"
                "Please run ChunkyLauncher.jar at least once to set up the configuration "
                "before using this application."
            )
        
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
        # Set the path if auto-detected
        if self.chunky_launcher_path:
            self.chunky_path_edit.setText(self.chunky_launcher_path)
        self.chunky_path_edit.setReadOnly(True)
        chunky_browse_btn = QPushButton("Browse...")
        chunky_browse_btn.clicked.connect(self.browse_chunky_launcher)
        chunky_download_btn = QPushButton("Download")
        chunky_download_btn.clicked.connect(self.download_chunky_launcher)
        chunky_layout.addWidget(self.chunky_path_edit)
        chunky_layout.addWidget(chunky_browse_btn)
        chunky_layout.addWidget(chunky_download_btn)
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
        
        # Add Create Video button
        self.create_video_btn = QPushButton("Create Video from Snapshots")
        self.create_video_btn.clicked.connect(self.create_video_from_snapshots)
        buttons_layout.addWidget(self.create_video_btn)
        
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
        
        # Add source code link as leftmost element
        source_link = QLabel()
        source_link.setText("<a href='https://github.com/ATOMIC09/chunky-timelapse'>Source Code</a>")
        source_link.setOpenExternalLinks(True)
        source_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        log_buttons_layout.addWidget(source_link)
        
        # Add save log button
        log_buttons_layout.addStretch()
        self.save_log_button = QPushButton("Save Log")
        self.save_log_button.clicked.connect(self.save_log_to_file)
        log_buttons_layout.addWidget(self.save_log_button)
        
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
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
        
    def save_log_to_file(self):
        """Save the log to a file with datetime in the filename"""
        try:
            # Generate filename with current datetime (YYMMDD format)
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            log_filename = f"log_{timestamp}.txt"
            
            # Ask user for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Log File", log_filename, "Text Files (*.txt)"
            )
            
            if file_path:
                # Write log content to file using UTF-8 encoding
                with open(file_path, 'w', encoding='utf-8') as log_file:
                    log_file.write(self.log_text.toPlainText())
                
                self.append_to_log(f"Log saved to: {file_path}")
                QMessageBox.information(self, "Log Saved", f"Log has been saved to {file_path}")
        except Exception as e:
            error_msg = f"Error saving log: {str(e)}"
            self.append_to_log(error_msg)
            QMessageBox.critical(self, "Save Log Error", error_msg)
        
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
            
    def parse_date_from_world_name(self, world_name):
        """
        Parses a date from a world name with format [arbitrary name]-YYMMDD
        Returns a datetime object if successful, or None if not a valid date format
        """
        # Look for any text followed by a dash and YYMMDD pattern
        date_match = re.search(r'-(\d{2})(\d{2})(\d{2})$', world_name)
        if date_match:
            try:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                
                # Add 2000 to the year (assuming 20xx for years)
                year += 2000
                
                # Validate the date components
                if 1 <= day <= 31 and 1 <= month <= 12:
                    from datetime import datetime
                    return datetime(year, month, day)
            except ValueError:
                # If date is invalid (e.g., February 31st), return None
                pass
        return None
            
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
            
            # Sort worlds by date if they have YYMMDD format
            worlds_with_dates = []
            other_worlds = []
            
            for world in self.world_list:
                parsed_date = self.parse_date_from_world_name(world)
                if parsed_date:
                    worlds_with_dates.append((world, parsed_date))
                else:
                    other_worlds.append(world)
            
            # Sort worlds with dates chronologically
            worlds_with_dates.sort(key=lambda x: x[1])
            
            # Create final sorted list: date-based worlds first, then others
            self.world_list = [world for world, _ in worlds_with_dates] + other_worlds
            
            # Populate the list widget with the sorted worlds
            self.world_list_widget.addItems(self.world_list)
            
            count = len(self.world_list)
            date_sorted_count = len(worlds_with_dates)
            self.append_to_log(f"Found {count} Minecraft world{'s' if count != 1 else ''} in {self.world_dir}")
            if date_sorted_count > 0:
                self.append_to_log(f"Sorted {date_sorted_count} worlds by YYMMDD date format")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to scan worlds: {str(e)}")
            self.append_to_log(f"Error scanning worlds: {str(e)}")
    
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
            # Update world path in JSON with normalized path separators
            # Convert all path separators to forward slashes for consistency
            normalized_path = world_path.replace('\\', '/')
            self.scene_json_data['world']['path'] = normalized_path
            
            # Save updated JSON
            json_path = os.path.join(self.scenes_dir, self.scene_name, f"{self.scene_name}.json")
            with open(json_path, 'w') as f:
                json.dump(self.scene_json_data, f, indent=2)
                
            self.append_to_log(f"Updated scene JSON with world path: {normalized_path}")
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
                "-render", f'"{self.scene_name}"',
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
                "-render", f'"{self.scene_name}"',
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
                universal_newlines=False
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
        
    def create_video_from_snapshots(self):
        """Create a video from the rendered snapshots"""
        if not self.scene_name:
            QMessageBox.warning(self, "Error", "Please select a scene first")
            return
            
        # Warning about world directory if not set but don't prevent video creation
        if not self.world_dir or not os.path.exists(self.world_dir):
            QMessageBox.information(
                self, 
                "World Directory Not Set", 
                "No world directory selected. Day values in the video will use sequence numbers instead of actual game days."
            )
            
        # Check for snapshots
        snapshot_dir = os.path.join(self.scenes_dir, self.scene_name, "snapshots")
        if not os.path.exists(snapshot_dir):
            QMessageBox.warning(self, "Error", "No snapshots directory found")
            return
            
        # Get list of snapshot images with world names
        snapshot_files = glob.glob(os.path.join(snapshot_dir, f"{self.scene_name}-*-*.png"))
        if not snapshot_files:
            QMessageBox.warning(
                self, 
                "No Snapshots Found", 
                f"No snapshots with world names found in {snapshot_dir}.\n\nMake sure you've rendered scenes with world names."
            )
            return
            
        # Sort snapshots by extracting dates from world names
        sorted_snapshots = []
        for snapshot in snapshot_files:
            # Extract world name from pattern: scene-sppvalue-worldname.png
            base_name = os.path.basename(snapshot)
            world_name_match = re.search(f"{self.scene_name}-\\d+-(.+)\\.png", base_name)
            if world_name_match:
                world_name = world_name_match.group(1)
                # Parse date from world name
                parsed_date = self.parse_date_from_world_name(world_name)
                if parsed_date:
                    self.append_to_log(f"Found date in snapshot: {world_name} → {parsed_date.strftime('%d/%m/%Y')}")
                    sorted_snapshots.append((snapshot, parsed_date, world_name))
                else:
                    # If no date in the world name, add it with minimal date for sorting
                    sorted_snapshots.append((snapshot, datetime.min, world_name))
            else:
                # If we can't extract a world name, put it at the beginning
                sorted_snapshots.append((snapshot, datetime.min, "unknown"))
        
        # Log the unsorted world names first (for debugging)
        # self.append_to_log("Snapshots before sorting:")
        # for snapshot, _, world_name in sorted_snapshots:
        #     self.append_to_log(f"  - {os.path.basename(snapshot)} ({world_name})")
                
        # Sort by date (chronologically)
        sorted_snapshots.sort(key=lambda x: x[1])
        
        # Extract just the file paths after sorting
        snapshot_files = [item[0] for item in sorted_snapshots]
        
        # Log the sorted world names (for debugging)
        # self.append_to_log("Snapshots after sorting:")
        # for i, (snapshot, date, world_name) in enumerate(sorted_snapshots):
        #     date_str = date.strftime("%d/%m/%Y") if date != datetime.min else "No date"
        #     self.append_to_log(f"  {i+1}. {os.path.basename(snapshot)} - {world_name} ({date_str})")
        
        self.append_to_log(f"Sorted {len(snapshot_files)} snapshots chronologically by date in world names")
            
        # Ask user for video settings
        settings_dialog = VideoSettingsDialog(self)
        if settings_dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        # Get settings
        settings = settings_dialog.get_settings()
        
        # Create video
        self.append_to_log(f"Creating video from {len(snapshot_files)} snapshots...")
        threading.Thread(
            target=self.create_video_thread,
            args=(snapshot_files, settings),
            daemon=True
        ).start()

    def create_video_thread(self, snapshot_files, settings):
        """Thread for creating video without blocking UI"""
        try:
            # Get first image to determine size
            first_img = cv2.imread(snapshot_files[0])
            height, width, _ = first_img.shape
            
            # Check if resolution needs to be adjusted for compatibility (most messengers prefer ≤1080p)
            max_height = 1080
            if height > max_height:
                # Calculate new width to maintain aspect ratio
                scale_factor = max_height / height
                new_width = int(width * scale_factor)
                new_height = max_height
                self.log_update_signal.emit(f"Resizing frames from {width}x{height} to {new_width}x{new_height} for better compatibility")
                resize_needed = True
                output_size = (new_width, new_height)
            else:
                resize_needed = False
                output_size = (width, height)
                
            # H.264 codec with specific parameters for messaging platforms
            if settings['codec'] == 'h264':
                # For H.264, use a specific FourCC and parameters optimal for messaging
                fourcc = cv2.VideoWriter_fourcc(*'avc1')  # Alternative H.264 FourCC that works better on some systems
            else:
                # Use the selected codec
                fourcc = cv2.VideoWriter_fourcc(*settings['codec'])
                
            # Setup video writer with optimized parameters
            out = cv2.VideoWriter(
                settings['output_path'],
                fourcc,
                settings['fps'],
                output_size
            )
            
            if not out.isOpened():
                raise Exception(f"Could not open video writer with codec {settings['codec']}. Try using a different codec.")
            
            # Dictionary to map worlds to day values
            world_day_map = {}
            
            # Process each image
            for i, img_path in enumerate(snapshot_files):
                # Update progress in UI
                progress_msg = f"Processing frame {i+1}/{len(snapshot_files)}"
                self.log_update_signal.emit(progress_msg)
                
                # Read frame
                frame = cv2.imread(img_path)
                if frame is None:
                    self.log_update_signal.emit(f"Warning: Could not read frame from {img_path}")
                    continue
                    
                # Resize if needed
                if resize_needed:
                    frame = cv2.resize(frame, output_size, interpolation=cv2.INTER_LANCZOS4)
                
                # Extract world name from filename for day calculation
                base_name = os.path.basename(img_path)
                # Extract world name from pattern: scene-sppvalue-worldname.png
                world_name_match = re.search(f"{self.scene_name}-\\d+-(.+)\\.png", base_name)
                
                # Default day value and world name
                day_value = i+1
                world_name = "Unknown"
                
                if world_name_match:
                    world_name = world_name_match.group(1)
                    
                    # Check if we have already calculated for this world
                    if world_name in world_day_map:
                        day_value = world_day_map[world_name]
                    else:
                        # Try to calculate the actual day value using mcworldlib
                        if mc is not None:
                            try:
                                world_path = os.path.join(self.world_dir, world_name)
                                if os.path.exists(world_path):
                                    self.log_update_signal.emit(f"Reading Minecraft data from: {world_path}")
                                    world = mc.load(world_path)
                                    time_value = world.level['Data']['Time']
                                    days = time_value // 24000
                                    day_value = days
                                    world_day_map[world_name] = day_value
                                    self.log_update_signal.emit(f"World '{world_name}' is on day {day_value}")
                            except Exception as e:
                                self.log_update_signal.emit(f"Error reading day value: {str(e)}")
                
                # Create text with both day number and world name
                day_text = f"Day {day_value} ({world_name})"
                
                # Add text to the frame
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 1.2
                font_thickness = 2
                
                # Draw text with black outline for better visibility
                text_position = (20, 50)  # Top-left corner with margin
                
                # Draw black outline
                for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
                    cv2.putText(
                        frame, 
                        day_text, 
                        (text_position[0]+dx, text_position[1]+dy), 
                        font, 
                        font_scale, 
                        (0,0,0), 
                        font_thickness+1, 
                        cv2.LINE_AA
                    )
                
                # Draw white text on top
                cv2.putText(
                    frame, 
                    day_text, 
                    text_position, 
                    font, 
                    font_scale, 
                    (255,255,255), 
                    font_thickness, 
                    cv2.LINE_AA
                )
                    
                # Write the frame
                out.write(frame)
            
            # Release video writer
            out.release()
            
            # Final message
            completion_msg = f"Video created successfully: {settings['output_path']}"
            self.log_update_signal.emit(completion_msg)
            
            # Add compatibility note
            if settings['codec'] == 'h264':
                compatibility_note = ("Note: Your video is created using H.264 codec which should be compatible "
                                    "with most messaging platforms. If you still encounter issues, try reducing "
                                    "the resolution or framerate.")
                self.log_update_signal.emit(compatibility_note)
                
        except Exception as e:
            error_msg = f"Error creating video: {str(e)}"
            self.log_update_signal.emit(error_msg)

    def download_chunky_launcher(self):
        """Download the ChunkyLauncher.jar from the official URL"""
        chunky_url = "https://chunkyupdate.lemaik.de/ChunkyLauncher.jar"

        # Choose download directory based on platform
        if sys.platform == 'darwin':  # macOS
            # Use Documents folder on macOS to avoid read-only app bundle issues
            documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
            download_dir = os.path.join(documents_dir, "ChunkyTimelapse")
        else:  # Windows and others
            download_dir = '.'
        download_path = os.path.join(download_dir, "ChunkyLauncher.jar")
        
        # Create a download dialog with progress bar
        download_dialog = QDialog(self)
        download_dialog.setWindowTitle("Downloading ChunkyLauncher.jar")
        download_dialog.setFixedSize(400, 100)
        
        layout = QVBoxLayout(download_dialog)
        
        # Add progress bar
        progress_bar = QProgressBar(download_dialog)
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(0)
        
        # Add status label
        status_label = QLabel("Starting download...")
        
        layout.addWidget(status_label)
        layout.addWidget(progress_bar)
        
        # Show dialog but don't block
        download_dialog.show()
        QApplication.processEvents()
        
        try:
            self.append_to_log(f"Downloading ChunkyLauncher.jar from {chunky_url}...")
            self.append_to_log(f"Will save to: {download_path}")
            
            # Create a download thread
            self.download_thread = DownloadThread(chunky_url, download_path)
            self.download_thread.progress_updated.connect(progress_bar.setValue)
            self.download_thread.download_complete.connect(lambda path: self.on_download_complete(path, download_dialog))
            self.download_thread.download_error.connect(lambda error: self.on_download_error(error, download_dialog))
            self.download_thread.start()
            
        except Exception as e:
            error_msg = f"Unexpected error during download: {str(e)}"
            self.append_to_log(f"ERROR: {error_msg}")
            QMessageBox.critical(self, "Download Error", error_msg)
            
    def on_download_complete(self, path, dialog):
        """Handle successful download"""
        dialog.accept()
        self.chunky_launcher_path = path
        self.chunky_path_edit.setText(path)
        self.append_to_log(f"Download complete. Saved to {path}")
        QMessageBox.information(self, "Download Complete", f"ChunkyLauncher.jar has been downloaded")
        self.update_render_button_state()
        
    def on_download_error(self, error, dialog):
        """Handle download error"""
        dialog.reject()
        self.append_to_log(f"ERROR: {error}")
        QMessageBox.critical(self, "Download Error", error)

def main():
    app = QApplication(sys.argv)

    # Set application icon for taskbar and title bar
    icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 
                            "auto_builder", "asset", "windows-logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ChunkyTimelapseApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()