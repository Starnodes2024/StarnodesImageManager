#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launch controller for StarImageBrowse
Handles the startup sequence and main window creation.
"""

import os
import logging
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

from src.config.config_manager import ConfigManager
from src.database.db_manager import DatabaseManager
from src.ui.main_window import MainWindow

logger = logging.getLogger("StarImageBrowse.ui.launch_controller")

class LaunchController:
    """Controls the startup sequence for StarImageBrowse."""
    
    def __init__(self):
        """Initialize the launch controller."""
        self.config_manager = ConfigManager()
        self.db_manager = None
        self.main_window = None
        self.app = QApplication.instance()
        
        # Get database path
        db_path = self.config_manager.get("database", "path")
        if not os.path.isabs(db_path):
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(app_dir, db_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database manager
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.initialize_database()
    
    def start(self):
        """Start the application."""
        logger.info("Starting application launch sequence")
        
        # Check if this is the first run
        is_first_run = self.config_manager.get("app", "first_run")
        
        # If this is the first run, initialize with default settings
        if is_first_run:
            logger.info("First run - initializing with default settings")
            self.initialize_default_settings()
            
        # Show main window directly
        logger.info("Showing main window")
        QTimer.singleShot(0, self.show_main_window)
    
    def initialize_default_settings(self):
        """Initialize the application with default settings."""
        try:
            logger.info("Initializing default settings")
            
            # Default Ollama settings
            self.config_manager.set("ollama", "server_url", "http://localhost:11434")
            self.config_manager.set("ollama", "model", "llava")  # Default to llava if available
            
            # AI settings
            self.config_manager.set("ai", "process_all_images", False)
            
            # UI settings
            self.config_manager.set("app", "theme", "system")
            self.config_manager.set("thumbnails", "size", 200)  # Medium size
            self.config_manager.set("ui", "show_descriptions", True)
            self.config_manager.set("monitor", "watch_folders", True)
            
            # Set first run flag to false
            self.config_manager.set("app", "first_run", False)
            
            # Save to file
            self.config_manager.save()
            logger.info("Default settings saved successfully")
            
        except Exception as e:
            logger.error(f"Error initializing default settings: {e}")
    
    def show_main_window(self):
        """Show the main window."""
        try:
            if not self.main_window:
                logger.info("Creating main window")
                self.main_window = MainWindow(self.db_manager)
                
                # Store reference in app to prevent garbage collection
                self.app._main_window = self.main_window
            
            logger.info("Showing main window")
            self.main_window.show()
            
            # Process events to ensure window is shown
            QApplication.processEvents()
            
            # Ensure window is visible and active
            self.main_window.setWindowState(
                (self.main_window.windowState() & ~Qt.WindowState.WindowMinimized) | 
                Qt.WindowState.WindowActive
            )
            self.main_window.activateWindow()
            self.main_window.raise_()
            
            # Process events again to ensure changes are applied
            QApplication.processEvents()
            
            logger.info("Main window shown successfully")
            
        except Exception as e:
            logger.error(f"Error creating/showing main window: {e}")
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to create main window: {e}\n\nThe application will now exit."
            )
            QApplication.instance().quit()


def launch_application():
    """Launch the application.
    
    Returns:
        int: Exit code
    """
    try:
        # Create application
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        app.setApplicationName("StarImageBrowse")
        app.setOrganizationName("StarKeeper")
        app.setOrganizationDomain("starkeeper.example.com")
        
        # Keep the application running
        app.setQuitOnLastWindowClosed(False)
        
        # Create launch controller
        controller = LaunchController()
        
        # Store reference to prevent garbage collection
        app._controller = controller
        
        # Start launch sequence
        controller.start()
        
        logger.info("Starting application event loop")
        # Start event loop
        return app.exec()
        
    except Exception as e:
        logger.error(f"Error in launch_application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(launch_application())
