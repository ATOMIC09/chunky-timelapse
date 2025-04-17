#!/usr/bin/env python3
import sys
import os
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QLineEdit, 
    QGroupBox, QFormLayout, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSlot

class ChunkyTimelapseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Default paths
        self.chunky_launcher_path = ""
        self.scenes_dir = os.path.join(os.path.expanduser("~"), ".chunky", "scenes")
        self.world_dir = ""
        self.scene_name = ""
        self.scene_json_data = None
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Chunky Timelapse Generator")
        self.setGeometry(100, 100, 800, 600)
        
        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
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
        main_layout.addWidget(paths_group)
        
        # Scene info
        scene_info_group = QGroupBox("Scene Information")
        scene_info_layout = QVBoxLayout()
        self.scene_info_text = QTextEdit()
        self.scene_info_text.setReadOnly(True)
        scene_info_layout.addWidget(self.scene_info_text)
        scene_info_group.setLayout(scene_info_layout)
        main_layout.addWidget(scene_info_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.render_button = QPushButton("Render Scene")
        self.render_button.clicked.connect(self.render_scene)
        self.render_button.setEnabled(False)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.render_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Initialize scene dropdown
        self.refresh_scenes()
        
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
            
    def on_scene_selected(self, scene_name):
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
            
    def render_scene(self):
        if not self.update_scene_json():
            return
            
        try:
            cmd = [
                "java", "-jar", self.chunky_launcher_path,
                "-scene-dir", self.scenes_dir,
                "-render", self.scene_name,
                "-f"
            ]
            
            # Display command
            cmd_str = " ".join(cmd)
            msg = f"Running command:\n{cmd_str}\n\nThis will start the rendering process. Continue?"
            
            reply = QMessageBox.question(
                self, "Confirm Render", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                subprocess.Popen(cmd)
                QMessageBox.information(
                    self, "Render Started", 
                    "The render has been started. Check Chunky for progress."
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start render: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = ChunkyTimelapseApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()