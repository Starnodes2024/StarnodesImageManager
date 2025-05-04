#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Settings dialog for StarImageBrowse
Allows users to configure application settings.
"""

import logging
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QSpinBox, QCheckBox, QComboBox,
    QPushButton, QFileDialog, QGroupBox, QFormLayout,
    QMessageBox, QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from src.config.theme_manager import ThemeManager

logger = logging.getLogger("StarImageBrowse.ui.settings_dialog")

class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""
    theme_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    
    def get_translation(self, section, key, default=None):
        """Get a translation for a key.
        
        Args:
            section (str): Section in the translations
            key (str): Key in the section
            default (str, optional): Default value if translation not found
            
        Returns:
            str: Translated string or default value
        """
        if self.language_manager:
            return self.language_manager.get_translation(section, key, default)
        return default
    
    def __init__(self, config_manager, theme_manager=None, language_manager=None, parent=None):
        """Initialize the settings dialog.
        
        Args:
            config_manager: Configuration manager instance
            theme_manager: Theme manager instance
            language_manager: Language manager instance
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.language_manager = language_manager
        self.original_config = dict(config_manager.get_all())  # Make a copy
        
        self.setup_ui()
        self.retranslateUi()
        self.load_settings()
        
        # Automatically fetch available Ollama models when the dialog is opened
        QApplication.processEvents()  # Process UI events before making the API call
        self.refresh_ollama_models(silent=True)

    def retranslateUi(self):
        """Update all UI texts according to the current language manager."""
        # Update tab titles
        if hasattr(self, 'tabs'):
            self.tabs.setTabText(0, self.get_translation('settings', 'general', 'General'))
            self.tabs.setTabText(1, self.get_translation('settings', 'thumbnails', 'Thumbnails'))
            self.tabs.setTabText(2, self.get_translation('settings', 'ai', 'AI Settings'))
            self.tabs.setTabText(3, self.get_translation('settings', 'advanced', 'Advanced'))
        # Update dialog title
        self.setWindowTitle(self.get_translation('settings', 'dialog_title', 'Settings'))
        # Update buttons if present
        if hasattr(self, 'findChild'):
            button_box = self.findChild(QDialogButtonBox)
            if button_box:
                button_box.button(QDialogButtonBox.StandardButton.Ok).setText(self.get_translation('settings', 'ok', 'OK'))
                button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(self.get_translation('settings', 'cancel', 'Cancel'))
                button_box.button(QDialogButtonBox.StandardButton.Apply).setText(self.get_translation('settings', 'apply', 'Apply'))
                button_box.button(QDialogButtonBox.StandardButton.Reset).setText(self.get_translation('settings', 'reset', 'Reset'))
        # Update group boxes and labels in each tab if present
        # General tab
        if hasattr(self, 'theme_combo'):
            self.theme_combo.setItemText(0, self.get_translation('settings', 'theme_system', 'System'))
        # Add further UI element translations as needed for all tabs, group boxes, labels, etc.

    def set_language_manager(self, language_manager):
        self.language_manager = language_manager
        self.retranslateUi()

    
    def load_available_languages(self):
        """Load available languages from the data/lang directory."""
        # Clear existing items
        self.language_combo.clear()
        
        # Use the language_manager to get the language directory if available
        if self.language_manager and hasattr(self.language_manager, 'get_language_dir'):
            lang_dir = self.language_manager.get_language_dir()
        else:
            # Fallback to old logic if language_manager is not set
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            lang_dir = os.path.join(app_dir, "data", "lang")
        
        # Check if the directory exists
        if not os.path.exists(lang_dir):
            logger.warning(f"Language directory not found: {lang_dir}")
            # Add English as fallback
            self.language_combo.addItem("English", "en")
            return
        
        # Get all JSON files in the directory
        language_files = [f for f in os.listdir(lang_dir) if f.endswith(".json")]
        
        # If no language files found, add English as fallback
        if not language_files:
            logger.warning("No language files found in the language directory")
            self.language_combo.addItem("English", "en")
            return
        
        # Add each language to the combo box
        for lang_file in language_files:
            try:
                with open(os.path.join(lang_dir, lang_file), "r", encoding="utf-8") as f:
                    lang_data = json.load(f)
                    lang_name = lang_data.get("language", os.path.splitext(lang_file)[0])
                    lang_code = lang_data.get("code", os.path.splitext(lang_file)[0])
                    self.language_combo.addItem(lang_name, lang_code)
            except Exception as e:
                logger.error(f"Error loading language file {lang_file}: {e}")
        
        # If no languages were added (all files had errors), add English as fallback
        if self.language_combo.count() == 0:
            self.language_combo.addItem("English", "en")
    
    def setup_ui(self):
        """Set up the settings dialog UI."""
        self.setMinimumWidth(500)
        # All text will be set in retranslateUi()

        # Main layout
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_general_tab()
        self.create_thumbnails_tab()
        self.create_ai_tab()
        self.create_advanced_tab()
        
        # Translate tab titles
        self.tabs.setTabText(0, self.get_translation('settings', 'general', 'General'))
        self.tabs.setTabText(1, self.get_translation('settings', 'thumbnails', 'Thumbnails'))
        self.tabs.setTabText(2, self.get_translation('settings', 'ai', 'AI'))
        self.tabs.setTabText(3, self.get_translation('settings', 'advanced', 'Advanced'))
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel | 
            QDialogButtonBox.StandardButton.Apply | 
            QDialogButtonBox.StandardButton.Reset
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset_settings)
        layout.addWidget(button_box)
    
    def create_general_tab(self):
        """Create the general settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # UI Settings
        ui_group = QGroupBox(self.get_translation('settings', 'ui_settings', 'User Interface'))
        ui_layout = QFormLayout(ui_group)
        
        # Theme selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System")
        
        # Add themes from the theme manager if available
        if self.theme_manager:
            themes = self.theme_manager.get_theme_list()
            for theme in themes:
                self.theme_combo.addItem(theme["name"], theme["id"])
        else:
            # Fallback to basic themes if theme manager is not available
            self.theme_combo.addItems(["Light", "Dark"])
            
        ui_layout.addRow(self.get_translation('settings', 'theme_label', 'Theme:'), self.theme_combo)
        
        # Language selection
        self.language_combo = QComboBox()
        self.load_available_languages()
        ui_layout.addRow(self.get_translation('settings', 'language_label', 'Language:'), self.language_combo)
        
        # Description option removed due to UI flickering issues
        
        layout.addWidget(ui_group)
        
        # Monitoring Settings
        monitor_group = QGroupBox(self.get_translation('settings', 'monitoring_settings', 'Folder Monitoring'))
        monitor_layout = QFormLayout(monitor_group)
        
        # Watch folders
        self.watch_folders_check = QCheckBox(self.get_translation('settings', 'watch_folders', 'Watch folders for changes'))
        monitor_layout.addRow("", self.watch_folders_check)
        
        # Background scanning
        self.background_scanning_check = QCheckBox(self.get_translation('settings', 'background_scanning', 'Enable background scanning for new images'))
        monitor_layout.addRow("", self.background_scanning_check)
        
        # Background scan interval
        self.background_interval_spin = QSpinBox()
        self.background_interval_spin.setRange(5, 1440)  # 5 min to 24 hours
        self.background_interval_spin.setSuffix(" minutes")
        self.background_interval_spin.setSingleStep(5)
        monitor_layout.addRow(self.get_translation('settings', 'background_scan_interval', 'Background scan interval:'), self.background_interval_spin)
        
        # Scan interval
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1, 1440)  # 1 minute to 24 hours
        self.scan_interval_spin.setSuffix(" minutes")
        self.scan_interval_spin.setEnabled(False)
        self.watch_folders_check.toggled.connect(self.scan_interval_spin.setEnabled)
        monitor_layout.addRow(self.get_translation('settings', 'scan_interval', 'Scan interval:'), self.scan_interval_spin)
        
        layout.addWidget(monitor_group)
        
        # Add stretch
        layout.addStretch(1)
        
        self.tabs.addTab(tab, "General")
    
    def create_thumbnails_tab(self):
        """Create the thumbnails settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Thumbnail Settings
        thumb_group = QGroupBox(self.get_translation('settings', 'thumbnail_settings', 'Thumbnail Settings'))
        thumb_layout = QFormLayout(thumb_group)
        
        # Thumbnail size
        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(50, 500)
        self.thumbnail_size_spin.setSingleStep(10)
        self.thumbnail_size_spin.setSuffix(" px")
        thumb_layout.addRow(self.get_translation('settings', 'thumbnail_size', 'Thumbnail size:'), self.thumbnail_size_spin)
        
        # Thumbnail quality
        self.thumbnail_quality_spin = QSpinBox()
        self.thumbnail_quality_spin.setRange(50, 100)
        self.thumbnail_quality_spin.setSuffix(" %")
        thumb_layout.addRow(self.get_translation('settings', 'thumbnail_quality', 'JPEG quality:'), self.thumbnail_quality_spin)
        
        layout.addWidget(thumb_group)
        
        # Preview Settings
        preview_group = QGroupBox(self.get_translation('settings', 'preview_settings', 'Hover Preview Settings'))
        preview_layout = QFormLayout(preview_group)
        
        # Preview size
        self.preview_size_spin = QSpinBox()
        self.preview_size_spin.setRange(300, 2000)
        self.preview_size_spin.setSingleStep(50)
        self.preview_size_spin.setSuffix(" px")
        preview_layout.addRow(self.get_translation('settings', 'preview_size', 'Max preview size:'), self.preview_size_spin)
        
        # Preview delay
        self.preview_delay_spin = QSpinBox()
        self.preview_delay_spin.setRange(0, 1000)
        self.preview_delay_spin.setSingleStep(50)
        self.preview_delay_spin.setSuffix(" ms")
        preview_layout.addRow(self.get_translation('settings', 'preview_delay', 'Hover delay:'), self.preview_delay_spin)
        
        layout.addWidget(preview_group)
        
        # Add stretch
        layout.addStretch(1)
        
        self.tabs.addTab(tab, "Thumbnails")
    
    def create_ai_tab(self):
        """Create the AI settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Ollama Settings
        ollama_group = QGroupBox(self.get_translation('settings', 'ollama_settings', 'Ollama Settings'))
        ollama_layout = QFormLayout(ollama_group)
        
        # Ollama Server URL
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        ollama_layout.addRow(self.get_translation('settings', 'server_url', 'Server URL:'), self.ollama_url_edit)
        
        # Ollama Model Selection
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.addItems(["llava", "llava:13b", "bakllava"])
        ollama_layout.addRow(self.get_translation('settings', 'model', 'Model:'), self.ollama_model_combo)
        
        # Refresh Models Button
        self.refresh_models_button = QPushButton(self.get_translation('settings', 'refresh_models', 'Refresh Models'))
        self.refresh_models_button.clicked.connect(self.refresh_ollama_models)
        ollama_layout.addRow("", self.refresh_models_button)
        
        # Test Connection Button
        self.test_ollama_button = QPushButton(self.get_translation('settings', 'test_connection', 'Test Connection'))
        self.test_ollama_button.clicked.connect(self.test_ollama_connection)
        ollama_layout.addRow("", self.test_ollama_button)
        
        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 16)
        self.batch_size_spin.setToolTip(self.get_translation('settings', 'batch_size_tooltip', 'Number of images to process in each batch'))
        ollama_layout.addRow(self.get_translation('settings', 'batch_size', 'Batch size:'), self.batch_size_spin)
        
        # Ollama System Prompt
        self.ollama_system_prompt_edit = QLineEdit()
        self.ollama_system_prompt_edit.setPlaceholderText(self.get_translation('settings', 'system_prompt_placeholder', 'Describe this image concisely, start with main colors...'))
        self.ollama_system_prompt_edit.setMinimumWidth(300)
        ollama_layout.addRow(self.get_translation('settings', 'system_prompt', 'System prompt:'), self.ollama_system_prompt_edit)
        
        layout.addWidget(ollama_group)
        
        # Description Generation Settings
        desc_group = QGroupBox(self.get_translation('settings', 'desc_generation_settings', 'Description Generation Settings'))
        desc_layout = QFormLayout(desc_group)
        
        # Default processing mode
        self.processing_mode_combo = QComboBox()
        self.processing_mode_combo.addItems([
            self.get_translation('settings', 'new_images_only', 'New Images Only'),
            self.get_translation('settings', 'all_images', 'All Images')
        ])
        desc_layout.addRow(self.get_translation('settings', 'default_processing_mode', 'Default processing mode:'), self.processing_mode_combo)
        
        layout.addWidget(desc_group)
        
        # Add stretch
        layout.addStretch(1)
        
        self.tabs.addTab(tab, "AI Settings")
    
    def create_advanced_tab(self):
        """Create the advanced settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Database Settings
        db_group = QGroupBox(self.get_translation('settings', 'database_settings', 'Database Settings'))
        db_layout = QFormLayout(db_group)
        
        # Database path
        self.db_path_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        self.db_path_layout.addWidget(self.db_path_edit)
        
        self.db_path_button = QPushButton(self.get_translation('settings', 'browse', 'Browse...'))
        self.db_path_button.clicked.connect(self.browse_db_path)
        self.db_path_layout.addWidget(self.db_path_button)
        
        db_layout.addRow(self.get_translation('settings', 'database_path', 'Database Path:'), self.db_path_layout)
        
        layout.addWidget(db_group)
        
        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch(1)
        
        self.reset_button = QPushButton(self.get_translation('settings', 'reset_all', 'Reset All Settings'))
        self.reset_button.clicked.connect(self.reset_all_settings)
        reset_layout.addWidget(self.reset_button)
        
        layout.addLayout(reset_layout)
        
        # Add stretch
        layout.addStretch(1)
        
        self.tabs.addTab(tab, "Advanced")
    
    def load_settings(self):
        """Load settings from configuration manager into UI."""
        # General tab
        watch_folders = self.config_manager.get("monitoring", "watch_folders", True)
        self.watch_folders_check.setChecked(watch_folders)
        
        bg_scanning = self.config_manager.get("monitoring", "background_scanning", True)
        self.background_scanning_check.setChecked(bg_scanning)
        
        scan_interval = self.config_manager.get("monitoring", "scan_interval", 300)
        self.scan_interval_spin.setValue(scan_interval)
        
        # Load theme setting
        theme = self.config_manager.get("ui", "theme", "System")
        theme_index = self.theme_combo.findText(theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
        else:
            # Look for theme by ID in data
            for i in range(self.theme_combo.count()):
                if self.theme_combo.itemData(i) == theme:
                    self.theme_combo.setCurrentIndex(i)
                    break
                    
        # Load language setting
        language = self.config_manager.get("ui", "language", "en")
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == language:
                self.language_combo.setCurrentIndex(i)
                break
        
        # Load thumbnail settings
        thumb_size = self.config_manager.get("thumbnails", "size", 200)
        self.thumbnail_size_spin.setValue(thumb_size)
        
        quality = self.config_manager.get("thumbnails", "quality", 85)
        self.thumbnail_quality_spin.setValue(quality)
        
        # Load preview settings
        preview_size = self.config_manager.get("thumbnails", "preview_size", 700)
        self.preview_size_spin.setValue(preview_size)
        
        preview_delay = self.config_manager.get("thumbnails", "preview_delay", 300)
        self.preview_delay_spin.setValue(preview_delay)
        
        # AI tab - Ollama settings
        self.ollama_url_edit.setText(
            self.config_manager.get("ollama", "server_url", "http://localhost:11434")
        )
        
        ollama_model = self.config_manager.get("ollama", "model", "llava")
        index = self.ollama_model_combo.findText(ollama_model)
        if index >= 0:
            self.ollama_model_combo.setCurrentIndex(index)
        else:
            self.ollama_model_combo.setCurrentText(ollama_model)
            
        # Ollama system prompt
        default_prompt = "Describe this image concisely, focusing on the main subject and key visual elements."
        self.ollama_system_prompt_edit.setText(
            self.config_manager.get("ollama", "system_prompt", default_prompt)
        )
        
        # AI tab - Batch size
        self.batch_size_spin.setValue(
            self.config_manager.get("ai", "batch_size", 1)
        )
        
        # Advanced tab
        self.db_path_edit.setText(
            self.config_manager.get("database", "path", "")
        )
        
        # Description generation settings
        process_all = self.config_manager.get("ai", "process_all_images", False)
        self.processing_mode_combo.setCurrentIndex(1 if process_all else 0)
    
    def save_settings(self):
        """Save settings from UI to configuration manager."""
        # Save general settings
        self.config_manager.set("monitoring", "watch_folders", self.watch_folders_check.isChecked())
        self.config_manager.set("monitoring", "background_scanning", self.background_scanning_check.isChecked())
        self.config_manager.set("monitoring", "scan_interval", self.scan_interval_spin.value())
        
        # Save theme setting
        theme_index = self.theme_combo.currentIndex()
        theme_data = self.theme_combo.itemData(theme_index)
        if theme_data:
            self.config_manager.set("ui", "theme", theme_data)
            self.theme_changed.emit(theme_data)
        else:
            theme = self.theme_combo.currentText()
            self.config_manager.set("ui", "theme", theme)
            self.theme_changed.emit(theme)
            
        # Save language setting
        language_index = self.language_combo.currentIndex()
        language_code = self.language_combo.itemData(language_index)
        if language_code:
            self.config_manager.set("ui", "language", language_code)
            self.language_changed.emit(language_code)
        
        # Save thumbnail settings
        self.config_manager.set("thumbnails", "size", self.thumbnail_size_spin.value())
        self.config_manager.set("thumbnails", "quality", self.thumbnail_quality_spin.value())
        
        # Save preview settings
        self.config_manager.set("thumbnails", "preview_size", self.preview_size_spin.value())
        self.config_manager.set("thumbnails", "preview_delay", self.preview_delay_spin.value())
        
        # Apply preview settings to ThumbnailWidget class
        from .thumbnail_widget import ThumbnailWidget
        ThumbnailWidget.set_preview_size(self.preview_size_spin.value())
        ThumbnailWidget.set_hover_delay(self.preview_delay_spin.value())
        
        # AI tab - Ollama settings
        self.config_manager.set("ollama", "server_url", self.ollama_url_edit.text())
        self.config_manager.set("ollama", "model", self.ollama_model_combo.currentText())
        self.config_manager.set("ollama", "system_prompt", self.ollama_system_prompt_edit.text())
        
        # AI tab - Batch size
        self.config_manager.set("ai", "batch_size", self.batch_size_spin.value())
        
        # Advanced tab
        self.config_manager.set("database", "path", self.db_path_edit.text())
        
        # Description generation settings
        process_all = (self.processing_mode_combo.currentIndex() == 1)  # 1 = All Images
        self.config_manager.set("ai", "process_all_images", process_all)
        
        # Save to file
        self.config_manager.save()
    
    def browse_model_path(self):
        """Browse for AI model directory."""
        current_path = self.model_path_edit.text()
        directory = QFileDialog.getExistingDirectory(
            self, "Select AI Model Directory", 
            current_path if current_path else os.path.expanduser("~")
        )
        
        if directory:
            self.model_path_edit.setText(directory)
    
    def browse_db_path(self):
        """Browse for database file."""
        current_path = self.db_path_edit.text()
        directory = os.path.dirname(current_path) if current_path else os.path.expanduser("~")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Database File", 
            directory,
            "SQLite Database (*.db);;All Files (*)"
        )
        
        if file_path:
            self.db_path_edit.setText(file_path)
    
    def refresh_ollama_models(self, silent=False):
        """Refresh the list of available Ollama models.
        
        Args:
            silent (bool): If True, don't show any message boxes
        """
        try:
            import requests
            server_url = self.ollama_url_edit.text().strip()
            if not server_url:
                server_url = "http://localhost:11434"
                self.ollama_url_edit.setText(server_url)
            
            # Save current selection
            current_model = self.ollama_model_combo.currentText()
            
            # Get list of models from Ollama API
            response = requests.get(f"{server_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                models = [model['name'] for model in models_data.get('models', [])]
                
                if not models:
                    logger.warning("No models found on Ollama server")
                    if not silent:
                        QMessageBox.warning(
                            self, "No Models Found", 
                            "No models were found on the Ollama server. Please make sure you have models installed.",
                            QMessageBox.StandardButton.Ok
                        )
                    return
                
                # Update combo box
                self.ollama_model_combo.clear()
                self.ollama_model_combo.addItems(models)
                
                # Restore selection if possible
                index = self.ollama_model_combo.findText(current_model)
                if index >= 0:
                    self.ollama_model_combo.setCurrentIndex(index)
                elif models:
                    # Find a vision model if available
                    vision_models = [m for m in models if 'llava' in m.lower() or 'bakllava' in m.lower() or 'vision' in m.lower()]
                    if vision_models:
                        self.ollama_model_combo.setCurrentText(vision_models[0])
                        logger.info(f"Selected vision model: {vision_models[0]}")
                    else:
                        # Just select the first model if no vision models are available
                        self.ollama_model_combo.setCurrentIndex(0)
                        logger.info(f"No vision models found, selected: {models[0]}")
                
                if not silent:
                    QMessageBox.information(
                        self, self.get_translation('settings', 'models_refreshed', 'Models Refreshed'), 
                        self.get_translation('settings', 'models_found', 'Found {count} models on the Ollama server.').format(count=len(models)),
                        QMessageBox.StandardButton.Ok
                    )
            else:
                logger.warning(f"Failed to get models from Ollama server: {response.status_code}")
                if not silent:
                    QMessageBox.warning(
                        self, self.get_translation('settings', 'connection_error', 'Connection Error'), 
                        self.get_translation('settings', 'failed_get_models', 'Failed to get models from Ollama server. Status code: {code}').format(code=response.status_code),
                        QMessageBox.StandardButton.Ok
                    )
        except Exception as e:
            logger.error(f"Error connecting to Ollama server: {e}")
            if not silent:
                QMessageBox.critical(
                    self, self.get_translation('common', 'error', 'Error'), 
                    self.get_translation('settings', 'error_connecting', 'Error connecting to Ollama server: {error}').format(error=str(e)),
                    QMessageBox.StandardButton.Ok
                )
    
    def test_ollama_connection(self):
        """Test the connection to the Ollama server."""
        try:
            import requests
            server_url = self.ollama_url_edit.text().strip()
            if not server_url:
                server_url = "http://localhost:11434"
                self.ollama_url_edit.setText(server_url)
            
            # Test connection to Ollama API
            response = requests.get(f"{server_url}/api/version")
            if response.status_code == 200:
                version_data = response.json()
                version = version_data.get('version', 'unknown')
                
                QMessageBox.information(
                    self, self.get_translation('settings', 'connection_successful', 'Connection Successful'), 
                    self.get_translation('settings', 'connected_to_ollama', 'Successfully connected to Ollama server.\nVersion: {version}').format(version=version),
                    QMessageBox.StandardButton.Ok
                )
            else:
                QMessageBox.warning(
                    self, self.get_translation('settings', 'connection_error', 'Connection Error'), 
                    self.get_translation('settings', 'failed_connect', 'Failed to connect to Ollama server. Status code: {code}').format(code=response.status_code),
                    QMessageBox.StandardButton.Ok
                )
        except Exception as e:
            QMessageBox.critical(
                self, self.get_translation('common', 'error', 'Error'), 
                self.get_translation('settings', 'error_connecting', 'Error connecting to Ollama server: {error}').format(error=str(e)),
                QMessageBox.StandardButton.Ok
            )
    
    def apply_settings(self):
        """Apply settings without closing dialog."""
        self.save_settings()
        
        # Inform user
        QMessageBox.information(
            self, self.get_translation('settings', 'settings_applied', 'Settings Applied'), 
            self.get_translation('settings', 'settings_applied_msg', 'Settings have been applied. Some changes may require restarting the application.'),
            QMessageBox.StandardButton.Ok
        )
    
    def reset_settings(self):
        """Reset settings to values from configuration manager."""
        self.load_settings()
    
    def reset_all_settings(self):
        """Reset all settings to default values."""
        # Confirm reset
        confirm = QMessageBox.question(
            self, self.get_translation('settings', 'confirm_reset', 'Confirm Reset'), 
            self.get_translation('settings', 'confirm_reset_msg', 'Are you sure you want to reset all settings to their default values?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_to_defaults()
            self.load_settings()
            
            QMessageBox.information(
                self, self.get_translation('settings', 'settings_reset', 'Settings Reset'), 
                self.get_translation('settings', 'settings_reset_msg', 'All settings have been reset to their default values.'),
                QMessageBox.StandardButton.Ok
            )
    
    def accept(self):
        """Handle dialog acceptance (OK button)."""
        self.save_settings()
        super().accept()
    
    def reject(self):
        """Handle dialog rejection (Cancel button)."""
        # Restore original config
        self.config_manager.config = self.original_config
        super().reject()
